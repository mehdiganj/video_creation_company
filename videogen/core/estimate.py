"""Projects TTS cost and duration for a project before rendering, and `videogen estimate` to
surface it — so a render's cost is known up front, and a re-render after an unrelated edit
(captions, music, background) doesn't resynthesize (or re-bill) narration that's already cached.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from videogen.core import cache
from videogen.models import VideoProject
from videogen.providers.base import estimate_duration_s
from videogen.settings import Settings

# Azure: official per-character pay-as-you-go pricing + free (F0) tier.
AZURE_PER_CHAR_USD = 15.0 / 1_000_000
AZURE_FREE_CHARS_PER_MONTH = 500_000

# Gemini bills per-TOKEN (input text + output audio tokens), not per-character — there is no
# exact per-character equivalent. This is a rough order-of-magnitude conversion so the two
# providers are at least directionally comparable; treat it as approximate, not a quote.
GEMINI_PER_CHAR_USD_APPROX = 0.08 / 1_000


@dataclass
class CostEstimate:
    provider: str
    total_scenes: int
    cached_scenes: int
    new_chars: int
    total_chars: int
    estimated_new_duration_s: float
    estimated_new_cost_usd: float
    notes: list[str] = field(default_factory=list)


def estimate_cost(project: VideoProject, settings: Settings, provider_name: str) -> CostEstimate:
    tts_cache_dir = settings.cache_dir

    total_chars = 0
    new_chars = 0
    cached_scenes = 0
    new_duration_s = 0.0

    for scene in project.scenes:
        n_chars = len(scene.text)
        total_chars += n_chars

        key = cache.tts_cache_key(scene.text, project.voice, project.language, project.rate, provider_name)
        if cache.get_cached_tts(tts_cache_dir, key) is not None:
            cached_scenes += 1
        else:
            new_chars += n_chars
            new_duration_s += estimate_duration_s(scene.text, project.rate)

    notes: list[str] = []
    if provider_name == "azure":
        cost_usd = new_chars * AZURE_PER_CHAR_USD
        if new_chars <= AZURE_FREE_CHARS_PER_MONTH:
            notes.append(
                f"within Azure's free tier if this is your only usage this month "
                f"(free tier: {AZURE_FREE_CHARS_PER_MONTH:,} chars/month)"
            )
    elif provider_name == "gemini":
        cost_usd = new_chars * GEMINI_PER_CHAR_USD_APPROX
        notes.append(
            "Gemini bills per-token, not per-character — this is a rough approximation, not a quote"
        )
    else:
        cost_usd = 0.0
        notes.append(f"no pricing data for provider {provider_name!r} (mock is always free)")

    if cached_scenes:
        notes.append(
            f"{cached_scenes}/{len(project.scenes)} scene(s) already cached — free on the next render"
        )

    return CostEstimate(
        provider=provider_name,
        total_scenes=len(project.scenes),
        cached_scenes=cached_scenes,
        new_chars=new_chars,
        total_chars=total_chars,
        estimated_new_duration_s=new_duration_s,
        estimated_new_cost_usd=cost_usd,
        notes=notes,
    )
