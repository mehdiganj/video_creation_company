"""End-to-end: project YAML -> mock TTS -> timeline -> captions -> ffmpeg compose -> export
self-check. Requires a real `ffmpeg`/`ffprobe` on PATH (not mocked) — skips cleanly if absent,
since the ffmpeg filter graph itself is exactly what this test needs to prove works.
"""

import pytest

from tests.conftest import FIXTURES_DIR
from videogen.core import ffmpeg
from videogen.core.pipeline import render
from videogen.models import VideoProject
from videogen.settings import Settings

pytestmark = pytest.mark.skipif(not ffmpeg.is_available(), reason="ffmpeg/ffprobe not installed")


def test_render_minimal_english_faceless_project(tmp_settings: Settings):
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")
    reports = render(project, tmp_settings, provider_name="mock", canvas_scale=0.25, preset="ultrafast")

    assert set(reports) == {"instagram"}
    report = reports["instagram"]
    assert report.path.is_file()
    assert report.video_codec == "h264"
    assert report.audio_codec == "aac"
    assert report.duration_s > 0


def test_render_minimal_farsi_text_card_project(tmp_settings: Settings):
    project = VideoProject.load(FIXTURES_DIR / "project_min_fa.yaml")
    reports = render(project, tmp_settings, provider_name="mock", canvas_scale=0.25, preset="ultrafast")

    report = reports["instagram"]
    assert report.path.is_file()
    assert report.duration_s > 0


def test_render_avatar_project(tmp_settings: Settings):
    from videogen.settings import REPO_ROOT

    project = VideoProject.load(REPO_ROOT / "projects/example_avatar_en.yaml")
    reports = render(project, tmp_settings, provider_name="mock", canvas_scale=0.25, preset="ultrafast")

    report = reports["instagram"]
    assert report.path.is_file()
    assert report.duration_s > 0


def test_render_is_idempotent_via_cache(tmp_settings: Settings):
    """A second render of the same project should reuse cached TTS, not re-synthesize."""
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")
    render(project, tmp_settings, provider_name="mock", canvas_scale=0.25, preset="ultrafast")

    cache_files_before = sorted((tmp_settings.cache_dir / "tts").glob("*.wav"))
    render(project, tmp_settings, provider_name="mock", canvas_scale=0.25, preset="ultrafast")
    cache_files_after = sorted((tmp_settings.cache_dir / "tts").glob("*.wav"))

    assert cache_files_before == cache_files_after
