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


CHARS_PER_SECOND = 15.0  # rough average speaking rate at rate=1.0, used only to ESTIMATE timing


def estimate_word_timings(text: str, total_duration_s: float) -> list[WordTiming]:
    """Distributes `total_duration_s` across `text`'s words proportionally to each word's
    character length. Used by providers whose API doesn't return real word-boundary timing
    (`providers/mock.py`, `providers/gemini.py`) — an approximation, not a measurement. Prefer
    a provider that returns real timings (Azure) when caption sync accuracy matters most."""
    words = text.split() or [""]
    total_chars = sum(len(w) for w in words) or 1

    timings: list[WordTiming] = []
    t = 0.0
    for w in words:
        share = len(w) / total_chars if total_chars else 1.0 / len(words)
        dur = total_duration_s * share
        timings.append(WordTiming(text=w, start_s=t, duration_s=dur))
        t += dur
    return timings


def estimate_duration_s(text: str, rate: float = 1.0) -> float:
    """Rough speaking-duration estimate from character count — used both by the mock provider
    (to fabricate silence of a plausible length) and by `core/estimate.py` (to project a cost
    estimate before any real synthesis happens)."""
    words = text.split()
    total_chars = sum(len(w) for w in words) or 1
    return max(0.3, total_chars / (CHARS_PER_SECOND * rate))
