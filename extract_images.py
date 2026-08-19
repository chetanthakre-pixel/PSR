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
    """Extract browse images (.png) from all downloaded OHRC zip files."""
    if not PRADAN_DIR.exists():
        print("PRADAN directory not found. Did the download finish?")
        return

    extracted_count = 0
    skipped_count = 0

    for root, dirs, files in os.walk(PRADAN_DIR):
        for file in sorted(files):
            if file.endswith(".zip"):
                zip_path = Path(root) / file
                print(f"\nProcessing: {zip_path.name}")

                try:
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        # List all contents for diagnostic purposes
                        contents = zf.namelist()
                        print(f"  Contains {len(contents)} files:")
                        for entry in contents:
                            info = zf.getinfo(entry)
                            size_kb = info.file_size / 1024
                            print(f"    {entry}  ({size_kb:.1f} KB)")

                        # Extract browse images (PNG) and any TIFF/IMG data files
                        for zip_info in zf.infolist():
                            fname_lower = zip_info.filename.lower()
                            if fname_lower.endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.xml', '.img')):
                                target_name = Path(zip_info.filename).name
                                target_path = ASSETS_DIR / target_name

                                if target_path.exists():
                                    print(f"  [SKIP] {target_name} (already exists)")
                                    skipped_count += 1
                                    continue

                                source = zf.open(zip_info)
                                with open(target_path, "wb") as target:
                                    shutil.copyfileobj(source, target)
                                size_kb = target_path.stat().st_size / 1024
                                print(f"  [OK] Extracted {target_name} ({size_kb:.1f} KB)")
                                extracted_count += 1

                except zipfile.BadZipFile:
                    print(f"  [ERROR] Bad zip file: {zip_path.name}")
                except Exception as e:
                    print(f"  [ERROR] {e}")

    print(f"\n{'='*50}")
    print(f"Extraction complete.")
    print(f"  New images extracted : {extracted_count}")
    print(f"  Already existing     : {skipped_count}")
    print(f"  Assets directory     : {ASSETS_DIR}")
    print(f"{'='*50}")

if __name__ == "__main__":
    extract_images()
