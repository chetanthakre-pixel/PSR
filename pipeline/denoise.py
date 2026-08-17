"""
pipeline/denoise.py
Three classical denoising algorithms + a convenience runner.
All functions accept and return float32 grayscale [0, 1] arrays.
"""

import time
import numpy as np
from skimage.restoration import (
    denoise_nl_means,
    denoise_wavelet,
    estimate_sigma,
)


# ─── NLM ─────────────────────────────────────────────────────────────────────

def denoise_nlm(img: np.ndarray,
                patch_size: int = 5,
                patch_distance: int = 6,
                h_factor: float = 1.15) -> np.ndarray:
    """
    Non-Local Means denoising (scikit-image fast_mode).

    h_factor: scalar applied to the auto-estimated sigma → controls
              smoothing strength. 1.15 is a mild setting that preserves edges.
    """
    sigma_est = float(np.mean(estimate_sigma(img, channel_axis=None)))
    denoised = denoise_nl_means(
        img,
        h=h_factor * sigma_est,
        fast_mode=True,
        patch_size=patch_size,
        patch_distance=patch_distance,
        channel_axis=None,
    )
    return np.clip(denoised, 0, 1).astype(np.float32)


# ─── BM3D ────────────────────────────────────────────────────────────────────

def denoise_bm3d(img: np.ndarray) -> np.ndarray:
    """
    BM3D Block-Matching 3D denoising using the `bm3d` pip package.
    Auto-estimates noise sigma from the image.
    """
    try:
        import bm3d as bm3d_pkg
        sigma_est = float(np.mean(estimate_sigma(img, channel_axis=None)))
        denoised = bm3d_pkg.bm3d(
            img,
            sigma_psd=sigma_est,
            stage_arg=bm3d_pkg.BM3DStages.ALL_STAGES,
        )
        return np.clip(denoised, 0, 1).astype(np.float32)
    except ImportError as exc:
        raise ImportError(
            "bm3d package not found. Install with: pip install bm3d"
        ) from exc


# ─── WAVELET ─────────────────────────────────────────────────────────────────

def denoise_wavelet_fn(img: np.ndarray,
                       wavelet: str = "db4",
                       levels: int = 4,
                       mode: str = "soft") -> np.ndarray:
    """
    Wavelet denoising (Daubechies db4, soft threshold, VisuShrink).
    """
    denoised = denoise_wavelet(
        img,
        method="VisuShrink",
        mode=mode,
        wavelet=wavelet,
        wavelet_levels=levels,
        rescale_sigma=True,
        channel_axis=None,
    )
    return np.clip(denoised, 0, 1).astype(np.float32)


# ─── RUNNER ──────────────────────────────────────────────────────────────────

_DENOISERS = {
    "NLM": denoise_nlm,
    "BM3D": denoise_bm3d,
    "Wavelet": denoise_wavelet_fn,
}

_DENOISER_LABELS = {
    "NLM": "Non-Local Means",
    "BM3D": "BM3D (Block-Matching 3D)",
    "Wavelet": "Wavelet (db4, VisuShrink)",
}

_DENOISER_DESC = {
    "NLM": "Searches for similar patches across the image to average out noise while preserving texture.",
    "BM3D": "Groups similar 2D patches into 3D stacks, applies collaborative filtering, then aggregates.",
    "Wavelet": "Decomposes image into frequency sub-bands; soft-thresholds small (noisy) coefficients.",
}


def run_all_denoisers(clahe_img: np.ndarray) -> dict:
    """
    Run NLM, BM3D, and Wavelet on the CLAHE-preprocessed input.

    Returns
    -------
    dict keyed by method name, each value is:
      {
        "image":  float32 numpy array [0,1],
        "time_s": float,
        "error":  str or None,
        "label":  human-readable name,
        "desc":   one-line description,
      }
    """
    results = {}
    for name, fn in _DENOISERS.items():
        t0 = time.perf_counter()
        try:
            out = fn(clahe_img)
            elapsed = time.perf_counter() - t0
            results[name] = {
                "image": out,
                "time_s": round(elapsed, 2),
                "error": None,
                "label": _DENOISER_LABELS[name],
                "desc": _DENOISER_DESC[name],
            }
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            results[name] = {
                "image": clahe_img.copy(),  # fallback: return CLAHE output
                "time_s": round(elapsed, 2),
                "error": str(exc),
                "label": _DENOISER_LABELS[name],
                "desc": _DENOISER_DESC[name],
            }
    return results
