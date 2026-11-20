from pathlib import Path

import pytest

from videogen.settings import Settings

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_settings(tmp_path, monkeypatch) -> Settings:
    monkeypatch.setenv("VIDEOGEN_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("VIDEOGEN_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    return Settings(_env_file=None)
