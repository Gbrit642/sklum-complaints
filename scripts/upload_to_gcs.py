"""Upload generated complaint data and images to GCS."""

import subprocess
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
GCS_BUCKET = "gs://sklum-complaints-agent-460311"
GCS_DEST = f"{GCS_BUCKET}/datasets/current"


def upload():
    csv_path = DATA_DIR / "complaints.csv"
    if not csv_path.exists():
        print("Error: complaints.csv not found. Run generate_data.py first.")
        return

    print(f"Uploading {csv_path} to {GCS_DEST}/")
    subprocess.run(
        ["gsutil", "cp", str(csv_path), f"{GCS_DEST}/complaints.csv"],
        check=True,
    )

    images_dir = DATA_DIR / "images"
    if images_dir.exists() and any(images_dir.iterdir()):
        image_count = len(list(images_dir.glob("*.png")))
        print(f"Uploading {image_count} images to {GCS_DEST}/images/")
        subprocess.run(
            ["gsutil", "-m", "cp", str(images_dir / "*.png"), f"{GCS_DEST}/images/"],
            check=True,
        )
    else:
        print("Warning: No images found in data/images/. Run generate_images.py first.")

    print("\nVerifying upload...")
    subprocess.run(["gsutil", "ls", f"{GCS_DEST}/"], check=True)
    print("\nUpload complete.")


if __name__ == "__main__":
    upload()
