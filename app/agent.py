# ruff: noqa
import os

import google.auth
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from . import tools
from .prompts import ROOT_INSTRUCTION

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

root_agent = Agent(
    name="sklum_complaint_analyst",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        temperature=0.2,
    ),
    description=(
        "Analiza reclamaciones de clientes de Sklum, detecta patrones "
        "sistémicos y genera informes priorizados con análisis de imágenes."
    ),
    instruction=ROOT_INSTRUCTION,
    tools=[
        tools.trigger_batch_analysis,
        tools.search_complaint,
        tools.get_complaint_details,
        tools.get_complaint_image_url,
    ],
    output_key="analysis_report",
)

app = App(
    root_agent=root_agent,
    name="app",
)
