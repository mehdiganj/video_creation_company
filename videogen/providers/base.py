"""TTS provider interface. Azure is the first (and recommended) implementation; Mock lets the
rest of the pipeline be tested without network access or credentials. Swapping in a future
provider (e.g. ElevenLabs) only means implementing this ABC — nothing downstream changes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class WordTiming:
    text: str
    start_s: float
    duration_s: float

    @property
    def end_s(self) -> float:
        return self.start_s + self.duration_s


@dataclass(frozen=True)
class VoiceInfo:
    name: str          # e.g. "en-US-AndrewMultilingualNeural"
    locale: str        # e.g. "en-US"
    gender: str = ""


@dataclass
class SynthesisResult:
    wav_path: Path
    duration_s: float
    words: list[WordTiming] = field(default_factory=list)


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice: str,
        language: str,
        out_path: Path,
        rate: float = 1.0,
    ) -> SynthesisResult:
        """Render `text` to a mono 16-bit WAV at `out_path` and return word-level timings."""

    @abstractmethod
    def list_voices(self, language: str | None = None) -> list[VoiceInfo]:
        """List available neural voices, optionally filtered to a language ('en' / 'fa')."""
