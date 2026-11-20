"""Declarative description of what gets composited, in pixel coordinates for one specific
canvas. `compose.py` lowers a list of these into a single ffmpeg filter graph; nothing
upstream of this module needs to know ffmpeg filter syntax.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class TimeSpan:
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


@dataclass(frozen=True)
class BackgroundLayer:
    """One scene's full-canvas background. Always fills the whole frame — this project has
    no avatar or picture-in-picture, so there's nothing to position sub-rects for."""

    kind: Literal["solid", "image", "video"]
    span: TimeSpan
    color: str | None = None
    src: Path | None = None
    ken_burns: bool = False


@dataclass(frozen=True)
class OverlayLayer:
    """A pre-rendered RGBA PNG (a caption cue, or a text-card slide) overlaid at (x_px, y_px)
    for the given time span. z breaks ties when spans overlap (higher draws on top)."""

    png_path: Path
    x_px: int
    y_px: int
    span: TimeSpan
    z: int = 0
