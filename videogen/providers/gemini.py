"""Gemini TTS (`gemini-3.8-flash-tts`). The main reason to reach for this instead of Azure is
voice cloning: Gemini's voice replication is self-serve via the API (a short reference clip +
a spoken consent statement), while Azure's equivalent (Personal Voice) sits behind Microsoft's
gated Limited Access program and can take a while — or be denied.

Known limitations, flagged rather than hidden (as of Nov 2026, this API is ~2 months old):

- **No real word timing.** Gemini's TTS response carries audio only — no word-boundary events
  like Azure's. This is a confirmed, open feature request on Google's own developer forum, not
  a gap in this integration. Word timings here are therefore ESTIMATED from character count
  (`providers.base.estimate_word_timings` — the same technique `providers/mock.py` uses for its
  synthetic audio), not measured. Captions on Gemini-voiced scenes will drift more than on
  Azure-voiced ones, especially on long or unevenly-paced sentences. A real fix would run a
  transcription pass (e.g. `gemini-3.5-transcribe`) on the generated audio — not implemented
  here because that API's exact request shape wasn't confidently verified enough to ship
  untested; a reasonable next step once it is.
- **Voice replication (`clone_voice` below) is young and has reported instability** (REST 500s)
  on Google's own developer forum as of this writing. If it fails, cloning a voice directly in
  Google AI Studio (https://aistudio.google.com) — Google's own primary documented path for
  this — and pasting the resulting voice id into a project's `voice:` field works the same way
  and may be more reliable right now.
- **`rate` is not applied.** No documented numeric speaking-rate parameter was found for this
  API at the time this was written (Azure's SSML `prosody rate` has no Gemini equivalent here).
  The `rate` argument is accepted (to satisfy the `TTSProvider` interface) but ignored.
- **Pricing is per-token** (input text + output audio tokens), not per-character like Azure —
  `core/estimate.py`'s cost projection for this provider is a rough approximation.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
import wave
from pathlib import Path

from videogen.errors import MissingDependencyError, RenderError
from videogen.providers.base import (
    SynthesisResult,
    TTSProvider,
    VoiceInfo,
    estimate_word_timings,
)

_MODEL = "gemini-3.8-flash-tts"
_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

# A small set of Gemini's stock voices. Not locale-filtered the way Azure's list is — Gemini's
# voices are multilingual by design. A cloned voice's id (from `clone_voice`, or from AI
# Studio) works as a `voice` value too, same as any name in this list.
STOCK_VOICES = ["Kore", "Puck", "Charon", "Fenrir", "Aoede", "Leda", "Orus", "Zephyr"]


class GeminiTTS(TTSProvider):
    def __init__(self, api_key: str) -> None:
        try:
            from google import genai
        except ImportError as e:
            raise MissingDependencyError(
                "google-genai is not installed. Run: pip install -r requirements.txt"
            ) from e
        self._client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})

    def synthesize(
        self,
        text: str,
        voice: str,
        language: str,
        out_path: Path,
        rate: float = 1.0,
    ) -> SynthesisResult:
        try:
            interaction = self._client.interactions.create(
                model=_MODEL,
                input=[{"type": "user_input", "content": [{"type": "text", "text": text}]}],
                response_format={"type": "audio"},
                generation_config={"speech_config": [{"voice": voice}]},
            )
        except Exception as e:  # the SDK's own exception types aren't pinned down here
            raise RenderError(f"Gemini TTS synthesis failed for voice={voice!r}: {e}") from e

        audio_bytes = base64.b64decode(interaction.output_audio.data)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(audio_bytes)  # response is already a RIFF/WAV file per the API docs

        duration_s = _wav_duration(out_path)
        words = estimate_word_timings(text, duration_s)  # see module docstring: not measured
        return SynthesisResult(wav_path=out_path, duration_s=duration_s, words=words)

    def list_voices(self, language: str | None = None) -> list[VoiceInfo]:
        return [VoiceInfo(name=v, locale="multi") for v in STOCK_VOICES]


def clone_voice(api_key: str, source_audio_path: Path, consent_audio_path: Path, display_name: str | None = None) -> str:
    """Replicates a voice from two short recordings (per Google's documented voice-replication
    flow): a clean 10-30s reference clip, and a clip of the same speaker reading the exact
    consent statement Google's AI Studio shows you. Returns a voice id usable directly as a
    project's `voice:` field.

    Implemented as a direct REST call (not the `google-genai` SDK) because the SDK's wrapper
    method for this endpoint wasn't confidently verified — the documented REST request/response
    shape (`POST /v1beta/voices`, `type="replicated"`) was. If this raises, try cloning directly
    in AI Studio instead — see this module's docstring.
    """
    source_b64 = base64.b64encode(Path(source_audio_path).read_bytes()).decode("ascii")
    consent_b64 = base64.b64encode(Path(consent_audio_path).read_bytes()).decode("ascii")

    body = {
        "type": "replicated",
        "source_audio": {"data": source_b64, "mime_type": _wav_mime_type(source_audio_path)},
        "consent_audio": {"data": consent_b64, "mime_type": _wav_mime_type(consent_audio_path)},
    }
    if display_name:
        body["display_name"] = display_name

    request = urllib.request.Request(
        f"{_API_BASE}/voices",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RenderError(
            f"Gemini voice replication failed (HTTP {e.code}): {detail}\n"
            "This endpoint is new and has reported instability — try cloning directly in "
            "Google AI Studio (https://aistudio.google.com) instead; the resulting voice id "
            "works the same way in a project's `voice:` field."
        ) from e

    for key in ("name", "voice_id", "voiceId", "id"):
        if key in payload:
            return str(payload[key])
    raise RenderError(f"Gemini voice replication returned no recognizable voice id: {payload}")


def _wav_mime_type(path: Path) -> str:
    return mimetypes.guess_type(str(path))[0] or "audio/wav"


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())
