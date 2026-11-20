"""Runtime settings loaded from .env / environment variables. No secret value is ever logged."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    azure_speech_key: str | None = Field(default=None, alias="AZURE_SPEECH_KEY")
    azure_speech_region: str | None = Field(default=None, alias="AZURE_SPEECH_REGION")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")

    videogen_tts_provider: str = Field(default="azure", alias="VIDEOGEN_TTS_PROVIDER")
    videogen_out_dir: str = Field(default="out", alias="VIDEOGEN_OUT_DIR")
    videogen_cache_dir: str = Field(default=".cache", alias="VIDEOGEN_CACHE_DIR")

    @property
    def out_dir(self) -> Path:
        p = Path(self.videogen_out_dir)
        return p if p.is_absolute() else REPO_ROOT / p

    @property
    def cache_dir(self) -> Path:
        p = Path(self.videogen_cache_dir)
        return p if p.is_absolute() else REPO_ROOT / p

    def has_azure_credentials(self) -> bool:
        return _is_filled_in(self.azure_speech_key) and _is_filled_in(self.azure_speech_region)

    def has_gemini_credentials(self) -> bool:
        return _is_filled_in(self.gemini_api_key)


def _is_filled_in(value: str | None) -> bool:
    """True if `value` is non-empty and isn't still the literal placeholder text from
    .env.example (copying .env.example to .env without editing it is an easy trap — `doctor`
    should say "not set", not falsely claim credentials are ready)."""
    return bool(value) and "your_" not in value and "_here" not in value


def get_settings() -> Settings:
    return Settings()
