"""Cross-corpus pattern detection using Gemini."""

import json
import logging

from google import genai
from google.genai import types

logger = logging.getLogger("sklum-batch")

PATTERN_PROMPT = """Analiza este conjunto de {count} reclamaciones ya categorizadas de Sklum (tienda online de muebles) y detecta patrones.

DATOS AGREGADOS DE RECLAMACIONES:
{aggregated_data}

ANALIZA Y RESPONDE en JSON con esta estructura exacta:
{{
  "patterns": [
    {{
      "pattern_id": "PAT-001",
      "theme": "nombre corto del patrón",
      "description": "descripción detallada del patrón detectado",
      "complaint_ids": ["REC-2024-XXXX", ...],
      "frequency": número_de_reclamaciones,
      "trend": "creciente|estable|decreciente",
      "root_cause_hypothesis": "hipótesis sobre la causa raíz"
    }}
  ],
  "top_skus": [
    {{
      "sku": "SKU-XXXX-XXX",
      "product_name": "nombre del producto",
      "complaint_count": número,
      "main_issue": "problema principal reportado"
    }}
  ]
}}

INSTRUCCIONES:
1. Identifica temas recurrentes (>= 3 reclamaciones similares)
2. Detecta SKUs con alta frecuencia de reclamaciones
3. Busca clusters por tipo de reclamación, periodo temporal o tipo de daño
4. Identifica problemas emergentes (nuevos tipos de queja no habituales)
5. Ordena los patrones por frecuencia (más frecuente primero)
6. Top SKUs: máximo 10, ordenados por complaint_count descendente"""


async def detect_patterns(
    analyzed_complaints: list[dict],
    project_id: str,
    location: str,
) -> dict:
    client = genai.Client(vertexai=True, project=project_id, location=location)

    aggregated = []
    for c in analyzed_complaints:
        aggregated.append({
            "complaint_id": c.get("complaint_id"),
            "category": c.get("category"),
            "subcategory": c.get("subcategory"),
            "priority": c.get("priority"),
            "product_sku": c.get("product_sku"),
            "product_name": c.get("product_name"),
            "damage_type": c.get("damage_type"),
            "key_excerpt": c.get("key_excerpt"),
            "date": c.get("date", ""),
            "sentiment_score": c.get("sentiment_score"),
        })

    prompt = PATTERN_PROMPT.format(
        count=len(analyzed_complaints),
        aggregated_data=json.dumps(aggregated, ensure_ascii=False, indent=1),
    )

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
        return json.loads(response.text)

    except Exception as e:
        logger.error(f"Pattern detection failed: {e}")
        return {"patterns": [], "top_skus": []}
