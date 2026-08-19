#!/usr/bin/env python3
"""
setup.py  —  PSR Demo one-time asset downloader.

Run ONCE before launching the app:
    python setup.py

What it does
------------
1. Downloads the OHRC Chandrayaan-2 PSR image → assets/psr_source.jpg
"""

import requests
from pathlib import Path

BASE_DIR   = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"

# ── URLs ──────────────────────────────────────────────────────────────────────
OHRC_URL = (
    "https://jatan.space/content/images/2024/02/"
    "https-3a-2f-2fbucketeer-e05bbc84-baa3-437e-9518-adb32be77984-s3-amazonaws"
    "-com-2fpublic-2fimages-2fcfc7737f-7e82-46be-a634-8679f6423598_961x324-jpeg.jpg"
)


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _download(url: str, dest: Path, label: str) -> bool:
    print(f"  >> Downloading {label} ...")
    try:
        resp = requests.get(
            url, stream=True, timeout=60,
            headers={"User-Agent": "PSR-SIH1732-Setup/1.0"},
        )
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=16_384):
                if chunk:
                    fh.write(chunk)
        size_kb = dest.stat().st_size / 1024
        print(f"     [OK] Saved to {dest}  ({size_kb:.1f} KB)")
        return True
    except Exception as exc:
        print(f"     [FAIL] {exc}")
        if dest.exists():
            dest.unlink()
        return False


# ── MAIN ─────────────────────────────────────────────────────────────────────

def setup():
    print("\n" + "=" * 48)
    print("  PSR Enhancement Demo -- Asset Setup")
    print("  SIH 1732 * Chandrayaan-2 OHRC Pipeline")
    print("=" * 48 + "\n")

    # 1. OHRC image ────────────────────────────────────────────────────────────
    img_path = ASSETS_DIR / "psr_source.jpg"
    print("-- Downloading OHRC PSR Image --")
    if img_path.exists():
        print(f"  [OK] Already cached at {img_path}")
    else:
        ok = _download(OHRC_URL, img_path, "OHRC Chandrayaan-2 PSR image (ISRO)")
        if not ok:
            print("  [WARN] Image download failed.")
            print("     The app will prompt you to upload an image manually.")

    # 2. Done ─────────────────────────────────────────────────────────────────
    print("\n" + "=" * 48)
    print("  Setup complete!  Launch the demo with:")
    print("      python -m uvicorn server:app --reload")
    print("=" * 48 + "\n")


if __name__ == "__main__":
    setup()

