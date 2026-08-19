# 🛰️ PSR Enhancement Analyzer (SIH 1732)

An automated, multi-algorithm denoising and analysis pipeline for Chandrayaan-2 OHRC (Orbiter High Resolution Camera) images of Permanently Shadowed Regions (PSRs) on the Lunar South Pole.

## Overview
This project solves the challenge of extracting usable geological features (boulders, micro-craters, reflectance patterns) from extremely dark and noisy PSR imagery. It provides an automated pipeline that:
1. **Preprocesses** images (Smart Crop, Bad Pixel Correction, adaptive CLAHE).
2. **Denoises** using three competing algorithms (NLM, BM3D, Wavelet).
3. **Scores & Auto-selects** the optimal result based on blind image quality metrics weighted for lunar science (EdgePI, CNR, SNR, Entropy).
4. **Visualizes** the result with a Relative Illumination Map (INFERNO colormap).
5. Provides an interactive, zoomable UI for **Final Comparison** between raw and processed images.

## Features
- **Robust Image Decoding**: Supports JPG, PNG, TIFF, and 16-bit images.
- **Blind Quality Metrics**: Evaluates performance without requiring a "clean" ground truth reference.
- **Interactive Web UI**: Built with HTML/CSS/JS (no heavy framework), featuring drag-and-drop upload, parameter tuning, and synchronized zoom/pan image comparison.
- **FastAPI Backend**: Efficient, async Python backend.

## Quick Start
1. Ensure you have Python 3.11+ installed.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python -m uvicorn server:app --reload
   ```
4. Open your browser and navigate to `http://localhost:8000`.

## Contributors
- [@chetanthakre-pixel](https://github.com/chetanthakre-pixel)
- [@ANAS-10261](https://github.com/ANAS-10261)
- [@Gaurang0510](https://github.com/Gaurang0510)

---
*Developed for Smart India Hackathon (SIH) 1732*