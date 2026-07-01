# Sklum Complaint Analysis Agent

An ADK agent that analyzes customer complaints for Sklum (furniture e-commerce), detects systemic patterns, and generates prioritized insight reports with multimodal image analysis.

Built with [Google Agent Development Kit (ADK)](https://adk.dev/), deployed on [Agent Runtime](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime), and published to [Gemini Enterprise](https://docs.cloud.google.com/gemini/enterprise/docs).

## Architecture

```
[Business User in Gemini Enterprise]
        |
        v
[Agent Runtime — ADK Agent (sklum_complaint_analyst)]
   - Single LlmAgent with 4 tools
   - Orchestrates analysis, generates reports
   - Model: gemini-flash-latest
        |
        v  (HTTP POST, SA identity token)
[Cloud Run — Batch Analysis Service]
   - Processes complaints CSV + images from GCS
   - Per-complaint Gemini analysis (text + image)
   - Cross-corpus pattern detection
   - Returns structured BatchAnalysisResponse
        |
        v  (reads)
[GCS — gs://sklum-complaints-agent-460311/]
   - datasets/current/complaints.csv (55 records)
   - datasets/current/images/ (~38 product damage photos)
```

## Features

- **Direct complaint lookup** — search any complaint by ID, view details and attached photo instantly
- **Full corpus analysis** — batch-process all complaints (text + images) with Gemini, detect patterns, generate a structured report
- **Image analysis** — AI analyzes damage photos to classify damage type and severity
- **Pattern detection** — identifies systemic issues (e.g., recurring courier problems, defective SKUs)
- **Priority classification** — categorizes complaints as urgent, systemic, or routine
- **Interactive follow-up** — drill into patterns, filter by category/SKU, view specific complaints after analysis

## Project Structure

```
sklum-complaints/
├── app/                          # ADK agent
│   ├── agent.py                  # Root agent definition
│   ├── tools.py                  # 4 tools: batch analysis, search, details, image URL
│   ├── prompts.py                # System instruction (Spanish)
│   ├── fast_api_app.py           # FastAPI serving layer
│   └── app_utils/                # A2A routes, telemetry, session services
├── batch_service/                # Cloud Run batch processing service
│   ├── main.py                   # FastAPI /analyze endpoint
│   ├── analyzer.py               # Per-complaint Gemini analysis
│   ├── pattern_detector.py       # Cross-corpus pattern detection
│   ├── schemas.py                # Pydantic models
│   └── Dockerfile
├── scripts/                      # Data generation utilities
│   ├── generate_data.py          # Generate synthetic complaints (Gemini)
│   ├── generate_images.py        # Generate damage photos (Gemini Image)
│   └── upload_to_gcs.py          # Upload to GCS
├── data/                         # Local data files
├── tests/                        # Unit, integration, eval tests
├── Dockerfile                    # Agent Runtime container
└── pyproject.toml
```

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- [agents-cli](https://cloud.google.com/gemini-enterprise-agent-platform/build/runtime) (`uv tool install google-agents-cli`)
- A GCP project with Vertex AI, Cloud Run, and Cloud Storage APIs enabled

## Quick Start

```bash
# Install dependencies
agents-cli install

# Run locally
agents-cli playground
```

## Agent Tools

| Tool | Purpose |
|------|---------|
| `trigger_batch_analysis` | Triggers Cloud Run service to analyze all complaints (text + images) |
| `search_complaint` | Direct lookup of a complaint by ID from the CSV database |
| `get_complaint_details` | Retrieves AI-enriched analysis from batch results |
| `get_complaint_image_url` | Returns the public URL for a complaint's damage photo |

## Deployment

### Deploy Batch Service (Cloud Run)

```bash
gcloud run deploy sklum-batch-service \
  --source=batch_service \
  --project=YOUR_PROJECT \
  --region=us-central1 \
  --service-account=sklum-batch-sa@YOUR_PROJECT.iam.gserviceaccount.com \
  --cpu=2 --memory=2Gi --timeout=300 \
  --no-allow-unauthenticated
```

### Deploy Agent (Agent Runtime)

```bash
agents-cli deploy \
  --service-account sklum-agent-sa@YOUR_PROJECT.iam.gserviceaccount.com \
  --update-env-vars "BATCH_SERVICE_URL=https://YOUR_BATCH_SERVICE_URL"
```

### Publish to Gemini Enterprise

```bash
agents-cli publish gemini-enterprise \
  --registration-type adk \
  --gemini-enterprise-app-id YOUR_GE_APP_ID \
  --display-name "Sklum Complaint Analyst" \
  --description "Analiza reclamaciones de clientes de Sklum"
```

## Data Generation

All complaint data is synthetic, generated with Gemini:

```bash
# Generate 55 Spanish complaints
python scripts/generate_data.py

# Generate damage photos
python scripts/generate_images.py

# Upload to GCS
python scripts/upload_to_gcs.py
```

Complaints are pre-masked (no real PII): customer IDs as `CLI-AXXX`, order IDs as `ORD-XXXX-XXXX`.

## Service Accounts & IAM

| Service Account | Purpose | Required Roles |
|---|---|---|
| `sklum-agent-sa` | ADK Agent on Agent Runtime | `roles/run.invoker`, `roles/storage.objectViewer`, `roles/aiplatform.user` |
| `sklum-batch-sa` | Cloud Run batch service | `roles/storage.objectViewer`, `roles/aiplatform.user` |

## Observability

- **Cloud Trace** — automatic distributed tracing on Agent Runtime
- **Cloud Logging** — structured JSON logging from Cloud Run batch service
- **Prompt-response logging** — enabled via `GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true`

## Demo Usage

In Gemini Enterprise, select the Sklum Complaint Analyst agent and try:

```
Analiza todas las reclamaciones del dataset actual
```

```
Dame más información sobre la reclamación REC-2024-0001
```

```
Muéstrame la foto de esta reclamación
```

## Tech Stack

- **Agent Framework**: Google ADK 2.x
- **LLM**: Gemini Flash (latest)
- **Deployment**: Agent Runtime (Reasoning Engine)
- **Frontend**: Gemini Enterprise
- **Batch Processing**: Cloud Run + FastAPI
- **Storage**: Google Cloud Storage
- **Language**: Python 3.12
