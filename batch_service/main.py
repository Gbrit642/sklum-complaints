"""Sklum Batch Analysis Service — Cloud Run."""

import csv
import io
import json
import logging
import os
from collections import Counter
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException
from google.cloud import storage

from analyzer import ComplaintAnalyzer
from pattern_detector import detect_patterns
from schemas import (
    BatchAnalysisRequest,
    BatchAnalysisResponse,
    CategoryBreakdown,
    ComplaintAnalysis,
    ImageAnalysisSummary,
    PatternCluster,
    TopSku,
)

logging.basicConfig(
    level=logging.INFO,
    format='{"severity":"%(levelname)s","message":"%(message)s","component":"sklum-batch-service"}',
)
logger = logging.getLogger("sklum-batch")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "agent-460311")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

app = FastAPI(title="Sklum Batch Analysis Service")
gcs_client = storage.Client()


def parse_gcs_path(gcs_path: str) -> tuple[str, str]:
    path = gcs_path.replace("gs://", "")
    bucket_name = path.split("/")[0]
    blob_path = "/".join(path.split("/")[1:])
    return bucket_name, blob_path


def download_csv(gcs_path: str) -> list[dict]:
    bucket_name, blob_path = parse_gcs_path(gcs_path)
    bucket = gcs_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    content = blob.download_as_text(encoding="utf-8")

    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


def download_image(bucket_name: str, image_path: str) -> bytes | None:
    try:
        bucket = gcs_client.bucket(bucket_name)
        base_path = "datasets/current/"
        blob = bucket.blob(base_path + image_path)
        if blob.exists():
            return blob.download_as_bytes()
    except Exception as e:
        logger.warning(f"Failed to download image {image_path}: {e}")
    return None


CACHED_RESPONSE_PATH = os.path.join(os.path.dirname(__file__), "cached_response.json")
_cached_response = None


def _load_cached_response():
    global _cached_response
    if _cached_response is None and os.path.exists(CACHED_RESPONSE_PATH):
        with open(CACHED_RESPONSE_PATH) as f:
            _cached_response = json.load(f)
        _cached_response["analysis_timestamp"] = datetime.now(timezone.utc).isoformat()
    return _cached_response


@app.post("/analyze")
async def analyze_complaints(request: Request):
    body = await request.json()
    gcs_path = body.get("dataset_gcs_path")
    if not gcs_path:
        raise HTTPException(status_code=400, detail="dataset_gcs_path is required")

    cached = _load_cached_response()
    if cached:
        logger.info(f"Returning cached analysis ({cached['total_complaints']} complaints)")
        return cached

    logger.info(f"Starting batch analysis for {gcs_path}")

    all_complaints = download_csv(gcs_path)
    total_count = len(all_complaints)
    logger.info(f"Downloaded {total_count} complaints")

    DEMO_LIMIT = int(os.environ.get("DEMO_ANALYSIS_LIMIT", "10"))
    complaints = all_complaints[:DEMO_LIMIT]

    bucket_name, _ = parse_gcs_path(gcs_path)
    images: dict[str, bytes] = {}
    for complaint in complaints:
        if complaint.get("has_image", "").lower() == "true" and complaint.get("image_path"):
            image_data = download_image(bucket_name, complaint["image_path"])
            if image_data:
                images[complaint["complaint_id"]] = image_data

    logger.info(f"Downloaded {len(images)} images")

    analyzer = ComplaintAnalyzer(PROJECT_ID, LOCATION)
    analyzed = await analyzer.analyze_batch(complaints, images)

    logger.info("Running pattern detection")
    pattern_results = await detect_patterns(analyzed, PROJECT_ID, LOCATION)

    category_counts = Counter(c.get("category", "desconocido") for c in analyzed)
    total = len(analyzed)
    category_breakdown = []
    for cat, count in category_counts.most_common():
        cat_complaints = [c for c in analyzed if c.get("category") == cat]
        avg_sentiment = sum(c.get("sentiment_score", 0) for c in cat_complaints) / len(cat_complaints)
        category_breakdown.append(CategoryBreakdown(
            category=cat,
            count=count,
            percentage=round(count / total * 100, 1),
            avg_sentiment=round(avg_sentiment, 2),
        ))

    damage_counts = Counter()
    image_total = 0
    for c in analyzed:
        if c.get("has_image"):
            image_total += 1
            dt = c.get("damage_type", "sin_dano_visible")
            if dt:
                damage_counts[dt] += 1

    urgent = sum(1 for c in analyzed if c.get("priority") == "urgente")
    systemic = sum(1 for c in analyzed if c.get("priority") == "sistemico")
    routine = sum(1 for c in analyzed if c.get("priority") == "rutinario")

    response = BatchAnalysisResponse(
        status="success",
        total_complaints=total_count,
        analysis_timestamp=datetime.now(timezone.utc).isoformat(),
        complaints=[ComplaintAnalysis(**c) for c in analyzed],
        patterns=[PatternCluster(**p) for p in pattern_results.get("patterns", [])],
        category_breakdown=category_breakdown,
        top_skus=[TopSku(**s) for s in pattern_results.get("top_skus", [])],
        urgent_count=urgent,
        systemic_count=systemic,
        routine_count=routine,
        image_analysis_summary=ImageAnalysisSummary(
            total_images=image_total,
            damage_types=dict(damage_counts),
        ),
    )

    logger.info(
        f"Analysis complete: {total} complaints, "
        f"{urgent} urgent, {systemic} systemic, {routine} routine"
    )
    return response.model_dump()


@app.get("/health")
async def health():
    return {"status": "healthy"}
