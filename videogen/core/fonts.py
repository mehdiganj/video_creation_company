"""Loads the right font file/weight for a given language, per `brand.yaml`."""

from __future__ import annotations

from functools import cache

from PIL import ImageFont

from videogen.settings import REPO_ROOT


@cache
def _load_truetype(path_str: str, size: int, variation: str | None) -> ImageFont.FreeTypeFont:
    # `variation` is part of the cache key (not applied after the fact) because
    # FreeTypeFont objects are mutable — sharing one instance between a "Regular" and
    # "Bold" request and mutating it in place would make both callers see whichever
    # weight was set last.
    font = ImageFont.truetype(path_str, size=size)
    if variation:
        try:
            font.set_variation_by_name(variation)
        except (AttributeError, OSError, ValueError):
            pass  # static (non-variable) font file — nothing to select, this is fine
    return font


def get_font(brand: dict, language: str, size_px: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """`brand` is the parsed brand.yaml dict (see brand_loader.load_brand)."""
    fonts = brand["fonts"]
    size_px = max(1, int(size_px))

    if language == "fa":
        path = fonts["farsi"]["bold_path" if bold else "regular_path"]
        return _load_truetype(str(REPO_ROOT / path), size_px, None)

    path = fonts["latin"]["path"]
    variation_name = fonts["latin"]["variation_bold" if bold else "variation_regular"]
    return _load_truetype(str(REPO_ROOT / path), size_px, variation_name)
