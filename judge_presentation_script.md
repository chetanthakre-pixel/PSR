# 🛰️ SIH 1732 — PSR Enhancement Analyzer
## Judge Presentation Script & Technical Explanation

---

## 1. Problem Statement (What Are We Solving?)

- **Chandrayaan-2's OHRC** (Orbiter High Resolution Camera) captures images of the Lunar South Pole at ~30cm/pixel resolution.
- **Permanently Shadowed Regions (PSRs)** are craters that never receive direct sunlight — potential sites for water ice.
- These PSR images are **extremely dark and noisy** — barely any visible detail to the naked eye.
- **Challenge**: ISRO scientists need to extract geological features (boulders, micro-craters, reflectance patterns) from these near-black images, but conventional brightness/contrast adjustments just amplify noise.
- **Our Goal**: Build an automated, benchmarked denoising pipeline that determines the **optimal algorithm** for each image and produces a clean, analyzable output.

---

## 2. Technical Architecture (How Does It Work?)

```
┌──────────────────────────────────────────────────────────┐
│                    USER (Browser UI)                     │
│  Upload Image → Set CLAHE Params → Click EXECUTE         │
└────────────────────────┬─────────────────────────────────┘
                         │  HTTP POST /run-pipeline
                         ▼
┌──────────────────────────────────────────────────────────┐
│                 FastAPI Backend (Python)                  │
│                                                          │
│  ┌─── Stage 1: PREPROCESSING ─────────────────────────┐  │
│  │  1. Image Decoding (JPG/PNG/TIFF/16-bit → BGR)     │  │
│  │  2. Smart Panel Cropping (dual-panel auto-detect)  │  │
│  │  3. Grayscale Conversion → Float32 [0,1]           │  │
│  │  4. Bad Pixel Correction (4σ median filter)        │  │
│  │  5. CLAHE Enhancement (tile-based adaptive)        │  │
│  └────────────────────────────────────────────────────┘  │
│                         │                                │
│  ┌─── Stage 2: MULTI-ALGORITHM DENOISING ─────────────┐  │
│  │  Run 3 algorithms IN PARALLEL on CLAHE output:     │  │
│  │    ✦ NLM  (Non-Local Means)                        │  │
│  │    ✦ BM3D (Block-Matching 3D)                      │  │
│  │    ✦ Wavelet (Daubechies db4, VisuShrink)          │  │
│  └────────────────────────────────────────────────────┘  │
│                         │                                │
│  ┌─── Stage 3: METRICS + SCORING ─────────────────────┐  │
│  │  Compute 4 quality metrics per denoised output     │  │
│  │  Normalize → Weighted Composite Score → Rank       │  │
│  │  Best method declared automatically                │  │
│  └────────────────────────────────────────────────────┘  │
│                         │                                │
│  ┌─── Stage 4: VISUALIZATION ─────────────────────────┐  │
│  │  Generate Relative Illumination Map (INFERNO)      │  │
│  │  on the best denoised output                       │  │
│  └────────────────────────────────────────────────────┘  │
│                         │                                │
│                    JSON Response                         │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│                    Browser Frontend                       │
│  ✦ Denoising Pipeline Tab   — all 3 results + metrics   │
│  ✦ Illumination Map Tab     — false-color visualization │
│  ✦ Final Compare Tab        — zoomable raw vs. output   │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Preprocessing Pipeline (Stage 1) — Point by Point

| Step | What It Does | Why It Matters |
|------|-------------|----------------|
| **Image Decoding** | Accepts JPG, PNG, TIFF, 16-bit, RGBA — converts all to standard BGR uint8 | OHRC data comes in various formats; we handle them all robustly |
| **Smart Panel Cropping** | Detects if image is a side-by-side comparison (aspect ratio > 1.7) and auto-crops the PSR (right) panel | ISRO comparison images have lit + dark panels — we isolate the PSR region |
| **Normalization** | Scales pixel values to float32 [0.0, 1.0] range | Standardizes input for all algorithms regardless of original bit-depth |
| **Bad Pixel Correction** | Identifies outlier pixels (> 4σ from local 3×3 median) and replaces them | Camera sensor hot/dead pixels would bias denoising results |
| **CLAHE** | Contrast Limited Adaptive Histogram Equalization (tile-based) | Reveals hidden detail in extremely dark PSR regions without over-amplifying noise in bright areas |

> **User-configurable**: Clip Limit (1.0–8.0) and Tile Grid Size (4×4 to 16×16) can be tuned from the UI.

---

## 4. The Three Denoising Algorithms (Stage 2) — What Each Does

### ✦ NLM (Non-Local Means)
- **How**: Searches the *entire image* for patches that look similar to the current patch, then averages them.
- **Strength**: Excellent at preserving texture and repeated patterns (crater walls, regolith).
- **Weakness**: Slower on large images; can over-smooth unique features.
- **Noise sigma**: Auto-estimated using `skimage.restoration.estimate_sigma`.

### ✦ BM3D (Block-Matching 3D)
- **How**: Groups similar 2D image patches into 3D stacks → applies collaborative Wiener filtering in the transform domain → aggregates back.
- **Strength**: State-of-the-art for Gaussian noise removal; preserves fine edges extremely well.
- **Weakness**: Computationally heavy; assumes Gaussian noise model.
- **Why it often wins for PSR**: PSR noise is largely Gaussian (photon shot + read noise) — BM3D's transform-domain filtering is ideal.

### ✦ Wavelet (Daubechies db4, VisuShrink)
- **How**: Decomposes the image into multi-scale frequency sub-bands using Discrete Wavelet Transform → soft-thresholds small (noisy) coefficients → reconstructs.
- **Strength**: Very fast; good at removing spatially uniform noise.
- **Weakness**: Can introduce ringing artifacts near sharp edges.

---

## 5. How the Best Algorithm Is Determined (Stage 3) — The Scoring System

### 5a. Four Quality Metrics Computed

| Metric | Formula / Method | What It Measures |
|--------|-----------------|------------------|
| **EdgePI** (Edge Preservation Index) | Pearson correlation between Sobel edge maps of original and denoised image | How well edges (crater rims, boulder outlines) are preserved. 1.0 = perfect. |
| **CNR** (Contrast-to-Noise Ratio) | `(mean_bright_30% − mean_dark_30%) / std_dark_30%` | How much the signal (bright features) stands out from background noise |
| **SNR** (Signal-to-Noise Ratio) | `mean(image) / std(image)` | Overall signal quality — higher = cleaner image |
| **Entropy** (Shannon Entropy) | `-Σ p·log₂(p)` over 256-bin histogram | Information richness — higher = more detail retained, not over-smoothed |

### 5b. Normalization

Each metric is min-max normalized to [0, 1] using empirically calibrated ranges for lunar PSR imagery:

| Metric | Min | Max |
|--------|-----|-----|
| SNR | 0.0 | 25.0 |
| CNR | 0.0 | 12.0 |
| EdgePI | -1.0 | 1.0 |
| Entropy | 0.0 | 5.6 |

### 5c. Weighted Composite Score

```
Final Score = 0.35 × EdgePI_norm
            + 0.30 × CNR_norm
            + 0.20 × SNR_norm
            + 0.15 × Entropy_norm
```

> **Why these weights?**
> - **EdgePI has the highest weight (35%)** because for PSR science, preserving crater rim edges and boulder outlines is the most critical requirement.
> - **CNR is second (30%)** because scientists need to distinguish faint geological features from background shadow.
> - **SNR (20%)** gives an overall cleanliness assessment.
> - **Entropy (15%)** penalizes over-smoothing — ensures the algorithm doesn't destroy information to get a "clean" image.

### 5d. Winner Selection

- All three algorithms are scored → sorted highest to lowest.
- The top-scoring method is declared the **Optimal Algorithm**.
- This is fully **automatic and objective** — no human bias in selection.

---

## 6. Relative Illumination Map (Stage 4)

- Takes the **best denoised grayscale output** and applies OpenCV's `COLORMAP_INFERNO` (perceptually uniform).
- Maps faint secondary illumination and subtle reflectance gradients across dark crater terrain.
- **Black/Purple** → deepest shadow / lowest albedo regions.
- **Yellow/White** → reflective crests / rim highlights / possible ice signatures.
- Helps geologists **visually identify** terrain variation that is invisible in grayscale.

> **Note to judges**: This is a visualization aid for geological interpretation. True 3D elevation modeling would require stereo DEM imagery or shape-from-shading analysis.

---

## 7. Final Compare View — Zoomable Inspection

- **Side-by-side**: Raw PSR input vs. Optimal Denoised Output.
- **Synchronized zoom**: Scroll-to-zoom on either panel zooms both — so you can inspect the **exact same region** in raw and cleaned versions.
- **Drag-to-pan**: Click and drag to navigate.
- **Zoom range**: 50% to 1000%.
- **Purpose**: Lets scientists verify edge preservation and noise removal at pixel-level detail.

---

## 8. The Complete Result We Deliver

| Output | Description |
|--------|------------|
| **3 Preprocessing Stages** | Raw crop → Normalized → CLAHE enhanced (visible in UI) |
| **3 Denoised Outputs** | NLM, BM3D, Wavelet — each with full metric scorecard |
| **Auto-Selected Winner** | Objectively scored best algorithm with reason |
| **Illumination Map** | False-color INFERNO visualization of the best output |
| **Zoomable Comparison** | Raw vs. Best output at up to 10× zoom |
| **Downloadable Files** | One-click download for cleaned image, grayscale, and illumination map |

---

## 9. Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11, FastAPI, Uvicorn (async ASGI server) |
| **Image Processing** | OpenCV, NumPy, SciPy, scikit-image |
| **Denoising** | scikit-image (NLM, Wavelet), bm3d package (BM3D) |
| **Frontend** | Vanilla HTML5, CSS3, JavaScript (no framework dependency) |
| **Deployment** | Single `python -m uvicorn server:app` command, zero external services |

---

## 10. Key Technical Differentiators (What Makes This Special)

1. **No Ground Truth Needed** — Unlike PSNR/SSIM-based approaches, our scoring system works on *real* PSR images where no clean reference exists. We use blind quality metrics (EdgePI, CNR, SNR, Entropy).

2. **Fully Automated Selection** — No manual parameter tuning or subjective visual comparison. The weighted score objectively picks the best algorithm.

3. **Multi-Format Robustness** — Handles TIFF, 16-bit, RGBA, grayscale, JPG, PNG. Automatically detects and handles dual-panel OHRC comparison images.

4. **Real-Time Interactive UI** — Not a CLI tool or Jupyter notebook. Scientists get a polished web dashboard with drag-and-drop upload, parameter sliders, and interactive zoom.

5. **Scientifically Calibrated Weights** — Metric normalization ranges and weights are empirically tuned for lunar PSR imagery characteristics, not generic photo denoising benchmarks.

---

## 11. Future Scope

### Short-Term (Next 3–6 Months)
1. **Deep Learning Denoisers** — Integrate DnCNN, NAFNet, or Restormer (pre-trained on synthetic PSR noise) as a 4th algorithm to benchmark against classical methods.
2. **Batch Processing** — Process entire OHRC orbit strips (hundreds of frames) in one go with CSV report export.
3. **Ground Truth Validation Module** — When a clean reference is available (lit region), compute PSNR/SSIM alongside blind metrics for validation.
4. **User Preset Profiles** — Save and load CLAHE + algorithm config profiles tuned for different crater types (deep PSR, partial shadow, etc.).

### Medium-Term (6–12 Months)
5. **Shape-from-Shading Integration** — Use faint secondary illumination in denoised PSR images to generate approximate 3D terrain models of crater floors.
6. **Multi-Spectral Support** — Extend pipeline to handle IIRS (Imaging IR Spectrometer) data for mineral/ice spectral analysis.
7. **Anomaly Detection** — Flag unusually bright spots in PSR images as potential volatile deposit (ice) candidates using statistical outlier analysis.
8. **Cloud Deployment** — Containerized (Docker) deployment on ISRO's PRADAN/IADS infrastructure for remote access by multiple research teams.

### Long-Term (1–2 Years)
9. **Transfer Learning for PSR Segmentation** — Train a U-Net/SAM model to automatically segment geological features (boulders, cracks, smooth deposits) in denoised PSR imagery.
10. **Chandrayaan-3 / Chandrayaan-4 Support** — Extend to upcoming mission data (different cameras, resolutions, noise characteristics).
11. **Collaborative Annotation Platform** — Allow ISRO geologists to annotate features on denoised images, building a labeled PSR geological dataset for the community.

---

## 12. Quick Demo Script (2-Minute Walkthrough for Judges)

> Use these exact steps during the demo:

1. **Open** the app at `http://localhost:8000`
2. **Point out** the sticky nav bar with 3 tabs: *Denoising Pipeline*, *Illumination Map*, *Final Compare*
3. **Select** `psr_source.jpg` from the dropdown (or drag-drop your own OHRC image)
4. **Adjust** CLAHE Clip Limit slider to `3.0` and Tile Grid to `8×8`
5. **Click** ⚡ EXECUTE PIPELINE — show the loading spinner
6. **Stage 1 results appear**: Point out Raw → Normalized → CLAHE images. "You can see how CLAHE reveals hidden detail in the shadows."
7. **Winner Banner**: "The system automatically determined **[BM3D/NLM/Wavelet]** as optimal with a score of X.XXXX"
8. **Stage 2 cards**: "Each algorithm card shows the denoised output — hover to compare with pre-denoised CLAHE. Below each are 5 quality metrics."
9. **Switch to Illumination Map tab**: "This false-color INFERNO map shows reflectance gradients invisible in grayscale. Purple = deep shadow, yellow = bright rim highlights."
10. **Switch to Final Compare tab**: "Here you can zoom in to pixel level — scroll to zoom, drag to pan — and compare the raw input with the cleaned output side by side, both zoom together."
11. **Download**: Click download buttons to show export functionality.

---

> [!TIP]
> **One-liner for judges**: "We take a near-black Chandrayaan-2 PSR image, run it through preprocessing + three competing denoising algorithms, objectively score each using blind image quality metrics weighted for lunar science, auto-select the winner, and visualize the result as an interactive illumination map — all in a single click."
