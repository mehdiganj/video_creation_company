"""The single rendering flow every template shares: load -> TTS -> timeline -> master audio
(all platform-independent, computed once) -> per platform: backgrounds + captions + template
overlays -> ffmpeg compose -> export self-check.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from videogen.brand import load_brand
from videogen.core import audio, cache, captions, compose, ffmpeg
from videogen.core.export import ExportReport, validate_export
from videogen.core.timeline import build_timeline
from videogen.errors import ConfigError, MissingDependencyError
from videogen.models import VideoProject
from videogen.platforms import get_platform
from videogen.providers.azure import AzureSpeechTTS
from videogen.providers.base import SynthesisResult, TTSProvider
from videogen.providers.gemini import GeminiTTS
from videogen.providers.mock import MockTTS
from videogen.settings import REPO_ROOT, Settings
from videogen.templates import get_template

ProgressFn = Callable[[str], None]
DEFAULT_MAX_CONCURRENCY = 4


def make_provider(provider_name: str, settings: Settings) -> TTSProvider:
    if provider_name == "mock":
        return MockTTS()
    if provider_name == "azure":
        if not settings.has_azure_credentials():
            raise MissingDependencyError(
                "AZURE_SPEECH_KEY / AZURE_SPEECH_REGION are not set. Copy .env.example to .env "
                "and fill them in, or pass --provider mock to render without real TTS."
            )
        return AzureSpeechTTS(settings.azure_speech_key, settings.azure_speech_region)
    if provider_name == "gemini":
        if not settings.has_gemini_credentials():
            raise MissingDependencyError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in, or pass "
                "--provider mock to render without real TTS."
            )
        return GeminiTTS(settings.gemini_api_key)
    raise ConfigError(f"Unknown TTS provider: {provider_name!r} (expected 'azure', 'gemini', or 'mock')")


def synthesize_scenes(
    project: VideoProject,
    provider: TTSProvider,
    provider_name: str,
    settings: Settings,
    use_cache: bool = True,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
) -> list[SynthesisResult]:
    """Synthesizes every scene's narration, reusing the TTS cache where possible. Cache misses
    are synthesized concurrently (each is an independent, blocking network call to the TTS
    provider) — the biggest lever on wall-clock render time for multi-scene projects, since
    Azure/Gemini calls are dominated by network round-trip latency, not local compute.
    `max_concurrency` caps how many requests are in flight at once, to stay well under a
    provider's rate limits."""
    tts_cache_dir = settings.cache_dir
    keys = [
        cache.tts_cache_key(scene.text, project.voice, project.language, project.rate, provider_name)
        for scene in project.scenes
    ]
    results: list[SynthesisResult | None] = [None] * len(project.scenes)
    to_synthesize: list[int] = []

    for i, key in enumerate(keys):
        cached = cache.get_cached_tts(tts_cache_dir, key) if use_cache else None
        if cached is not None:
            results[i] = cached
        else:
            to_synthesize.append(i)

    def _synth_one(i: int) -> SynthesisResult:
        scene = project.scenes[i]
        wav_path, _ = cache.cache_paths(tts_cache_dir, keys[i])
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        result = provider.synthesize(
            text=scene.text,
            voice=project.voice,
            language=project.language,
            out_path=wav_path,
            rate=project.rate,
        )
        return cache.put_cached_tts(tts_cache_dir, keys[i], result)

    if to_synthesize:
        workers = max(1, min(max_concurrency, len(to_synthesize)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_index = {pool.submit(_synth_one, i): i for i in to_synthesize}
            for future in as_completed(future_to_index):
                i = future_to_index[future]
                results[i] = future.result()  # re-raises here if _synth_one failed

    return results  # type: ignore[return-value]  # every slot was filled above


def render(
    project: VideoProject,
    settings: Settings,
    platforms: list[str] | None = None,
    provider_name: str | None = None,
    use_cache: bool = True,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    canvas_scale: float = 1.0,
    preset: str = "medium",
    crf: int = 20,
    on_progress: ProgressFn = lambda msg: None,
) -> dict[str, ExportReport]:
    if not ffmpeg.is_available():
        raise MissingDependencyError(
            "ffmpeg/ffprobe not found on PATH. Install with: brew install ffmpeg"
        )

    problems = project.asset_problems(REPO_ROOT)
    if problems:
        raise ConfigError("Project references missing files:\n  " + "\n  ".join(problems))

    warning = project.voice_language_warning()
    if warning:
        on_progress(f"warning: {warning}")

    provider_name = provider_name or settings.videogen_tts_provider
    provider = make_provider(provider_name, settings)
    brand = load_brand()
    template = get_template(project.template)

    out_root = settings.out_dir / project.name
    work_dir = out_root / "_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    on_progress(f"synthesizing {len(project.scenes)} scene(s) via {provider_name}...")
    synth_results = synthesize_scenes(
        project, provider, provider_name, settings, use_cache, max_concurrency
    )

    timeline = build_timeline(project, synth_results)
    on_progress(f"timeline built: {timeline.total_duration_s:.1f}s, {len(timeline.cues)} caption cue(s)")

    on_progress("building voice track...")
    voice_path, voice_duration_s = audio.build_voice_track(project, synth_results, work_dir)

    on_progress("mixing master audio...")
    master_audio_path = audio.build_master_audio(project, voice_path, voice_duration_s, work_dir, brand)

    target_platforms = platforms or project.platforms
    reports: dict[str, ExportReport] = {}

    for platform_name in target_platforms:
        canvas = get_platform(platform_name)
        if canvas_scale != 1.0:
            canvas = _scaled_platform(canvas, canvas_scale)

        on_progress(f"[{platform_name}] building visuals...")
        backgrounds = template.build_backgrounds(project, timeline, canvas)

        platform_work_dir = work_dir / platform_name
        caption_overlays = captions.render_caption_overlays(
            cues=timeline.cues,
            language=project.language,
            style=project.captions,
            canvas=canvas,
            brand=brand,
            out_dir=platform_work_dir / "captions",
        )
        extra_overlays = template.build_extra_overlays(
            project, timeline, canvas, brand, platform_work_dir
        )

        out_video_path = out_root / f"{platform_name}.mp4"
        on_progress(f"[{platform_name}] encoding {canvas.width}x{canvas.height}...")
        compose.render_platform_video(
            canvas=canvas,
            backgrounds=backgrounds,
            overlays=[*caption_overlays, *extra_overlays],
            master_audio_path=master_audio_path,
            out_video_path=out_video_path,
            work_dir=platform_work_dir,
            preset=preset,
            crf=crf,
        )

        on_progress(f"[{platform_name}] validating output...")
        report = validate_export(out_video_path, canvas)
        for w in report.warnings:
            on_progress(f"[{platform_name}] warning: {w}")
        reports[platform_name] = report

    return reports


def _scaled_platform(platform, scale: float):
    from dataclasses import replace

    return replace(
        platform,
        width=max(16, round(platform.width * scale / 2) * 2),
        height=max(16, round(platform.height * scale / 2) * 2),
    )
