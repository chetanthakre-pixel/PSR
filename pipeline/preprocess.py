"""
pipeline/preprocess.py
Normalization, CLAHE, and smart panel cropping for OHRC comparison images.
"""

import cv2
import numpy as np


# ─── UTILITY ─────────────────────────────────────────────────────────────────

def normalize_image(img: np.ndarray) -> np.ndarray:
    """Scale any numeric image to float32 in [0, 1]."""
    img = img.astype(np.float32)
    lo, hi = img.min(), img.max()
    if hi - lo < 1e-8:
        return np.zeros_like(img)
    return (img - lo) / (hi - lo)


def bad_pixel_correction(img: np.ndarray) -> np.ndarray:
    """Replace obvious hot/dead pixels (> 4σ from local median) via median filter."""
    from scipy.ndimage import median_filter
    med = median_filter(img, size=3)
    diff = np.abs(img - med)
    thresh = 4 * np.std(diff)
    corrected = img.copy()
    corrected[diff > thresh] = med[diff > thresh]
    return corrected


# ─── CLAHE ───────────────────────────────────────────────────────────────────

def apply_clahe(img_gray: np.ndarray, clip_limit: float = 3.0,
                tile_grid: tuple = (8, 8)) -> np.ndarray:
    """
    Tile-based CLAHE on a float32 grayscale [0,1] image.
    Returns float32 [0,1].
    """
    img_u8 = (np.clip(img_gray, 0, 1) * 255).astype(np.uint8)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid)
    enhanced = clahe.apply(img_u8)
    return enhanced.astype(np.float32) / 255.0



# ─── FULL PREPROCESSING PIPELINE ─────────────────────────────────────────────

def preprocess_pipeline(img_bgr: np.ndarray,
                        clahe_clip: float = 3.0,
                        clahe_tile: tuple = (8, 8)):
    """
    End-to-end preprocessing for the PSR (right) panel.

    Parameters
    ----------
    img_bgr : numpy array (H, W, 3) in BGR uint8

    Returns
    -------
    psr_bgr      : cropped BGR panel (for display)
    normalized   : float32 grayscale [0,1] after bad-pixel correction
    clahe_out    : float32 grayscale [0,1] after CLAHE
    """
    # Use the full image — no panel crop
    psr_bgr = img_bgr
    gray = cv2.cvtColor(psr_bgr, cv2.COLOR_BGR2GRAY)
    normalized = normalize_image(gray.astype(np.float32))
    normalized = bad_pixel_correction(normalized)
    clahe_out = apply_clahe(normalized, clip_limit=clahe_clip, tile_grid=clahe_tile)
    return psr_bgr, normalized, clahe_out

