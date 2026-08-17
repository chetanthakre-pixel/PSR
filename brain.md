# 🧠 brain.md — PSR Enhancement Analyzer (SIH 1732)
> **Purpose**: This file is a comprehensive context document for any AI model
> (or developer) picking up this project mid-way. Read this first — it
> replaces the need to read every file from scratch.

---

## 1. What This Project Is

A **fully-offline Streamlit web app** for the Smart India Hackathon (SIH 1732).
It takes a real OHRC (Optical High Resolution Camera) image of a lunar
Permanently Shadowed Region (PSR) from **Chandrayaan-2**, enhances it using
three classical denoising algorithms, benchmarks them with real image-quality
metrics, and automatically declares the best method.

**Scientific goal**: PSRs never receive direct sunlight → extreme noise in
images → must enhance to detect water-ice deposits and geological features.

---

## 2. File Map

```
PSR/
├── app.py                     ← Main Streamlit app (launch this)
├── setup.py                   ← Download assets once before first run
├── requirements.txt           ← Core pip deps
├── optional_requirements.txt  ← PyTorch (optional, for DL baseline)
├── brain.md                   ← YOU ARE HERE
│
├── pipeline/
│   ├── preprocess.py          ← normalize, bad-pixel fix, CLAHE, smart crop
│   ├── denoise.py             ← NLM, BM3D, Wavelet denoisers + runner
│   ├── metrics.py             ← SNR, CNR, EdgePI, Entropy, PSNR, SSIM + scoring
│   ├── dl_baseline.py         ← Zero-DCE inference wrapper (graceful fallback)
├── assets/
│   └── psr_source.jpg         ← Downloaded by setup.py (not in repo)
├── weights/
│   └── zero_dce.pth           ← Downloaded by setup.py (not in repo)
└── .streamlit/
    └── config.toml            ← Dark mission-control theme base
```

---

## 3. How to Run

```bash
# Step 1: Install deps
pip install -r requirements.txt
pip install -r optional_requirements.txt   # optional, for DL column

# Step 2: Download assets (internet required ONCE)
python setup.py

# Step 3: Launch (fully offline after this)
streamlit run app.py
```

App runs at `http://localhost:8501`. After step 2, it works with WiFi off.

---

## 4. Pipeline Architecture

```
Source image (OHRC 961×324 comparison image)
    │
    ├── crop_psr_panel()     → right half (the dark PSR crater floor)
    │   crop_reference_panel() → left half (lit reference, for validation only)
    │
    ▼
normalize_image() + bad_pixel_correction()
    │
    ▼
apply_clahe(clip=3.0, tile=8×8)   ← CLAHE enhances faint structure before denoising
    │
    ├─── denoise_nlm()       → Non-Local Means (scikit-image, fast_mode)
    ├─── denoise_bm3d()      → BM3D (bm3d pip package, ALL_STAGES)
    ├─── denoise_wavelet_fn() → Wavelet (db4, VisuShrink, soft threshold)
    └─── run_zero_dce()      → DL baseline (Zero-DCE pretrained, optional)
    │
    ▼
compute_all_metrics()  for each output:
    SNR, CNR, EdgePI, Entropy
    PSNR/SSIM only if ground truth exists (synthetic validation mode)
    │
    ▼
rank_methods() + compute_weighted_score()
    │
    ▼
Winner declared + RELATIVE ILLUMINATION MAP (bonus tab on winner output)
```

---

## 5. Metrics Reference

| Metric   | Formula / Method                            | Weight | Range       |
|----------|---------------------------------------------|--------|-------------|
| **EdgePI** | Pearson corr of Sobel edge maps (input vs denoised) | **0.35** | [-1, 1] |
| **CNR**    | (mean_top30% − mean_bot30%) / std_bot30%   | **0.30** | [0, ∞)  |
| **SNR**    | mean(img) / std(img)                        | 0.20   | [0, ∞)  |
| **Entropy**| Shannon entropy of 256-bin histogram (bits) | 0.15   | [0, ~5.6]|
| PSNR     | 10·log₁₀(1/MSE) vs ground truth             | —      | dB        |
| SSIM     | scikit-image structural_similarity           | —      | [0, 1]  |

> EdgePI + CNR weighted highest: edge preservation and contrast matter most
> for crater/boulder interpretability in PSR science.

**Normalisation for scoring** (min, max → clipped):
- SNR → [0, 25], CNR → [0, 12], EdgePI → [-1, 1], Entropy → [0, 5.6]

---

## 6. The Three Denoisers

### NLM — Non-Local Means
- `skimage.restoration.denoise_nl_means`
- Searches image-wide for similar patches → averages out noise
- Params: patch_size=5, patch_distance=6, h=1.15×σ_est (auto-estimated)
- Strength: excellent texture preservation; Weakness: slow on large images

### BM3D — Block-Matching 3D
- `bm3d` pip package, `BM3DStages.ALL_STAGES`
- Groups similar 2D patches into 3D stacks, collaborative filtering + IDWT
- σ auto-estimated from image
- Strength: state-of-the-art classical denoising; Weakness: ~30s on CPU

### Wavelet — db4 VisuShrink
- `skimage.restoration.denoise_wavelet`
- Decomposes into db4 sub-bands, soft-thresholds small coefficients
- Params: levels=4, mode='soft', rescale_sigma=True
- Strength: very fast; Weakness: may lose fine detail at high noise levels

---

## 7. DL Baseline (Zero-DCE)

- Architecture: DCE-Net (7 Conv layers, skip connections, 24-ch tanh output)
- Layer names: `e_conv1` … `e_conv7` (matches official pretrained checkpoint)
- Weights: `weights/zero_dce.pth` (downloaded by setup.py from GitHub)
- Input: 3-channel float32 tensor; applies 8 iterative curve adjustments
- **Fully optional** — if PyTorch missing or weights absent, app shows
  "DL baseline unavailable" and everything else works perfectly
- Labelled "DL baseline (pretrained, inference-only)" in the UI — not
  trained on OHRC/PSR data, so judges understand the distinction

---

## 8. Synthetic Validation

- Uses the **left panel** (lit reference region) of the same OHRC image
- Darkening: `img^3.0 × 0.15` (simulates shadow photon starvation)
- Poisson noise: `np.random.poisson(img × 80) / 80` (shot noise)
- Gaussian noise: σ=0.05 (thermal/read noise)
- Ground truth is known → PSNR and SSIM are valid here
- **PSNR/SSIM are shown ONLY in this tab** — never on real PSR imagery

---

## 9. Bonus Feature — Relative Illumination Map (Tab 3)

**Visual interpretation**: A perceptually uniform colormap (Inferno) applied to the winning classical denoised output. Maps darker pixels to cool colors and brighter pixels to warm colors.

**Implementation**:
1. Takes the best denoised output image
2. Applies `cv2.COLORMAP_INFERNO`
3. Displays side-by-side with grayscale version

**Disclaimer always shown**: "Color-coded brightness for visual interpretation — not a measured elevation model. True depth would require stereo imagery (DEM) or shape-from-shading analysis, noted as future scope."

---

## 10. UI / UX Decisions

- **Theme**: Dark mission-control (#060a14 bg, #00d4ff cyan accent, #00ff88 winner)
- **CSS**: Injected via `st.markdown(CUSTOM_CSS, unsafe_allow_html=True)`
- **Caching**: `@st.cache_data` on pipeline functions; image passed as bytes
  (numpy arrays aren't directly hashable in Streamlit cache keys)
- **Session state**: Results stored in `st.session_state` so switching tabs
  doesn't re-run the full pipeline
- **ISRO credit**: Visible in header at all times — not hidden
- **Offline**: All assets bundled after `setup.py`. No CDN fonts or API calls.

---

## 11. Known Gotchas

1. **BM3D install on Windows**: `pip install bm3d` works on Python 3.9+.
   If it fails, the BM3D column shows the CLAHE output as fallback + error badge.

2. **Zero-DCE weights URL**: GitHub raw binary download. If the URL breaks,
   add a mirror to `ZERO_DCE_URLS` list in `setup.py`.

3. **OHRC image crop**: Uses `_find_vertical_split()` to auto-detect the
   separator. If the image layout changes (e.g. different OHRC comparison),
   it falls back to cropping the right 50%.

4. **Image size**: The default OHRC image is 961×324 px. After cropping the
   PSR panel it's ~480×324 px. NLM takes ~15-30s on CPU at this size.

5. **Matplotlib `Agg` backend**: Set explicitly at import in both `app.py`
   and `feature_detector.py` to avoid tkinter conflicts in Streamlit.

6. **`st.cache_data` hash**: Images passed as `.tobytes()` bytes for reliable
   hashing. Changing CLAHE params invalidates the cache correctly.

---

## 12. What Still Needs Doing (if incomplete)

- [ ] Verify `run_zero_dce()` loads correctly after `setup.py` succeeds
- [ ] Test BM3D on Windows without CUDA
- [ ] Add "Export PDF Report" button (nice-to-have for judges)
- [ ] Add error handling if OHRC image crop produces very small image (<50px wide)

---

## 13. Quick Command Reference

```bash
python setup.py              # Download assets (run once)
streamlit run app.py         # Launch demo

pip install -r requirements.txt
pip install -r optional_requirements.txt

# Test pipeline without UI
python -c "
from pipeline.preprocess import *
from pipeline.denoise import *
from pipeline.metrics import *
import cv2, numpy as np
img = cv2.imread('assets/psr_source.jpg')
_, norm, clahe = preprocess_pipeline(img)
res = run_all_denoisers(clahe)
for k,v in res.items():
    m = compute_all_metrics(norm, v['image'])
    print(k, compute_weighted_score(m))
"
```

---

*Last updated: 2026-08-16 · SIH 1732 · OHRC PSR Enhancement Demo*
