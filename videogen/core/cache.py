"""Content-hash cache for TTS synthesis results.

Azure's free tier is metered (~0.5M characters/month). Editing a caption color or a background
image must never trigger a re-synthesis of unchanged narration — so every TTS call is cached on
a hash of exactly the inputs that affect its output.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from videogen.providers.base import SynthesisResult, WordTiming


def tts_cache_key(text: str, voice: str, language: str, rate: float, provider_name: str) -> str:
    payload = f"{provider_name}|{language}|{voice}|{rate:.3f}|{text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def cache_paths(cache_dir: Path, key: str) -> tuple[Path, Path]:
    """Where a cached TTS result for `key` lives: (wav_path, metadata_json_path). Pass
    `wav_path` directly as the TTS provider's `out_path` to synthesize straight into the
    cache slot — `put_cached_tts` then only has to write the metadata, not copy a file."""
    tts_dir = cache_dir / "tts"
    return tts_dir / f"{key}.wav", tts_dir / f"{key}.json"


def get_cached_tts(cache_dir: Path, key: str) -> SynthesisResult | None:
    wav_path, meta_path = cache_paths(cache_dir, key)
    if not (wav_path.is_file() and meta_path.is_file()):
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    words = [WordTiming(**w) for w in meta["words"]]
    return SynthesisResult(wav_path=wav_path, duration_s=meta["duration_s"], words=words)


def put_cached_tts(cache_dir: Path, key: str, result: SynthesisResult) -> SynthesisResult:
    wav_path, meta_path = cache_paths(cache_dir, key)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    if result.wav_path != wav_path:
        wav_path.write_bytes(Path(result.wav_path).read_bytes())
    meta = {
        "duration_s": result.duration_s,
        "words": [
            {"text": w.text, "start_s": w.start_s, "duration_s": w.duration_s}
            for w in result.words
        ],
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return SynthesisResult(wav_path=wav_path, duration_s=result.duration_s, words=result.words)
