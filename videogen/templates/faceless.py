"""Voiceover over a background — a solid color, a still image (optionally panned/zoomed with
a Ken Burns effect), or a looping video clip. No avatar, no on-screen big text: the narration
and captions carry the video. Good for general narrated reels/shorts.
"""

from __future__ import annotations

from videogen.core.layers import BackgroundLayer, TimeSpan
from videogen.core.timeline import Timeline
from videogen.models import VideoProject, Visual
from videogen.platforms import Platform
from videogen.settings import REPO_ROOT
from videogen.templates.base import Template


class FacelessTemplate(Template):
    def build_backgrounds(
        self, project: VideoProject, timeline: Timeline, canvas: Platform
    ) -> list[BackgroundLayer]:
        layers = []
        for span in timeline.scene_spans:
            visual = span.scene.visual or Visual(kind="solid")
            layers.append(
                BackgroundLayer(
                    kind=visual.kind,
                    span=TimeSpan(start_s=span.start_s, end_s=span.end_s),
                    color=visual.color,
                    src=(REPO_ROOT / visual.src) if visual.src else None,
                    ken_burns=(visual.motion == "ken_burns"),
                )
            )
        return layers
