"""
pipeline/metrics.py
Image-quality metrics for PSR denoising evaluation.

Metric definitions
------------------
SNR   : Signal-to-Noise Ratio — mean(img) / std(img)
CNR   : Contrast-to-Noise Ratio — (mean_signal - mean_bg) / std_bg
          signal = top-30% intensity pixels, bg = bottom-30%
EdgePI: Edge Preservation Index — Pearson corr of Sobel edge maps
          (input vs denoised). Closer to 1.0 = better edge retention.
Entropy: Shannon entropy of intensity histogram — higher = richer detail.
PSNR  : Peak SNR vs ground truth (synthetic validation only)
SSIM  : Structural Similarity vs ground truth (synthetic validation only)

Weighted score
--------------
  score = 0.35 * EdgePI_norm
        + 0.30 * CNR_norm
        + 0.20 * SNR_norm
        + 0.15 * Entropy_norm

Edge preservation and CNR weighted highest: what matters most for
crater / boulder interpretability in PSR science.
"""

import numpy as np
import cv2
from scipy.stats import entropy as scipy_entropy


# ─── NORMALISATION RANGES (empirically set for PSR lunar imagery) ─────────────
_NORM = {
    "SNR":     (0.0, 25.0),
    "CNR":     (0.0, 12.0),
    "EdgePI":  (-1.0, 1.0),
    "Entropy": (0.0,  5.6),
}

_WEIGHTS = {
    "EdgePI":  0.35,
    "CNR":     0.30,
    "SNR":     0.20,
    "Entropy": 0.15,
}


# ─── INDIVIDUAL METRICS ───────────────────────────────────────────────────────

def compute_snr(img: np.ndarray) -> float:
    """SNR = mean / std."""
    std = float(np.std(img))
    return float(np.mean(img)) / std if std > 1e-10 else 0.0


def compute_cnr(img: np.ndarray) -> float:
    """
    CNR using brightest vs darkest 30% pixel populations.
    Approximates signal (bright crater rim features) vs background (shadow floor).
    """
    flat = img.flatten()
    n = len(flat)
    srt = np.sort(flat)
    bg = srt[: int(0.30 * n)]
    sig = srt[int(0.70 * n):]
    std_bg = float(np.std(bg))
    if std_bg < 1e-10:
        return 0.0
    return float((np.mean(sig) - np.mean(bg)) / std_bg)


def compute_edge_preservation(original: np.ndarray,
                              denoised: np.ndarray) -> float:
    """
    Pearson correlation of Sobel gradient magnitude maps.
    1.0 = perfect edge preservation; < 0 = edges destroyed.
    """
    def _sobel_mag(arr):
        u8 = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
        gx = cv2.Sobel(u8, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(u8, cv2.CV_64F, 0, 1, ksize=3)
        return np.sqrt(gx ** 2 + gy ** 2).flatten()

    orig_e = _sobel_mag(original)
    den_e = _sobel_mag(denoised)

    std_o = np.std(orig_e)
    std_d = np.std(den_e)
    if std_o < 1e-10 or std_d < 1e-10:
        return 0.0
    return float(np.clip(np.corrcoef(orig_e, den_e)[0, 1], -1.0, 1.0))


def compute_entropy(img: np.ndarray) -> float:
    """Shannon entropy of the 256-bin intensity histogram."""
    hist, _ = np.histogram(img.flatten(), bins=256, range=(0.0, 1.0),
                           density=False)
    hist = hist.astype(np.float64) + 1e-12   # avoid log(0)
    hist /= hist.sum()
    return float(-np.sum(hist * np.log2(hist + 1e-12)))


def compute_psnr(original: np.ndarray, enhanced: np.ndarray) -> float:
    """PSNR in dB. Only meaningful when original is the known ground truth."""
    mse = float(np.mean((original.astype(np.float32) -
                          enhanced.astype(np.float32)) ** 2))
    if mse < 1e-12:
        return float("inf")
    return 10.0 * np.log10(1.0 / mse)


def compute_ssim(original: np.ndarray, enhanced: np.ndarray) -> float:
    """SSIM. Only meaningful for synthetic validation with known ground truth."""
    from skimage.metrics import structural_similarity
    return float(structural_similarity(
        original.astype(np.float32),
        enhanced.astype(np.float32),
        data_range=1.0,
    ))


# ─── BATCH COMPUTATION ───────────────────────────────────────────────────────

def compute_all_metrics(original: np.ndarray,
                        denoised: np.ndarray,
                        ground_truth: np.ndarray | None = None) -> dict:
    """
    Compute SNR, CNR, EdgePI, Entropy for one denoised result.
    If ground_truth is provided, also compute PSNR and SSIM.
    """
    m = {
        "SNR":     round(compute_snr(denoised), 4),
        "CNR":     round(compute_cnr(denoised), 4),
        "EdgePI":  round(compute_edge_preservation(original, denoised), 4),
        "Entropy": round(compute_entropy(denoised), 4),
        "PSNR":    "N/A (no ground truth)",
        "SSIM":    "N/A (no ground truth)",
    }
    if ground_truth is not None:
        m["PSNR"] = round(compute_psnr(ground_truth, denoised), 2)
        m["SSIM"] = round(compute_ssim(ground_truth, denoised), 4)
    return m


# ─── SCORING & RANKING ───────────────────────────────────────────────────────

def _norm_val(key: str, val: float) -> float:
    lo, hi = _NORM[key]
    return float(np.clip((val - lo) / (hi - lo), 0.0, 1.0))


def compute_weighted_score(metrics: dict) -> float:
    """
    Weighted composite score ∈ [0, 1].
    Metrics that are strings ("N/A …") are ignored in scoring.
    """
    score = 0.0
    for key, w in _WEIGHTS.items():
        val = metrics.get(key, 0.0)
        if isinstance(val, (int, float)):
            score += w * _norm_val(key, val)
    return round(score, 4)


def rank_methods(all_metrics: dict) -> list[tuple[str, float]]:
    """
    Return list of (method_name, score) sorted highest-first.
    all_metrics: {method_name: metrics_dict}
    """
    scored = {name: compute_weighted_score(m) for name, m in all_metrics.items()}
    return sorted(scored.items(), key=lambda x: x[1], reverse=True)


def dominant_reason(metrics: dict) -> str:
    """
    Return a short human-readable string explaining why this method won,
    e.g. 'highest EdgePI (0.94) + CNR (8.21)'.
    """
    top_keys = sorted(_WEIGHTS, key=lambda k: _WEIGHTS[k], reverse=True)[:2]
    parts = []
    for k in top_keys:
        v = metrics.get(k)
        if isinstance(v, float):
            parts.append(f"{k} = {v:.3f}")
    return " -- ".join(parts) if parts else "composite score"
