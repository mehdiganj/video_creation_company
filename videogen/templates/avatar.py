"""A static portrait (see `assets/avatar/`) as the full-canvas background for every scene,
with a slow Ken-Burns-style zoom so it doesn't read as a dead still frame, plus captions and
(optionally) music — narration carries the video, same as `faceless`.

This is deliberately not a lip-synced talking avatar: the source images are flat, opaque
portraits (no transparent cutout, no separate mouth/eye layers), so there's nothing to animate
beyond the picture itself. See assets/avatar/README.md if layered art ever gets added later —
the pipeline already has everything else (captions, timeline, audio) this would need; only a
new background rendering step (per-frame mouth compositing) would have to be added.
"""

from __future__ import annotations

from videogen.avatar_presets import resolve_avatar_path
from videogen.core.layers import BackgroundLayer, TimeSpan
from videogen.core.timeline import Timeline
from videogen.models import VideoProject
from videogen.platforms import Platform
from videogen.settings import REPO_ROOT
from videogen.templates.base import Template


class AvatarTemplate(Template):
    def build_backgrounds(
        self, project: VideoProject, timeline: Timeline, canvas: Platform
    ) -> list[BackgroundLayer]:
        src = REPO_ROOT / resolve_avatar_path(project.avatar)
        return [
            BackgroundLayer(
                kind="image",
                span=TimeSpan(span.start_s, span.end_s),
                src=src,
                ken_burns=True,
            )
            for span in timeline.scene_spans
        ]
