"""A Template turns a project's scenes into layers for one specific canvas. That's the only
thing that differs between `faceless` and `text_card` — everything else (TTS, timeline,
captions, audio, ffmpeg compose/export) is shared pipeline code neither template touches.

To add a new template: subclass `Template`, implement `build_backgrounds` (and optionally
`build_extra_overlays` for template-specific visuals like text-card's big on-screen text),
then register it in `templates/__init__.py`. See docs/adding-a-template.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from videogen.core.layers import BackgroundLayer, OverlayLayer
from videogen.core.timeline import Timeline
from videogen.models import VideoProject
from videogen.platforms import Platform
from videogen.providers.base import WordTiming


class Template(ABC):
    @abstractmethod
    def build_backgrounds(
        self, project: VideoProject, timeline: Timeline, canvas: Platform
    ) -> list[BackgroundLayer]:
        """One full-canvas background layer per scene (solid color, image, or video)."""

    def build_extra_overlays(
        self,
        project: VideoProject,
        timeline: Timeline,
        canvas: Platform,
        brand: dict,
        work_dir: Path,
    ) -> list[OverlayLayer]:
        """Template-specific overlays beyond captions (e.g. text_card's big on-screen text).
        Default: none — most templates only need the background + the shared caption layer."""
        return []


def scene_words(timeline: Timeline, scene_index: int) -> list[WordTiming]:
    """Absolute-time word timings belonging to one scene, for templates that need to sync
    their own visuals (not just captions) to speech — e.g. text_card's word-by-word reveal."""
    span = timeline.scene_spans[scene_index]
    return [w for w in timeline.words if span.start_s <= w.start_s < span.end_s]
