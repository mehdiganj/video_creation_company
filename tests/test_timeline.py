import pytest

from tests.conftest import FIXTURES_DIR
from videogen.core.timeline import build_timeline
from videogen.models import VideoProject
from videogen.providers.mock import MockTTS


def _synth_all(project, tmp_path):
    provider = MockTTS()
    results = []
    for i, scene in enumerate(project.scenes):
        results.append(
            provider.synthesize(
                scene.text, project.voice, project.language, tmp_path / f"s{i}.wav", project.rate
            )
        )
    return results


def test_scene_spans_are_contiguous_through_the_pause(tmp_path):
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")
    synth_results = _synth_all(project, tmp_path)

    timeline = build_timeline(project, synth_results)

    assert len(timeline.scene_spans) == 2
    first, second = timeline.scene_spans
    assert first.start_s == 0.0
    # A scene's visual span extends through its trailing pause, right up to the next scene's
    # start — no gap in background coverage between scenes (see timeline.py's docstring on why).
    assert first.end_s == second.start_s

    first_speech_end_s = first.start_s + synth_results[0].duration_s
    assert second.start_s == pytest.approx(first_speech_end_s + project.scenes[0].pause_after_s)
    assert timeline.total_duration_s == second.end_s


def test_words_are_in_increasing_order(tmp_path):
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")
    synth_results = _synth_all(project, tmp_path)
    timeline = build_timeline(project, synth_results)

    starts = [w.start_s for w in timeline.words]
    assert starts == sorted(starts)
    assert len(timeline.words) == sum(len(s.text.split()) for s in project.scenes)


def test_cues_never_cross_scene_boundary(tmp_path):
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")
    synth_results = _synth_all(project, tmp_path)
    timeline = build_timeline(project, synth_results)

    for cue in timeline.cues:
        assert all(w.start_s < timeline.scene_spans[cue.scene_index].end_s for w in cue.words)
        assert len(cue.words) <= project.captions.max_words_per_cue
