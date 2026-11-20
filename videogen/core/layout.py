"""Small pixel-geometry helpers shared by captions.py and templates/text_card.py.

Both templates' backgrounds are always full-canvas (solid fill, image, or video) — there's
no sub-rect positioning to resolve in this project (no avatar, no picture-in-picture), so this
module stays deliberately small: just the handful of fraction-to-pixel conversions that let
the same project YAML render correctly at every platform's canvas size ("native" reframe).
"""

from __future__ import annotations

from videogen.platforms import Platform


def font_size_px(canvas: Platform, ratio: float) -> int:
    return max(12, round(canvas.height * ratio))


def safe_margin_px(canvas: Platform, fraction: float = 0.08) -> int:
    return round(min(canvas.width, canvas.height) * fraction)


def band_y_px(canvas: Platform, center_fraction: float, band_height_px: int) -> int:
    """Top-left y for a horizontal band whose vertical center sits at `center_fraction`
    of the canvas height, clamped so it never runs off the top/bottom edge."""
    y = round(canvas.height * center_fraction - band_height_px / 2)
    return max(0, min(y, canvas.height - band_height_px))
