import os
import zipfile
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
PRADAN_DIR = BASE_DIR / "pradan.issdc.gov.in"

if not ASSETS_DIR.exists():
    ASSETS_DIR.mkdir(parents=True)

def extract_images():
    if not PRADAN_DIR.exists():
        print("PRADAN directory not found. Did the download finish?")
        return

    extracted_count = 0
    for root, dirs, files in os.walk(PRADAN_DIR):
        for file in files:
            if file.endswith(".zip"):
                zip_path = Path(root) / file
                print(f"Extracting {zip_path.name}...")
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    for zip_info in zf.infolist():
                        if zip_info.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff')):
                            # We want to extract it directly into assets/, avoiding nested directories
                            source = zf.open(zip_info)
                            # Create a target path
                            target_path = ASSETS_DIR / Path(zip_info.filename).name
                            with open(target_path, "wb") as target:
                                shutil.copyfileobj(source, target)
                            print(f"  Extracted {target_path.name}")
                            extracted_count += 1
                            if extracted_count >= 5:
                                print("Done. Extracted 5 images to assets/.")
                                return
    print(f"Done. Extracted {extracted_count} images to assets/.")

if __name__ == "__main__":
    extract_images()
