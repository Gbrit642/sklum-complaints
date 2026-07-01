"""Generate synthetic product damage images using Gemini image generation.

Reads image_descriptions.json produced by generate_data.py and generates
one image per complaint that has has_image=true.

Uses Gemini's image generation capability (Imagen via Gemini).
"""

import json
import os
import time
from pathlib import Path

from google import genai
from google.genai import types

PROJECT_ID = "agent-460311"
LOCATION = "us-central1"
DATA_DIR = Path(__file__).parent.parent / "data"
IMAGES_DIR = DATA_DIR / "images"


def generate_images():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATA_DIR / "image_descriptions.json", "r", encoding="utf-8") as f:
        descriptions = json.load(f)

    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

    total = len(descriptions)
    generated = 0
    failed = 0

    for i, (complaint_id, description) in enumerate(descriptions.items()):
        output_path = IMAGES_DIR / f"{complaint_id}.png"
        if output_path.exists():
            print(f"[{i+1}/{total}] Skipping {complaint_id} (already exists)")
            generated += 1
            continue

        prompt = (
            f"Generate a realistic photo of a damaged furniture product as would be "
            f"taken by a customer filing a complaint. {description} "
            f"The photo should look like it was taken with a smartphone camera, "
            f"slightly unfocused, indoor lighting, casual angle. "
            f"No text overlays, no watermarks, no people visible."
        )

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )

            image_saved = False
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                        with open(output_path, "wb") as img_file:
                            img_file.write(part.inline_data.data)
                        image_saved = True
                        break

            if image_saved:
                generated += 1
                print(f"[{i+1}/{total}] Generated {complaint_id}")
            else:
                failed += 1
                print(f"[{i+1}/{total}] No image in response for {complaint_id}")

        except Exception as e:
            failed += 1
            print(f"[{i+1}/{total}] Failed {complaint_id}: {e}")

        time.sleep(2)

    print(f"\nDone: {generated} generated, {failed} failed out of {total}")


if __name__ == "__main__":
    generate_images()
