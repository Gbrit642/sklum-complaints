"""Generate 55 synthetic Spanish complaint records for Sklum demo.

Uses Gemini 3.5 Flash for complaint text generation.
Images are generated separately via generate_images.py.
Outputs: data/complaints.csv
"""

import json
import csv
import os
from pathlib import Path

from google import genai
from google.genai import types

PROJECT_ID = "agent-460311"
LOCATION = "us-central1"
OUTPUT_DIR = Path(__file__).parent.parent / "data"

GENERATION_PROMPT = """Genera exactamente 55 reclamaciones de clientes ficticias para Sklum, una tienda online de muebles y decoración.

REQUISITOS:
- Todas las reclamaciones deben estar en español
- Los datos de clientes deben estar anonimizados (CLI-A001, CLI-A002, etc.)
- Los números de pedido deben estar hasheados (ORD-XXXX-0001, ORD-XXXX-0002, etc.)
- NO incluir nombres reales, direcciones, ni datos personales

DISTRIBUCIÓN DE PRIORIDADES:
- 6 reclamaciones URGENTES (riesgo de seguridad, impacto financiero alto >500€, riesgo legal)
- 13 reclamaciones SISTÉMICAS (agrupadas en 4 causas raíz):
  - 4 sobre problemas recurrentes con el transportista MRW (paquetes abandonados en la calle)
  - 3 sobre defectos en la serie de estanterías BILLY-SKL (baldas que se comban)
  - 3 sobre embalaje insuficiente en lámparas (llegan rotas)
  - 3 sobre envío de producto equivocado (color o modelo incorrecto)
- 36 reclamaciones RUTINARIAS (defectos menores, retrasos normales, devoluciones estándar)

CATEGORÍAS DE PRODUCTO (usar SKUs realistas):
- Mesas: SKU-MESA-001 a SKU-MESA-010 (Mesa Comedor Roble, Mesa Centro Cristal, Mesa Extensible Nogal, etc.)
- Sillas: SKU-SILLA-001 a SKU-SILLA-010 (Silla Eames Replica, Silla Comedor Tapizada, Taburete Alto, etc.)
- Estanterías: SKU-ESTAN-001 a SKU-ESTAN-008 (Estantería BILLY-SKL, Estantería Modular, Librería Pared, etc.)
- Lámparas: SKU-LAMP-001 a SKU-LAMP-008 (Lámpara Colgante Industrial, Lámpara Pie Arco, Foco LED, etc.)
- Sofás: SKU-SOFA-001 a SKU-SOFA-006 (Sofá 3 Plazas Tela, Sofá Esquinero, Sofá Cama, etc.)
- Muebles Exterior: SKU-EXT-001 a SKU-EXT-006 (Mesa Jardín Teca, Silla Plegable Exterior, etc.)

CAMPO has_image: aproximadamente el 70% de las reclamaciones (38 de 55) deben tener has_image=true.
Las reclamaciones con imagen deben incluir un campo image_description que describa qué se vería en la foto del cliente.

CAMPO date: distribuir las fechas entre 2024-10-01 y 2024-12-15

FORMATO DE SALIDA (JSON array):
[
  {
    "complaint_id": "REC-2024-0001",
    "date": "2024-10-03",
    "customer_id": "CLI-A001",
    "product_sku": "SKU-MESA-042",
    "product_name": "Mesa Comedor Roble 180cm",
    "order_id": "ORD-XXXX-0001",
    "category_hint": "dano_envio",
    "complaint_text": "La mesa llegó con una pata completamente rota. El embalaje estaba aplastado por un lado y se nota que el transportista no tuvo cuidado. Necesito una solución urgente porque tengo una cena familiar este fin de semana.",
    "has_image": true,
    "image_description": "Mesa de comedor de roble con una pata rota, astillada en la base. El embalaje de cartón aplastado visible al fondo."
  },
  ...
]

IMPORTANTE:
- Varía el tono: algunos clientes están muy enfadados, otros son más descriptivos y tranquilos
- Incluye detalles específicos que un cliente real mencionaría (dimensiones, colores, fechas de entrega prometidas)
- Las reclamaciones sistémicas deben tener patrones claros pero no ser copias exactas
- Algunos complaint_text deben ser cortos (1-2 frases) y otros largos (3-5 frases)
- category_hint posibles: defecto_producto, dano_envio, entrega_incorrecta, retraso_entrega, calidad_material, pieza_faltante, error_facturacion, devolucion
"""


def generate_complaints():
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=GENERATION_PROMPT,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.9,
            max_output_tokens=65536,
            thinking_config=types.ThinkingConfig(thinking_budget=8000),
        ),
    )

    complaints = json.loads(response.text)
    print(f"Generated {len(complaints)} complaints")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_DIR / "complaints.json", "w", encoding="utf-8") as f:
        json.dump(complaints, f, ensure_ascii=False, indent=2)

    fieldnames = [
        "complaint_id", "date", "customer_id", "product_sku", "product_name",
        "order_id", "category_hint", "complaint_text", "has_image", "image_path",
    ]
    with open(OUTPUT_DIR / "complaints.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in complaints:
            row = {k: c.get(k, "") for k in fieldnames}
            if c.get("has_image"):
                row["image_path"] = f"images/{c['complaint_id']}.png"
            else:
                row["image_path"] = ""
            row["has_image"] = str(c.get("has_image", False)).lower()
            writer.writerow(row)

    image_descriptions = {
        c["complaint_id"]: c.get("image_description", "")
        for c in complaints if c.get("has_image")
    }
    with open(OUTPUT_DIR / "image_descriptions.json", "w", encoding="utf-8") as f:
        json.dump(image_descriptions, f, ensure_ascii=False, indent=2)

    priority_counts = {"urgente": 0, "sistemico": 0, "rutinario": 0}
    for c in complaints:
        text_lower = c.get("complaint_text", "").lower()
        cid = c.get("complaint_id", "")
        idx = int(cid.split("-")[-1]) if cid else 0
        if idx <= 6:
            priority_counts["urgente"] += 1
        elif idx <= 19:
            priority_counts["sistemico"] += 1
        else:
            priority_counts["rutinario"] += 1

    image_count = sum(1 for c in complaints if c.get("has_image"))
    print(f"Complaints with images: {image_count}/{len(complaints)}")
    print(f"CSV written to: {OUTPUT_DIR / 'complaints.csv'}")
    print(f"Image descriptions written to: {OUTPUT_DIR / 'image_descriptions.json'}")


if __name__ == "__main__":
    generate_complaints()
