"""Text layout and shaping for drawing with Pillow.

Pillow on this project's target environment has no RAQM (`PIL.features.check("raqm")` is
False), which means it cannot shape complex scripts itself. For Farsi this means:

1. Word-wrap in LOGICAL (reading) order, measuring with the plain (unshaped) string — shaping
   can change width slightly but not enough to break wrapping in practice for our font sizes.
2. Per *line* (after wrapping, not before): reshape with `arabic_reshaper` (joins letterforms)
   then reorder to VISUAL order with `python-bidi`.
3. Draw the resulting visual-order string with Pillow as if it were a normal LTR string.

Doing this per-line rather than on the whole text is what keeps mixed Farsi+English+digit
lines correct — Mehdi routinely writes Farsi sentences with embedded English terms ("Claude
Code") and Latin digits, which are themselves LTR runs embedded in an RTL line. python-bidi
handles the mixed-direction reordering; arabic_reshaper only needs to see Arabic-script runs.

Caption *timing* must stay keyed to the logical-order words (that's what Azure gives us);
only this module's output — the string actually handed to Pillow's `draw.text()` — is in
visual order.
"""

from __future__ import annotations

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import ImageFont

_reshaper = arabic_reshaper.ArabicReshaper(
    configuration={"delete_harakat": False, "support_ligatures": True}
)


def shape_for_display(line: str, language: str) -> str:
    """Convert one line of logical-order text into the string Pillow should draw.
    No-op for English/Latin; reshape+bidi for Farsi."""
    if language != "fa":
        return line
    return get_display(_reshaper.reshape(line))


def wrap_words(
    words: list[str], font: ImageFont.FreeTypeFont, max_width_px: float
) -> list[str]:
    """Greedy word-wrap in logical order, measuring the *unshaped* string. Returns a list of
    logical-order lines (call `shape_for_display` on each line before drawing, not before)."""
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = current + [word]
        if current and font.getlength(" ".join(trial)) > max_width_px:
            lines.append(" ".join(current))
            current = [word]
        else:
            current = trial
    if current:
        lines.append(" ".join(current))
    return lines or [""]


def is_rtl(language: str) -> bool:
    return language == "fa"
