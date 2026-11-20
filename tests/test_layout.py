from videogen.core.layout import band_y_px, font_size_px, safe_margin_px
from videogen.platforms import PLATFORMS

INSTAGRAM = PLATFORMS["instagram"]  # 1080x1920


def test_font_size_px_scales_with_height():
    assert font_size_px(INSTAGRAM, 0.055) == round(1920 * 0.055)


def test_font_size_px_has_a_floor():
    assert font_size_px(INSTAGRAM, 0.0001) >= 12


def test_safe_margin_px_uses_smaller_dimension():
    assert safe_margin_px(INSTAGRAM, 0.08) == round(1080 * 0.08)


def test_band_y_px_centers_on_fraction():
    band_h = 100
    y = band_y_px(INSTAGRAM, 0.5, band_h)
    assert y == round(1920 * 0.5 - band_h / 2)


def test_band_y_px_clamps_to_canvas():
    # a huge band near the bottom edge must not push past the canvas
    y = band_y_px(INSTAGRAM, 0.99, 500)
    assert 0 <= y <= INSTAGRAM.height - 500
