import pytest
from pydantic import ValidationError

from tests.conftest import FIXTURES_DIR
from videogen.models import VideoProject
from videogen.settings import REPO_ROOT


def test_load_minimal_english_project():
    project = VideoProject.load(FIXTURES_DIR / "project_min_en.yaml")
    assert project.template == "faceless"
    assert project.primary_platform == "instagram"
    assert len(project.scenes) == 2
    assert project.asset_problems(REPO_ROOT) == []


def test_load_minimal_farsi_project():
    project = VideoProject.load(FIXTURES_DIR / "project_min_fa.yaml")
    assert project.language == "fa"
    assert project.captions.style == "none"


def test_rejects_empty_scenes():
    with pytest.raises(ValidationError):
        VideoProject.model_validate(
            {"name": "x", "template": "faceless", "language": "en", "voice": "v", "scenes": []}
        )


def test_rejects_unknown_platform():
    with pytest.raises(ValidationError):
        VideoProject.model_validate(
            {
                "name": "x", "template": "faceless", "language": "en", "voice": "v",
                "platforms": ["myspace"],
                "scenes": [{"text": "hi"}],
            }
        )


def test_image_visual_requires_src():
    with pytest.raises(ValidationError):
        VideoProject.model_validate(
            {
                "name": "x", "template": "faceless", "language": "en", "voice": "v",
                "scenes": [{"text": "hi", "visual": {"kind": "image"}}],
            }
        )


def test_asset_problems_flags_missing_file():
    project = VideoProject.model_validate(
        {
            "name": "x", "template": "faceless", "language": "en", "voice": "v",
            "music": {"track": "assets/music/does_not_exist.mp3"},
            "scenes": [{"text": "hi"}],
        }
    )
    problems = project.asset_problems(REPO_ROOT)
    assert any("does_not_exist.mp3" in p for p in problems)


def test_avatar_template_defaults_to_male_and_resolves():
    project = VideoProject.model_validate(
        {
            "name": "x", "template": "avatar", "language": "en", "voice": "v",
            "scenes": [{"text": "hi"}],
        }
    )
    assert project.avatar == "male"
    assert project.asset_problems(REPO_ROOT) == []


def test_avatar_template_flags_unknown_preset():
    project = VideoProject.model_validate(
        {
            "name": "x", "template": "avatar", "language": "en", "voice": "v", "avatar": "robot",
            "scenes": [{"text": "hi"}],
        }
    )
    problems = project.asset_problems(REPO_ROOT)
    assert any("robot" in p for p in problems)


def test_voice_language_warning():
    project = VideoProject.model_validate(
        {
            "name": "x", "template": "faceless", "language": "fa", "voice": "en-US-AndrewNeural",
            "scenes": [{"text": "hi"}],
        }
    )
    assert project.voice_language_warning() is not None

    project_ok = VideoProject.model_validate(
        {
            "name": "x", "template": "faceless", "language": "fa", "voice": "fa-IR-DilaraNeural",
            "scenes": [{"text": "hi"}],
        }
    )
    assert project_ok.voice_language_warning() is None
