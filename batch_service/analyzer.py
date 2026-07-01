"""Per-complaint analysis using Gemini 3.5 Flash."""

import asyncio
import json
import logging

from google import genai
from google.genai import types

logger = logging.getLogger("sklum-batch")

ANALYSIS_PROMPT = """Analiza esta reclamación de cliente de Sklum (tienda online de muebles y decoración).

Texto de la reclamación:
{complaint_text}

Información adicional:
- ID: {complaint_id}
- Producto: {product_name} (SKU: {product_sku})
- Fecha: {date}
- Categoría sugerida: {category_hint}

{image_instruction}

Responde SOLO con un JSON válido con estos campos exactos:
{{
  "category": "una de: defecto_producto, dano_envio, entrega_incorrecta, retraso_entrega, calidad_material, pieza_faltante, error_facturacion, devolucion",
  "subcategory": "subcategoría específica del problema",
  "priority": "una de: urgente, sistemico, rutinario",
  "priority_reasoning": "justificación breve de la prioridad asignada",
  "sentiment_score": -1.0 a 1.0 (negativo a positivo),
  "damage_type": "una de: embalaje, componente_producto, etiquetado, superficie, estructural, sin_dano_visible (o null si no hay imagen)",
  "image_analysis_summary": "descripción del daño visible en la imagen (o null si no hay imagen)",
  "key_excerpt": "la frase más relevante de la reclamación",
  "suggested_action": "acción recomendada para resolver esta reclamación"
}}"""


class ComplaintAnalyzer:
    def __init__(self, project_id: str, location: str):
        self.client = genai.Client(
            vertexai=True, project=project_id, location=location
        )
        self.semaphore = asyncio.Semaphore(10)

    async def analyze_single(
        self,
        complaint: dict,
        image_data: bytes | None = None,
    ) -> dict:
        async with self.semaphore:
            return await self._call_gemini(complaint, image_data)

    async def _call_gemini(
        self,
        complaint: dict,
        image_data: bytes | None = None,
    ) -> dict:
        complaint_id = complaint.get("complaint_id", "unknown")

        if image_data:
            image_instruction = "Se adjunta una imagen del producto/daño. Analiza la imagen para determinar el tipo y severidad del daño."
        else:
            image_instruction = "No se proporcionó imagen para esta reclamación."

        prompt_text = ANALYSIS_PROMPT.format(
            complaint_text=complaint.get("complaint_text", ""),
            complaint_id=complaint_id,
            product_name=complaint.get("product_name", "N/A"),
            product_sku=complaint.get("product_sku", "N/A"),
            date=complaint.get("date", "N/A"),
            category_hint=complaint.get("category_hint", "N/A"),
            image_instruction=image_instruction,
        )

        contents = []
        if image_data:
            contents.append(
                types.Part.from_bytes(data=image_data, mime_type="image/png")
            )
        contents.append(prompt_text)

        try:
            response = await self.client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )

            analysis = json.loads(response.text)

            analysis["complaint_id"] = complaint_id
            analysis["original_text"] = complaint.get("complaint_text", "")
            analysis["has_image"] = image_data is not None
            analysis["product_sku"] = complaint.get("product_sku")
            analysis["product_name"] = complaint.get("product_name")

            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze {complaint_id}: {e}")
            return {
                "complaint_id": complaint_id,
                "original_text": complaint.get("complaint_text", ""),
                "category": complaint.get("category_hint", "desconocido"),
                "subcategory": "error_analisis",
                "priority": "rutinario",
                "priority_reasoning": f"Error en análisis automático: {str(e)[:100]}",
                "sentiment_score": 0.0,
                "damage_type": None,
                "image_analysis_summary": None,
                "has_image": image_data is not None,
                "key_excerpt": complaint.get("complaint_text", "")[:100],
                "suggested_action": "Revisar manualmente",
                "product_sku": complaint.get("product_sku"),
                "product_name": complaint.get("product_name"),
            }

    async def analyze_batch(
        self,
        complaints: list[dict],
        images: dict[str, bytes],
    ) -> list[dict]:
        tasks = []
        for complaint in complaints:
            cid = complaint.get("complaint_id", "")
            image_data = images.get(cid)
            tasks.append(self.analyze_single(complaint, image_data))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        analyzed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception analyzing complaint {i}: {result}")
                analyzed.append({
                    "complaint_id": complaints[i].get("complaint_id", f"unknown-{i}"),
                    "original_text": complaints[i].get("complaint_text", ""),
                    "category": "desconocido",
                    "subcategory": "error",
                    "priority": "rutinario",
                    "priority_reasoning": f"Error: {str(result)[:100]}",
                    "sentiment_score": 0.0,
                    "has_image": False,
                    "key_excerpt": "",
                    "suggested_action": "Revisar manualmente",
                })
            else:
                analyzed.append(result)

        return analyzed
