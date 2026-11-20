"""Renders caption cues to transparent RGBA PNGs that `compose.py` overlays via ffmpeg.

Two styles:
- "block": the whole cue appears as one static image for its full time span. No per-word
  color change. Always used as the fallback when a cue doesn't fit on one line (see below).
- "karaoke": the cue is rendered once per word boundary, with words already spoken drawn in
  `highlight_color` and the rest in the base text color — i.e. one small PNG per *word*, not
  per video frame (a 4-word cue is 4 PNGs), swapped via ffmpeg `overlay=...:enable=between(...)`.

Word-by-word reveal draws the full cue once in the base text color (always fully visible, so
the line never jumps/reflows), then draws just the already-spoken prefix a second time in the
highlight color, anchored to the reading-start edge of that same line: left edge for English
(`anchor="lm"`), right edge for Farsi (`anchor="rm"`). Because the prefix is reshaped and
bidi-reordered on its own and anchored at the edge reading starts from, it lands on exactly the
glyphs it's meant to highlight without needing to compute any pixel offset into the full line —
this works the same way for both directions. The one simplification worth naming: reshaping a
short prefix in isolation can very rarely join slightly differently than it would mid-line
(arabic_reshaper's joining is local to each word; spaces break it, so this is uncommon) — see
docs/troubleshooting.md.

If a cue doesn't fit on one line at the target canvas width, it's wrapped to multiple lines and
rendered once, fully in the base text color, for its whole span — karaoke reveal is skipped for
that cue rather than attempted across a line break.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from videogen.core import text_shaping
from videogen.core.fonts import get_font
from videogen.core.layers import OverlayLayer, TimeSpan
from videogen.core.layout import band_y_px, font_size_px, safe_margin_px
from videogen.core.timeline import Cue
from videogen.models import CaptionStyle
from videogen.platforms import Platform

_LINE_SPACING = 1.3
_VERTICAL_PADDING_RATIO = 0.35  # extra band height above/below the text, as a ratio of font size


def render_caption_overlays(
    cues: list[Cue],
    language: str,
    style: CaptionStyle,
    canvas: Platform,
    brand: dict,
    out_dir: Path,
) -> list[OverlayLayer]:
    if style.style == "none" or not cues:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    font_size = font_size_px(canvas, style.font_size_ratio)
    font = get_font(brand, language, font_size, bold=True)
    margin = safe_margin_px(canvas)
    max_text_w = canvas.width - 2 * margin
    text_color = brand["colors"]["text"]
    highlight_color = style.highlight_color or brand["colors"]["accent"]

    overlays: list[OverlayLayer] = []
    for cue_idx, cue in enumerate(cues):
        words = [w.text for w in cue.words if w.text]
        if not words:
            continue
        single_line = " ".join(words)
        fits_one_line = font.getlength(text_shaping.shape_for_display(single_line, language)) <= max_text_w

        if style.style == "karaoke" and fits_one_line:
            overlays.extend(
                _render_karaoke_states(
                    cue, cue_idx, language, font, font_size, canvas,
                    text_color, highlight_color, out_dir, style.position,
                )
            )
        else:
            overlays.append(
                _render_block_cue(
                    cue, cue_idx, words, language, font, font_size, canvas, max_text_w,
                    text_color, out_dir, style.position,
                )
            )
    return overlays


def _render_karaoke_states(
    cue: Cue, cue_idx: int, language: str, font, font_size: int, canvas: Platform,
    text_color: str, highlight_color: str, out_dir: Path, position: float,
) -> list[OverlayLayer]:
    full_text = " ".join(w.text for w in cue.words if w.text)
    full_display = text_shaping.shape_for_display(full_text, language)
    band_w = canvas.width
    band_h = round(font_size * (1 + 2 * _VERTICAL_PADDING_RATIO))
    mid_y = band_h / 2
    full_w = font.getlength(full_display)
    left_edge = band_w / 2 - full_w / 2
    right_edge = band_w / 2 + full_w / 2

    overlays: list[OverlayLayer] = []
    n = len(cue.words)
    for i in range(n):
        highlighted_count = i + 1
        start_s = cue.words[i].start_s
        end_s = cue.words[i + 1].start_s if i + 1 < n else cue.end_s

        band = Image.new("RGBA", (band_w, band_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(band)
        draw.text((band_w / 2, mid_y), full_display, font=font, fill=text_color, anchor="mm")

        prefix_text = " ".join(w.text for w in cue.words[:highlighted_count] if w.text)
        prefix_display = text_shaping.shape_for_display(prefix_text, language)
        if prefix_display:
            if language == "fa":
                draw.text((right_edge, mid_y), prefix_display, font=font, fill=highlight_color, anchor="rm")
            else:
                draw.text((left_edge, mid_y), prefix_display, font=font, fill=highlight_color, anchor="lm")

        png_path = out_dir / f"cue_{cue_idx:04d}_state_{i:02d}.png"
        band.save(png_path)
        y_px = band_y_px(canvas, position, band_h)
        overlays.append(
            OverlayLayer(
                png_path=png_path, x_px=0, y_px=y_px,
                span=TimeSpan(start_s=start_s, end_s=end_s), z=10,
            )
        )
    return overlays


def _render_block_cue(
    cue: Cue, cue_idx: int, words: list[str], language: str, font, font_size: int,
    canvas: Platform, max_text_w: int, text_color: str, out_dir: Path, position: float,
) -> OverlayLayer:
    lines = text_shaping.wrap_words(words, font, max_text_w)
    display_lines = [text_shaping.shape_for_display(line, language) for line in lines]

    line_h = round(font_size * _LINE_SPACING)
    band_w = canvas.width
    band_h = round(len(display_lines) * line_h + font_size * 2 * _VERTICAL_PADDING_RATIO)

    band = Image.new("RGBA", (band_w, band_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(band)
    top = (band_h - len(display_lines) * line_h) / 2 + line_h / 2
    for i, line in enumerate(display_lines):
        y = top + i * line_h
        draw.text((band_w / 2, y), line, font=font, fill=text_color, anchor="mm")

    png_path = out_dir / f"cue_{cue_idx:04d}_block.png"
    band.save(png_path)
    y_px = band_y_px(canvas, position, band_h)
    return OverlayLayer(
        png_path=png_path, x_px=0, y_px=y_px, span=TimeSpan(start_s=cue.start_s, end_s=cue.end_s), z=10
    )
