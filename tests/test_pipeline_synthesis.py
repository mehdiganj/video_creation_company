import time

from tests.conftest import FIXTURES_DIR
from videogen.core.pipeline import synthesize_scenes
from videogen.models import VideoProject
from videogen.providers.base import SynthesisResult, TTSProvider, VoiceInfo, WordTiming
from videogen.providers.mock import MockTTS
from videogen.settings import Settings


class SlowProvider(TTSProvider):
    """A fake provider that sleeps per call, so we can prove concurrent calls overlap."""

    def __init__(self, delay_s: float = 0.2):
        self.delay_s = delay_s
        self.call_count = 0

    def synthesize(self, text, voice, language, out_path, rate=1.0):
        self.call_count += 1
        time.sleep(self.delay_s)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"RIFF....WAVEfmt ")  # not a real wav; unused by this test
        return SynthesisResult(
            wav_path=out_path, duration_s=1.0, words=[WordTiming(text=text, start_s=0.0, duration_s=1.0)]
        )

    def list_voices(self, language=None):
        return [VoiceInfo(name="slow", locale="en-US")]


def test_synthesize_scenes_preserves_order(tmp_settings: Settings):
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")
    results = synthesize_scenes(project, MockTTS(), "mock", tmp_settings, use_cache=False)

    assert len(results) == len(project.scenes)
    for scene, result in zip(project.scenes, results):
        synthesized_text = " ".join(w.text for w in result.words)
        assert synthesized_text == scene.text


def test_synthesize_scenes_reuses_cache_on_second_call(tmp_settings: Settings):
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")
    provider = MockTTS()

    synthesize_scenes(project, provider, "mock", tmp_settings, use_cache=True)
    cached_wavs_after_first = sorted((tmp_settings.cache_dir / "tts").glob("*.wav"))
    assert len(cached_wavs_after_first) == len(project.scenes)

    synthesize_scenes(project, provider, "mock", tmp_settings, use_cache=True)
    cached_wavs_after_second = sorted((tmp_settings.cache_dir / "tts").glob("*.wav"))
    assert cached_wavs_after_first == cached_wavs_after_second


def test_synthesize_scenes_runs_uncached_calls_concurrently(tmp_settings: Settings):
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")  # 2 scenes
    provider = SlowProvider(delay_s=0.3)

    start = time.monotonic()
    results = synthesize_scenes(
        project, provider, "slow", tmp_settings, use_cache=False, max_concurrency=4
    )
    elapsed = time.monotonic() - start

    assert len(results) == 2
    assert provider.call_count == 2
    # Sequential would take >= 0.6s; concurrent should land close to one 0.3s slot.
    assert elapsed < 0.55, f"expected concurrent execution, took {elapsed:.2f}s"


def test_synthesize_scenes_respects_max_concurrency_of_one(tmp_settings: Settings):
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")  # 2 scenes
    provider = SlowProvider(delay_s=0.2)

    start = time.monotonic()
    synthesize_scenes(project, provider, "slow", tmp_settings, use_cache=False, max_concurrency=1)
    elapsed = time.monotonic() - start

    # With concurrency capped at 1, the two calls must run back-to-back.
    assert elapsed >= 0.38, f"expected serialized execution, took {elapsed:.2f}s"
