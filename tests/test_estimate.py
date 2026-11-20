from tests.conftest import FIXTURES_DIR
from videogen.core.estimate import AZURE_PER_CHAR_USD, estimate_cost
from videogen.core.pipeline import synthesize_scenes
from videogen.models import VideoProject
from videogen.providers.mock import MockTTS
from videogen.settings import Settings


def test_estimate_counts_all_scenes_as_new_when_uncached(tmp_settings: Settings):
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")
    est = estimate_cost(project, tmp_settings, "azure")

    expected_chars = sum(len(s.text) for s in project.scenes)
    assert est.total_chars == expected_chars
    assert est.new_chars == expected_chars
    assert est.cached_scenes == 0
    assert est.estimated_new_cost_usd == expected_chars * AZURE_PER_CHAR_USD
    assert est.estimated_new_duration_s > 0


def test_estimate_excludes_already_cached_scenes(tmp_settings: Settings):
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")
    # Prime the cache for provider "azure" specifically — cache keys are provider-scoped.
    synthesize_scenes(project, MockTTS(), "azure", tmp_settings, use_cache=True)

    est = estimate_cost(project, tmp_settings, "azure")
    assert est.cached_scenes == len(project.scenes)
    assert est.new_chars == 0
    assert est.estimated_new_cost_usd == 0.0


def test_estimate_mock_provider_is_free(tmp_settings: Settings):
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")
    est = estimate_cost(project, tmp_settings, "mock")
    assert est.estimated_new_cost_usd == 0.0


def test_estimate_gemini_uses_approximate_pricing_note(tmp_settings: Settings):
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")
    est = estimate_cost(project, tmp_settings, "gemini")
    assert est.estimated_new_cost_usd > 0
    assert any("approximation" in note for note in est.notes)
