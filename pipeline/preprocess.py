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


# ─── SMART CROP ──────────────────────────────────────────────────────────────

def _find_vertical_split(img_gray: np.ndarray) -> int | None:
    """
    Detect the vertical separator line between the two panels of a
    side-by-side comparison image by finding the minimum-variance column
    in the central third of the image.
    If the image is not a dual-panel image (e.g. aspect ratio < 1.7), returns None.
    """
    h, w = img_gray.shape[:2]
    if w / max(h, 1) < 1.7:
        return None

    lo, hi = w // 3, 2 * w // 3
    if hi <= lo:
        return None

    mid = img_gray[:, lo:hi]
    col_var = np.var(mid.astype(np.float32), axis=0)
    min_idx = int(np.argmin(col_var))

    # Only trust it if variance there is unusually low (likely a separator)
    if col_var[min_idx] < np.median(col_var) * 0.5:
        return lo + min_idx + 3   # +3 px to skip the separator itself
    
    # If wide comparison format (> 2.2:1 aspect ratio), use middle split
    if w / max(h, 1) >= 2.2:
        return w // 2
        
    return None


def crop_psr_panel(img: np.ndarray) -> np.ndarray:
    """
    Crop the RIGHT panel (PSR crater floor) from a side-by-side
    OHRC comparison image. If already a single-panel image, returns full image.
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    split = _find_vertical_split(gray)
    if split is None or split >= w - 10:
        return img
    return img[:, split:, ...] if img.ndim == 3 else img[:, split:]


def crop_reference_panel(img: np.ndarray) -> np.ndarray:
    """
    Crop the LEFT panel (lit reference region) for synthetic validation.
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    split = _find_vertical_split(gray)
    return img[:, :split, ...] if img.ndim == 3 else img[:, :split]


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
    psr_bgr = crop_psr_panel(img_bgr)
    gray = cv2.cvtColor(psr_bgr, cv2.COLOR_BGR2GRAY)
    normalized = normalize_image(gray.astype(np.float32))
    normalized = bad_pixel_correction(normalized)
    clahe_out = apply_clahe(normalized, clip_limit=clahe_clip, tile_grid=clahe_tile)
    return psr_bgr, normalized, clahe_out


def make_synthetic_noisy(img_float: np.ndarray,
                         darken_gamma: float = 3.0,
                         darken_scale: float = 0.15,
                         gaussian_sigma: float = 0.05,
                         poisson_scale: float = 80.0,
                         seed: int = 42) -> np.ndarray:
    """
    Simulate PSR-like noise on a well-lit reference crop:
      1. Gamma darkening + scale
      2. Poisson photon noise
      3. Additive Gaussian read noise

    Returns float32 [0, 1].
    """
    rng = np.random.default_rng(seed)
    dark = np.clip(img_float ** darken_gamma * darken_scale, 0, 1)

    # Poisson (shot) noise
    photons = rng.poisson(dark * poisson_scale) / poisson_scale
    photons = np.clip(photons, 0, 1).astype(np.float32)

    # Gaussian (read/thermal) noise
    gauss = rng.normal(0, gaussian_sigma, photons.shape).astype(np.float32)
    noisy = np.clip(photons + gauss, 0, 1)
    return noisy.astype(np.float32)
