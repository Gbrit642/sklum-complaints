import csv
import io
import os

import google.auth
import google.auth.transport.requests
import httpx
from google.adk.tools import ToolContext

BATCH_SERVICE_URL = os.environ.get("BATCH_SERVICE_URL", "")
DEFAULT_DATASET = "gs://sklum-complaints-agent-460311/datasets/current/complaints.csv"
GCS_BUCKET = "sklum-complaints-agent-460311"
GCS_CSV_BLOB = "datasets/current/complaints.csv"
GCS_PUBLIC_BASE = "https://storage.googleapis.com/sklum-complaints-agent-460311/datasets/current/images/"


def _get_identity_token(audience: str) -> str:
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()

    from google.auth import impersonated_credentials
    from google.oauth2 import id_token

    token = id_token.fetch_id_token(auth_req, audience)
    return token


def trigger_batch_analysis(
    dataset_gcs_path: str,
    tool_context: ToolContext,
) -> dict:
    """Triggers batch analysis of the Sklum complaint dataset.

    Analyzes all complaints (text and images) in the specified GCS dataset,
    detects patterns across the corpus, and returns categorized, prioritized
    results with damage assessments from images.

    Args:
        dataset_gcs_path: GCS path to the complaints CSV file.
            Default: gs://sklum-complaints-agent-460311/datasets/current/complaints.csv
    """
    if not BATCH_SERVICE_URL:
        return {
            "status": "error",
            "message": "BATCH_SERVICE_URL not configured. Set it as an environment variable.",
        }

    if not dataset_gcs_path:
        dataset_gcs_path = DEFAULT_DATASET

    try:
        token = _get_identity_token(BATCH_SERVICE_URL)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
    except Exception:
        headers = {"Content-Type": "application/json"}

    try:
        response = httpx.post(
            f"{BATCH_SERVICE_URL}/analyze",
            json={"dataset_gcs_path": dataset_gcs_path},
            headers=headers,
            timeout=300.0,
        )

        if response.status_code != 200:
            return {
                "status": "error",
                "message": f"Batch analysis failed: {response.status_code} - {response.text[:500]}",
            }

        results = response.json()
        tool_context.state["last_analysis_results"] = results
        tool_context.state["last_dataset_path"] = dataset_gcs_path
        return results

    except httpx.TimeoutException:
        return {
            "status": "error",
            "message": "Batch analysis timed out after 300 seconds. The dataset may be too large.",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to connect to batch service: {str(e)[:200]}",
        }


def _get_image_url(complaint_id: str) -> str:
    """Get the public GCS URL for a complaint's image."""
    return f"{GCS_PUBLIC_BASE}{complaint_id}.png"


def _load_complaints_from_gcs() -> list[dict]:
    """Load complaints CSV from GCS via public URL."""
    url = f"https://storage.googleapis.com/{GCS_BUCKET}/{GCS_CSV_BLOB}"
    response = httpx.get(url, timeout=30.0)
    response.raise_for_status()
    reader = csv.DictReader(io.StringIO(response.text))
    return list(reader)


def search_complaint(
    complaint_id: str,
    tool_context: ToolContext,
) -> dict:
    """Searches for a specific complaint ticket by its ID directly from the
    complaint database. Use this when the user asks about a specific complaint
    and no batch analysis has been run yet.

    Returns the raw complaint record including text, product info, and a link
    to the image if available.

    Args:
        complaint_id: The complaint identifier (e.g. 'REC-2024-0001')
    """
    try:
        complaints = _load_complaints_from_gcs()
    except Exception as e:
        return {
            "status": "error",
            "message": f"No se pudo acceder a la base de datos de reclamaciones: {str(e)[:200]}",
        }

    for complaint in complaints:
        if complaint.get("complaint_id") == complaint_id:
            response = {"status": "success", "complaint": complaint}
            if complaint.get("has_image", "").lower() == "true":
                response["image_url"] = _get_image_url(complaint_id)
            return response

    available_ids = [c.get("complaint_id", "") for c in complaints[:10]]
    return {
        "status": "not_found",
        "message": f"Reclamación {complaint_id} no encontrada.",
        "sample_ids": available_ids,
    }


def get_complaint_details(
    complaint_id: str,
    tool_context: ToolContext,
) -> dict:
    """Retrieves the AI-analyzed details of a specific complaint by its ID.

    This returns the enriched analysis (priority, category, sentiment,
    damage type, suggested action) from the last batch analysis run.
    If no batch analysis has been run, it falls back to searching the
    raw complaint database directly.

    Args:
        complaint_id: The complaint identifier (e.g. 'REC-2024-0042')
    """
    results = tool_context.state.get("last_analysis_results")

    if results:
        complaints = results.get("complaints", [])
        for complaint in complaints:
            if complaint.get("complaint_id") == complaint_id:
                response = {"status": "success", "complaint": complaint}
                if complaint.get("has_image"):
                    response["image_url"] = _get_image_url(complaint_id)
                return response

    return search_complaint(complaint_id, tool_context)


def get_complaint_image_url(
    complaint_id: str,
    tool_context: ToolContext,
) -> dict:
    """Generates a link to view the image attached to a complaint.

    Use this when the user wants to see the photo/image evidence for a
    specific complaint. Returns a direct URL to the image.

    Args:
        complaint_id: The complaint identifier (e.g. 'REC-2024-0001')
    """
    return {
        "status": "success",
        "complaint_id": complaint_id,
        "image_url": _get_image_url(complaint_id),
        "note": "Haz clic en el enlace para ver la imagen adjunta a esta reclamación.",
    }
