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


def test_scene_offsets_include_pause(tmp_path):
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")
    synth_results = _synth_all(project, tmp_path)

    timeline = build_timeline(project, synth_results)

    assert len(timeline.scene_spans) == 2
    first, second = timeline.scene_spans
    assert first.start_s == 0.0
    # second scene must start after the first scene's audio PLUS its pause_after_s
    assert second.start_s == pytest.approx(first.end_s + project.scenes[0].pause_after_s)
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
