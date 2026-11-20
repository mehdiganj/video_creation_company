# Adding a new template

A template only decides how a project's scenes become visual layers. Everything else — TTS,
word timings, caption rendering, audio mixing, ffmpeg compose, multi-platform export, caching —
is shared pipeline code in `videogen/core/` that no template touches.

1. Create `videogen/templates/your_template.py`:

```python
from videogen.core.layers import BackgroundLayer, TimeSpan
from videogen.core.timeline import Timeline
from videogen.models import VideoProject
from videogen.platforms import Platform
from videogen.templates.base import Template


class YourTemplate(Template):
    def build_backgrounds(
        self, project: VideoProject, timeline: Timeline, canvas: Platform
    ) -> list[BackgroundLayer]:
        # One BackgroundLayer per scene, covering that scene's TimeSpan.
        ...

    # Optional — only implement this if you need visuals beyond captions
    # (text_card's big on-screen text is a good example to copy from).
    # def build_extra_overlays(self, project, timeline, canvas, brand, work_dir):
    #     ...
```

2. Register it in `videogen/templates/__init__.py`'s `REGISTRY` dict.

3. Add `"your_template"` to `TemplateName` in `videogen/models.py` (a `Literal`, so this is
   also where you get schema validation for free).

4. Add a scaffold at `projects/_templates/your_template.yaml` (copy an existing one — `new`
   does a literal `REPLACE_ME_NAME` / `REPLACE_ME_LANGUAGE` substitution, nothing fancier) and
   add `"your_template"` to the `--template` choices in `videogen/cli.py`.

5. Add a minimal example project and a test in `tests/test_pipeline_e2e.py` that renders it
   with the mock TTS provider.

## What you get for free

- Word-level caption sync (`core/timeline.py`, `core/captions.py`) — karaoke or block style,
  Farsi-correct, with automatic wrap-to-block fallback for long cues.
- Multi-platform export (`core/compose.py`, `core/export.py`) — `native` reframe re-runs your
  `build_backgrounds`/`build_extra_overlays` per canvas, so write your layout logic in terms of
  the `canvas: Platform` you're given (its `.width`/`.height`), not a hardcoded size.
- Music ducking/loudness normalization (`core/audio.py`) — runs once per project regardless of
  how many templates/platforms are involved.
- TTS caching (`core/cache.py`) — your template never calls a TTS provider directly; by the
  time `build_backgrounds` runs, `timeline` already has every word's absolute timing.

## What you're responsible for

- Keeping `build_backgrounds` fast and deterministic for the same inputs — it may be called
  once per platform in a single render.
- Not assuming a specific canvas size/aspect ratio — platforms span 1:1, 9:16, and 16:9.
- Returning `BackgroundLayer`s that fully cover every moment of `timeline.total_duration_s`
  (one per scene, spanning each `SceneSpan`, is the simplest correct approach — see
  `faceless.py`/`avatar.py`).
