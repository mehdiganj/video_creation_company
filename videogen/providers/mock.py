"""Deterministic, credential-free TTS stand-in. Used by tests, CI, and `videogen preview` /
`--provider mock` so the whole pipeline (timeline, captions, layout, ffmpeg compose, export)
can be exercised without an Azure key or a network call.

Duration and word timings are estimated from character count at a fixed speaking rate — not
accurate to any real voice, but consistent run-to-run, which is what tests need.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from videogen.providers.base import SynthesisResult, TTSProvider, VoiceInfo, WordTiming

SAMPLE_RATE = 48_000
CHARS_PER_SECOND = 15.0   # rough average speaking rate at rate=1.0
TONE_HZ = 220.0           # audible-but-unobtrusive tone so a mock render isn't silent


class MockTTS(TTSProvider):
    def synthesize(
        self,
        text: str,
        voice: str,
        language: str,
        out_path: Path,
        rate: float = 1.0,
    ) -> SynthesisResult:
        words = text.split()
        if not words:
            words = [""]

        total_chars = sum(len(w) for w in words) or 1
        total_duration_s = max(0.3, total_chars / (CHARS_PER_SECOND * rate))

        timings: list[WordTiming] = []
        t = 0.0
        for w in words:
            share = len(w) / total_chars if total_chars else 1.0 / len(words)
            dur = total_duration_s * share
            timings.append(WordTiming(text=w, start_s=t, duration_s=dur))
            t += dur

        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_tone_wav(out_path, total_duration_s)

        return SynthesisResult(wav_path=out_path, duration_s=total_duration_s, words=timings)

    def list_voices(self, language: str | None = None) -> list[VoiceInfo]:
        voices = [
            VoiceInfo(name="mock-en-voice", locale="en-US"),
            VoiceInfo(name="mock-fa-voice", locale="fa-IR"),
        ]
        if language == "en":
            return [v for v in voices if v.locale.startswith("en")]
        if language == "fa":
            return [v for v in voices if v.locale.startswith("fa")]
        return voices


def _write_tone_wav(path: Path, duration_s: float) -> None:
    n_samples = max(1, int(duration_s * SAMPLE_RATE))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        amplitude = 3000
        frames = bytearray()
        for i in range(n_samples):
            # fade in/out 10ms to avoid clicks
            fade = min(1.0, i / (SAMPLE_RATE * 0.01), (n_samples - i) / (SAMPLE_RATE * 0.01))
            sample = int(amplitude * fade * math.sin(2 * math.pi * TONE_HZ * i / SAMPLE_RATE))
            frames += struct.pack("<h", sample)
        wf.writeframes(bytes(frames))
