# Pipeline Explainer — PSR Enhancement Analyzer (SIH 1732)
> What every model does, what it outputs, and what the numbers mean.

---

## The Full Pipeline — End to End

```
Raw OHRC Image (961×324 px)
        │
        ▼
  ┌─────────────────────────────┐
  │     PREPROCESSING           │
  │  1. crop_psr_panel()        │  → right ~420×324 px (dark crater floor)
  │  2. normalize_image()       │  → pixel values scaled to [0.0, 1.0]
  │  3. bad_pixel_correction()  │  → hot/dead pixels replaced by local median
  │  4. apply_clahe()           │  → local contrast boost
  └─────────────────────────────┘
        │
        ▼  (CLAHE image — same input to all denoisers)
        │
   ┌────┴──────┬──────────────┬──────────────┬──────────────┐
   ▼           ▼              ▼              ▼              ▼
  NLM         BM3D         Wavelet      Zero-DCE (DL)   [metrics]
   │           │              │              │
   └────┬──────┴──────────────┴──────────────┘
        │
        ▼
   Score each output → rank → declare winner
        │
        ▼
   🏆 Best Method + Metrics Table
```

---

## Stage 1 — Preprocessing

### What it does
The raw OHRC comparison image has two panels side by side:
- **Left panel**: a lit reference region of the lunar surface
- **Right panel**: the actual PSR crater floor (permanently dark)

The code auto-detects the separator and crops only the right panel.

### Steps

| Step | Function | What happens |
|------|----------|-------------|
| Crop | `crop_psr_panel()` | Isolates right ~50% = the dark crater floor |
| Normalize | `normalize_image()` | Scales pixel values from [0, 255] → [0.0, 1.0] float32 |
| Bad pixels | `bad_pixel_correction()` | Finds pixels > 4σ from local median; replaces with median |
| CLAHE | `apply_clahe()` | Adaptive histogram equalization — boosts local contrast |

### Why CLAHE first?
Without CLAHE, the image is too dark and flat — the denoiser would have almost nothing to work with. CLAHE makes faint crater features visible **before** denoising rather than after. Think of it as "pre-processing the darkness out" so the denoisers can operate on meaningful signal.

### Output of Stage 1
A float32 grayscale image in [0, 1] — the same image fed to all three (or four) algorithms.

---

## Stage 2 — The Three Classical Denoisers

All three receive the **identical CLAHE image** as input and return a **float32 grayscale [0,1]** image as output.

---

### Denoiser 1: NLM — Non-Local Means

**Core idea:**
> "If two patches of the image look similar, they probably represent the same surface material — average them together to cancel noise."

**How it works step by step:**
```
For every pixel P at position (x, y):
  1. Extract a small patch around P (5×5 pixels)
  2. Scan the entire image for all similar-looking patches
     (within a search window of 6-pixel radius)
  3. Weight each match by how similar it looks (Gaussian kernel)
  4. Replace P with the weighted average of all matched patch centres
```

**Parameters used:**
- `patch_size = 5` — size of comparison patch
- `patch_distance = 6` — search radius
- `h = 1.15 × σ_estimated` — smoothing strength (auto-tuned from image noise level)

**Output:** Smoothed image where repeated textures (crater floor patterns) reinforce each other and noise cancels out. Edges preserved fairly well because unique edges don't have many similar matches and therefore get less averaging.

**Strength:** Excellent texture preservation on repetitive surfaces  
**Weakness:** Slow (~0.6s here), can over-smooth unique one-off features

---

### Denoiser 2: BM3D — Block Matching 3D Filtering

**Core idea:**
> "Group similar image patches into 3D stacks, filter noise in that 3D space (where signal is consistent across the stack but noise is random), then put everything back."

**How it works step by step:**
```
Pass 1 (basic estimate):
  1. Divide image into overlapping blocks (patches)
  2. For each block → find similar blocks anywhere in image → stack into 3D cube
  3. Apply 3D Hard Threshold in wavelet domain:
       - Coefficients above threshold = signal → keep
       - Coefficients below threshold = noise → zero
  4. Invert transform → aggregate overlapping blocks back

Pass 2 (final Wiener filter using Pass 1 as guide):
  1. Repeat grouping using Pass 1 result as reference
  2. Apply 3D Wiener filter (optimal linear estimator)
  3. Aggregate → final output
```

**Why it wins (EdgePI = 0.875, score = 0.6344):**
The 3D structure means the algorithm sees noise as "inconsistent across the stack" and signal as "consistent." This makes it much smarter than 2D filtering — it can aggressively denoise while preserving edges because edges are *consistent* across matched blocks.

**Output:** State-of-the-art denoised image. Best edge preservation and contrast of the three classical methods.

**Strength:** Best quality, especially on textured surfaces  
**Weakness:** Heaviest computation (~4s on our 420×324 image)

---

### Denoiser 3: Wavelet — Daubechies db4 + VisuShrink

**Core idea:**
> "Noise lives in small wavelet coefficients. Real signal lives in large ones. Shrink the small ones to zero."

**How it works step by step:**
```
1. Decompose image using Daubechies db4 wavelet (4 levels)
   → Low-frequency subbands  = large structures, crater shape, slow gradients
   → High-frequency subbands = edges, fine detail, AND noise

2. VisuShrink threshold: T = σ × √(2 × log(N))
   where σ = estimated noise std, N = number of pixels

3. Soft threshold all high-frequency coefficients:
   - If |coeff| > T → shrink toward zero by T
   - If |coeff| ≤ T → set to zero

4. Reconstruct image from modified coefficients (inverse wavelet transform)
```

**Output:** Clean, somewhat smoother image. Fastest of the three (0.01s). Good baseline result. Can over-smooth if the threshold is too aggressive.

**Strength:** Extremely fast, principled mathematical foundation  
**Weakness:** Global threshold may be too aggressive in some image regions

---

## Stage 3 — Zero-DCE DL Baseline (optional 4th column)

**Core idea:**
> "Learn per-pixel tone curves from the image itself — no ground truth needed."

**Architecture:** DCE-Net — 7 convolutional layers with skip connections
```
Input: (1, 3, H, W) float tensor   ← grayscale replicated to 3 channels

Conv1 → ReLU → x1
Conv2 → ReLU → x2
Conv3 → ReLU → x3
Conv4 → ReLU → x4
Conv5(cat[x3,x4]) → ReLU → x5
Conv6(cat[x2,x5]) → ReLU → x6
Conv7(cat[x1,x6]) → Tanh → x_r   ← shape: (1, 24, H, W)
```

**What the 24 output channels are:**
- 24 channels = 8 iterations × 3 colour channels
- Each iteration produces a "curve map" `A(x,y)` ∈ [-1, +1] per pixel

**The curve formula — applied 8 times:**
```python
x = x + A * (x - x²)
```
Where:
- `x` = current pixel value [0, 1]
- `A` = learned adjustment from DCE-Net
- `(x - x²)` = a smooth bell curve that peaks at x=0.5 → most adjustment at midtones
- `A > 0` → brightens (pushes pixel up the curve)
- `A < 0` → darkens

Applied 8 times iteratively, each pass refining the enhancement.

**Why "inference-only":**
The pretrained weights (Epoch99.pth, 312 KB) were trained on general low-light photos — not OHRC lunar imagery. The model never "saw" PSR data during training. We just run a single forward pass and use whatever it produces. This is the "DL baseline" — it shows what a general-purpose model does vs. the domain-specific classical methods.

**Output:** Brightness-enhanced float32 grayscale image. Often looks visually appealing but may not score as well on scientific metrics (edge preservation, CNR) because the model optimised for human perception, not lunar geology.

---

## Stage 4 — Metrics (What the Numbers Mean)

Every denoiser output is scored on 4 metrics:

### SNR — Signal-to-Noise Ratio
```
SNR = mean(image) / std(image)
```
- **What it measures:** How much of the image is "signal" vs random variation
- **Higher = less noise.** A perfectly uniform image would have infinite SNR.
- **Typical range for PSR:** 5–20
- **Weight: 0.20**

### CNR — Contrast-to-Noise Ratio
```
signal_region = top 30% brightest pixels   (crater rim features, illuminated rocks)
background    = bottom 30% darkest pixels  (deep shadow floor)

CNR = (mean_signal - mean_background) / std_background
```
- **What it measures:** How distinct bright features are from the dark background, relative to noise
- **Higher = more interpretable geology** — you can tell apart the crater floor from lit features
- **Typical range:** 3–10
- **Weight: 0.30** (second highest — geologically important)

### EdgePI — Edge Preservation Index
```
1. Compute Sobel gradient magnitude of the CLAHE input image
2. Compute Sobel gradient magnitude of the denoised output
3. EdgePI = Pearson correlation between the two edge maps
```
- **What it measures:** Did the denoiser keep edges in the same places as the original?
  - `1.0` = perfect — all edges preserved exactly
  - `0.5` = half the edge structure destroyed
  - `0.0` = no correlation — all edges wiped out
- **Why it's critical for PSR science:** Edges = boulder outlines, crater rim boundaries, rock fractures. These are the scientifically interesting features.
- **Our result:** BM3D = 0.875, NLM = 0.874, Wavelet = 0.867
- **Weight: 0.35** (highest — most important for geology)

### Entropy — Shannon Entropy
```
1. Compute 256-bin intensity histogram of the image
2. Entropy = -Σ p(i) × log2(p(i))   for each bin i
```
- **What it measures:** How much information / detail is in the image
  - High entropy (~5.5) = many different intensity levels = rich detail
  - Low entropy (~1.0) = mostly uniform = over-smoothed / detail lost
- **Weight: 0.15** (useful sanity check — penalises over-smoothing)

### Weighted Score (how the winner is chosen)
```python
score = 0.35 × normalize(EdgePI)
      + 0.30 × normalize(CNR)
      + 0.20 × normalize(SNR)
      + 0.15 × normalize(Entropy)
```
Each metric is normalised to [0, 1] using known physical ranges before weighting.

---

## PSNR and SSIM — Why They're Only in Validation Tab

**PSNR (Peak Signal-to-Noise Ratio):**
```
PSNR = 10 × log10(1 / MSE)    where MSE = mean squared error vs ground truth
```
- Measures how close the denoised image is to the **true, clean original**
- **Requires knowing the ground truth** — impossible for real PSR imagery (no ground truth exists)

**SSIM (Structural Similarity Index):**
- Measures perceptual similarity in luminance, contrast, and structure vs ground truth
- Also **requires ground truth**

**How Synthetic Validation solves this:**
1. Take the **left panel** (lit reference region — well-exposed, clear)
2. Artificially degrade it: `darkened = image^3.0 × 0.15` + Poisson noise + Gaussian noise
3. Now we have a "fake PSR" where we know the correct answer
4. Run the full pipeline on the degraded version
5. Compare output against the original → compute PSNR and SSIM legitimately

This proves the pipeline actually recovers real detail rather than fabricating it.

---

## Final Output Summary — What You See in the App

| Tab | What's Shown |
|-----|-------------|
| **Real PSR Analysis** | Raw → CLAHE → 3 (or 4) denoised outputs side by side, each with SNR/CNR/EdgePI/Entropy scores + score bar. Winner banner with dominant metric. Full comparison table. |
| **Synthetic Validation** | Original → Degraded → CLAHE → 3 denoised outputs with **real PSNR/SSIM** vs known ground truth. Proves the pipeline works. |

### Concrete numbers from our test run (420×324 px OHRC PSR panel)

| Method | Score | EdgePI | CNR | SNR | Time |
|--------|-------|--------|-----|-----|------|
| **BM3D** ← 🏆 | 0.6344 | 0.8751 | 5.4950 | — | 4.13s |
| NLM | 0.6343 | 0.8743 | 5.4956 | — | 0.60s |
| Wavelet | 0.6322 | 0.8667 | 5.4482 | — | 0.01s |

- **BM3D wins** by a tiny margin — EdgePI 0.8751 vs NLM's 0.8743
- All three are very close because the image is small and well-handled by all algorithms
- On larger / noisier OHRC images the gap between methods would be larger
- **Wavelet** is the smart fallback when time is critical — 400× faster than BM3D with only ~0.3% less score

---

*PSR Enhancement Analyzer · SIH 1732 · Chandrayaan-2 OHRC*
