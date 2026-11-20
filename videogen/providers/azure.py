"""Azure AI Speech (Cognitive Services) neural TTS. Produces a 48kHz mono 16-bit WAV plus
word-level timings (from the SDK's word-boundary events) that drive caption sync.

No lip-sync/viseme data is requested — this project has no avatar, only captions need timing.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from videogen.errors import MissingDependencyError, RenderError
from videogen.providers.base import SynthesisResult, TTSProvider, VoiceInfo, WordTiming

_LOCALE_BY_LANGUAGE = {"en": "en-US", "fa": "fa-IR"}
TICKS_PER_SECOND = 10_000_000  # Azure reports offsets/durations in 100-nanosecond ticks


class AzureSpeechTTS(TTSProvider):
    def __init__(self, speech_key: str, speech_region: str) -> None:
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError as e:
            raise MissingDependencyError(
                "azure-cognitiveservices-speech is not installed. "
                "Run: pip install -r requirements.txt"
            ) from e
        self._speechsdk = speechsdk
        self._speech_key = speech_key
        self._speech_region = speech_region

    def _speech_config(self):
        speechsdk = self._speechsdk
        config = speechsdk.SpeechConfig(subscription=self._speech_key, region=self._speech_region)
        config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm
        )
        return config

    def synthesize(
        self,
        text: str,
        voice: str,
        language: str,
        out_path: Path,
        rate: float = 1.0,
    ) -> SynthesisResult:
        speechsdk = self._speechsdk
        out_path.parent.mkdir(parents=True, exist_ok=True)

        speech_config = self._speech_config()
        audio_config = speechsdk.audio.AudioOutputConfig(filename=str(out_path))
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config
        )

        words: list[WordTiming] = []

        def _on_word_boundary(evt) -> None:
            boundary_type = getattr(evt, "boundary_type", None)
            # Compare against the enum member, not its str() — SpeechSynthesisBoundaryType.Word
            # stringifies as "SpeechSynthesisBoundaryType.Word", not "Word", so a string
            # comparison here silently filtered out every event (verified against SDK 1.53.1).
            if boundary_type is not None and boundary_type != speechsdk.SpeechSynthesisBoundaryType.Word:
                return
            start_s = evt.audio_offset / TICKS_PER_SECOND
            duration = getattr(evt, "duration", None)
            if duration is not None and hasattr(duration, "total_seconds"):
                duration_s = duration.total_seconds()
            else:
                duration_s = getattr(evt, "duration_in_ticks", 0) / TICKS_PER_SECOND
            words.append(WordTiming(text=evt.text, start_s=start_s, duration_s=duration_s))

        synthesizer.synthesis_word_boundary.connect(_on_word_boundary)

        locale = _LOCALE_BY_LANGUAGE.get(language, "en-US")
        ssml = _build_ssml(text=text, voice=voice, locale=locale, rate=rate)

        result = synthesizer.speak_ssml_async(ssml).get()

        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            details = result.cancellation_details
            reason = details.reason if details else "unknown"
            error_detail = details.error_details if details else ""
            raise RenderError(
                f"Azure TTS synthesis failed for voice={voice!r}: {reason} {error_detail}"
            )

        duration_s = words[-1].end_s if words else _probe_wav_duration(out_path)
        return SynthesisResult(wav_path=out_path, duration_s=duration_s, words=words)

    def list_voices(self, language: str | None = None) -> list[VoiceInfo]:
        speechsdk = self._speechsdk
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=self._speech_config())
        result = synthesizer.get_voices_async().get()
        if result.reason != speechsdk.ResultReason.VoicesListRetrieved:
            raise RenderError(f"Could not list Azure voices: {result.reason}")

        locale_prefix = _LOCALE_BY_LANGUAGE.get(language, "")[:2] if language else None
        voices = []
        for v in result.voices:
            if locale_prefix and not v.locale.lower().startswith(locale_prefix):
                continue
            voices.append(VoiceInfo(name=v.short_name, locale=v.locale, gender=str(v.gender)))
        return voices


def _build_ssml(text: str, voice: str, locale: str, rate: float) -> str:
    rate_pct = round((rate - 1.0) * 100)
    sign = "+" if rate_pct >= 0 else ""
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{locale}">'
        f'<voice name="{escape(voice)}">'
        f'<prosody rate="{sign}{rate_pct}%">{escape(text)}</prosody>'
        f"</voice></speak>"
    )


def _probe_wav_duration(path: Path) -> float:
    import wave

    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())
