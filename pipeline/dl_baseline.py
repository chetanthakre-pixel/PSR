"""
pipeline/dl_baseline.py
Zero-DCE pretrained DL baseline — inference-only, no training.

Architecture: "Zero-Reference Deep Curve Estimation for Low-Light Image
Enhancement" (Li et al., CVPR 2020). A 7-layer DCE-Net estimates per-pixel
curve parameters (8 iterations × 3 channels = 24 output channels).

Fallback behaviour
------------------
If PyTorch is not installed or the weights file is missing, run_zero_dce()
returns (None, reason_string) and the app gracefully hides the DL column
without affecting the classical pipeline.
"""

from __future__ import annotations
import os
import numpy as np
from pathlib import Path

WEIGHTS_PATH = Path(__file__).parent.parent / "weights" / "zero_dce.pth"


# ─── DCE-NET ARCHITECTURE ────────────────────────────────────────────────────

def _build_dce_net():
    """Build the official DCE-Net (matches published pretrained weights)."""
    import torch
    import torch.nn as nn

    class DCENet(nn.Module):
        """Matches layer names in the official Epoch99.pth checkpoint."""

        def __init__(self):
            super().__init__()
            nf = 32
            self.relu = nn.ReLU(inplace=True)
            self.e_conv1 = nn.Conv2d(3, nf, 3, 1, 1, bias=True)
            self.e_conv2 = nn.Conv2d(nf, nf, 3, 1, 1, bias=True)
            self.e_conv3 = nn.Conv2d(nf, nf, 3, 1, 1, bias=True)
            self.e_conv4 = nn.Conv2d(nf, nf, 3, 1, 1, bias=True)
            self.e_conv5 = nn.Conv2d(nf * 2, nf, 3, 1, 1, bias=True)
            self.e_conv6 = nn.Conv2d(nf * 2, nf, 3, 1, 1, bias=True)
            self.e_conv7 = nn.Conv2d(nf * 2, 24, 3, 1, 1, bias=True)

        def forward(self, x):
            import torch
            x1 = self.relu(self.e_conv1(x))
            x2 = self.relu(self.e_conv2(x1))
            x3 = self.relu(self.e_conv3(x2))
            x4 = self.relu(self.e_conv4(x3))
            x5 = self.relu(self.e_conv5(torch.cat([x3, x4], dim=1)))
            x6 = self.relu(self.e_conv6(torch.cat([x2, x5], dim=1)))
            x_r = torch.tanh(self.e_conv7(torch.cat([x1, x6], dim=1)))
            return x_r

    return DCENet()


def _apply_curves(tensor, x_r):
    """Apply 8 iterative curve adjustments: x = x + r*(x - x²)."""
    import torch
    x = tensor
    for i in range(8):
        r = x_r[:, i * 3:(i + 1) * 3, :, :]
        x = x + r * (x - x ** 2)
    return x


# ─── PUBLIC API ──────────────────────────────────────────────────────────────

def run_zero_dce(img_gray: np.ndarray) -> tuple[np.ndarray | None, str | None]:
    """
    Run Zero-DCE on a float32 grayscale image [0, 1].

    Returns
    -------
    (enhanced_gray, None)   on success
    (None, error_message)   on any failure
    """
    # 1. Check PyTorch availability
    try:
        import torch
    except ImportError:
        return None, "PyTorch not installed (run: pip install -r optional_requirements.txt)"

    # 2. Check weights
    if not WEIGHTS_PATH.exists():
        return None, f"Weights not found at {WEIGHTS_PATH} — run setup.py to download"

    try:
        # 3. Build and load model
        model = _build_dce_net()
        state = torch.load(str(WEIGHTS_PATH), map_location="cpu", weights_only=True)

        # Handle state dict that may be wrapped under a key
        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]

        missing, unexpected = model.load_state_dict(state, strict=False)
        # Tolerate minor key mismatches (e.g., different checkpoint versions)
        if len(missing) > 10:
            return None, f"Weight mismatch: {len(missing)} missing keys"

        model.eval()

        # 4. Prepare input: gray → 3-channel float tensor (1, 3, H, W)
        img_3ch = np.stack([img_gray] * 3, axis=0)          # (3, H, W)
        tensor = torch.from_numpy(img_3ch).unsqueeze(0).float()  # (1, 3, H, W)

        # 5. Forward pass
        with torch.no_grad():
            x_r = model(tensor)                              # (1, 24, H, W)
            enhanced = _apply_curves(tensor, x_r)            # (1, 3, H, W)

        # 6. Back to grayscale numpy
        enhanced_np = enhanced.squeeze(0).numpy()            # (3, H, W)
        enhanced_gray = np.mean(enhanced_np, axis=0)         # (H, W)
        enhanced_gray = np.clip(enhanced_gray, 0, 1).astype(np.float32)
        return enhanced_gray, None

    except Exception as exc:
        return None, f"Inference error: {exc}"
