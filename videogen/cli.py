from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from videogen.core import ffmpeg
from videogen.core.estimate import estimate_cost
from videogen.core.pipeline import DEFAULT_MAX_CONCURRENCY, make_provider
from videogen.core.pipeline import render as run_render
from videogen.errors import VideogenError
from videogen.models import VideoProject
from videogen.platforms import PLATFORMS
from videogen.settings import REPO_ROOT, get_settings

console = Console()
PROVIDER_CHOICES = ["azure", "gemini", "mock"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="videogen", description="Code-driven social video generator.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="Check ffmpeg, fonts, and TTS provider credentials.")

    p_new = sub.add_parser("new", help="Scaffold a new project YAML from a template.")
    p_new.add_argument("name")
    p_new.add_argument("--template", choices=["faceless", "text_card", "avatar"], required=True)
    p_new.add_argument("--language", choices=["en", "fa"], required=True)

    p_validate = sub.add_parser("validate", help="Check a project file's schema and referenced assets.")
    p_validate.add_argument("project")

    p_estimate = sub.add_parser("estimate", help="Project TTS cost/duration before rendering.")
    p_estimate.add_argument("project")
    p_estimate.add_argument("--provider", choices=PROVIDER_CHOICES, default=None)

    p_voices = sub.add_parser("voices", help="List available neural voices for a provider.")
    p_voices.add_argument("--provider", choices=["azure", "gemini"], default="azure")
    p_voices.add_argument("--language", choices=["en", "fa"], default=None)

    p_clone = sub.add_parser(
        "clone-voice",
        help="Clone a voice via Gemini (self-serve, beta) from two short recordings.",
    )
    p_clone.add_argument("--source", required=True, help="10-30s clean reference clip (wav), you speaking normally.")
    p_clone.add_argument(
        "--consent", required=True,
        help="A clip of you speaking the exact consent statement Google AI Studio's voice "
             "replication flow shows you (wav) — this tool does not supply that wording.",
    )
    p_clone.add_argument("--name", default=None, help="Optional display name for the cloned voice.")

    p_preview = sub.add_parser("preview", help="Fast, low-res draft render of a project.")
    p_preview.add_argument("project")
    p_preview.add_argument("--provider", choices=PROVIDER_CHOICES, default=None,
                            help="Defaults to mock; pass --provider azure/gemini for a real-voice preview.")

    p_render = sub.add_parser("render", help="Render a project to one or more platforms.")
    p_render.add_argument("project")
    p_render.add_argument("--platform", choices=sorted(PLATFORMS), default=None, help="Render only this platform.")
    p_render.add_argument("--provider", choices=PROVIDER_CHOICES, default=None)
    p_render.add_argument("--no-cache", action="store_true", help="Ignore the TTS cache and re-synthesize.")
    p_render.add_argument(
        "--concurrency", type=int, default=DEFAULT_MAX_CONCURRENCY,
        help=f"Max concurrent TTS requests for uncached scenes (default {DEFAULT_MAX_CONCURRENCY}).",
    )

    args = parser.parse_args(argv)

    try:
        if args.command == "doctor":
            return _cmd_doctor()
        if args.command == "new":
            return _cmd_new(args.name, args.template, args.language)
        if args.command == "validate":
            return _cmd_validate(args.project)
        if args.command == "estimate":
            return _cmd_estimate(args.project, args.provider)
        if args.command == "voices":
            return _cmd_voices(args.provider, args.language)
        if args.command == "clone-voice":
            return _cmd_clone_voice(args.source, args.consent, args.name)
        if args.command == "preview":
            return _cmd_preview(args.project, provider=args.provider)
        if args.command == "render":
            return _cmd_render(
                args.project, platform=args.platform, provider=args.provider,
                no_cache=args.no_cache, concurrency=args.concurrency,
            )
    except VideogenError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    return 1


def _cmd_doctor() -> int:
    settings = get_settings()
    ok = True

    if ffmpeg.is_available():
        console.print("[green]✓[/green] ffmpeg/ffprobe found on PATH")
    else:
        console.print("[red]✗[/red] ffmpeg/ffprobe NOT found — run: brew install ffmpeg")
        ok = False

    for label, path in [
        ("Inter (Latin) font", REPO_ROOT / "assets/fonts/Inter-Variable.ttf"),
        ("Vazirmatn (Farsi) regular font", REPO_ROOT / "assets/fonts/Vazirmatn-Regular.ttf"),
        ("Vazirmatn (Farsi) bold font", REPO_ROOT / "assets/fonts/Vazirmatn-Bold.ttf"),
        ("Avatar photo (male)", REPO_ROOT / "assets/avatar/male.png"),
        ("Avatar photo (female)", REPO_ROOT / "assets/avatar/female.png"),
    ]:
        if path.is_file():
            console.print(f"[green]✓[/green] {label} present")
        else:
            console.print(f"[red]✗[/red] {label} missing: {path}")
            ok = False

    if settings.has_azure_credentials():
        console.print("[green]✓[/green] AZURE_SPEECH_KEY / AZURE_SPEECH_REGION are set")
    else:
        console.print(
            "[yellow]![/yellow] AZURE_SPEECH_KEY / AZURE_SPEECH_REGION not set "
            "(copy .env.example to .env) — `--provider mock` still works without them"
        )

    try:
        import azure.cognitiveservices.speech  # noqa: F401

        console.print("[green]✓[/green] azure-cognitiveservices-speech importable")
    except ImportError:
        console.print("[red]✗[/red] azure-cognitiveservices-speech not installed — pip install -r requirements.txt")
        ok = False

    if settings.has_gemini_credentials():
        console.print("[green]✓[/green] GEMINI_API_KEY is set")
    else:
        console.print(
            "[yellow]![/yellow] GEMINI_API_KEY not set (copy .env.example to .env) — only "
            "needed for --provider gemini / voice cloning"
        )

    try:
        import google.genai  # noqa: F401

        console.print("[green]✓[/green] google-genai importable")
    except ImportError:
        console.print("[yellow]![/yellow] google-genai not installed — pip install -r requirements.txt "
                       "(only needed for --provider gemini)")

    return 0 if ok else 1


def _cmd_new(name: str, template: str, language: str) -> int:
    template_path = REPO_ROOT / "projects" / "_templates" / f"{template}.yaml"
    out_path = REPO_ROOT / "projects" / f"{name}.yaml"
    if out_path.exists():
        console.print(f"[red]Error:[/red] {out_path} already exists")
        return 1
    text = template_path.read_text(encoding="utf-8")
    text = text.replace("REPLACE_ME_NAME", name).replace("REPLACE_ME_LANGUAGE", language)
    out_path.write_text(text, encoding="utf-8")
    console.print(f"[green]Created[/green] {out_path.relative_to(REPO_ROOT)}")
    console.print("Edit it, then: videogen validate " + str(out_path.relative_to(REPO_ROOT)))
    return 0


def _cmd_validate(project_path: str) -> int:
    project = VideoProject.load(project_path)
    problems = project.asset_problems(REPO_ROOT)
    warning = project.voice_language_warning()

    if not problems and not warning:
        console.print(f"[green]✓[/green] {project.name} is valid — {len(project.scenes)} scene(s), "
                      f"platforms: {', '.join(project.platforms)}")
        return 0

    for p in problems:
        console.print(f"[red]✗[/red] {p}")
    if warning:
        console.print(f"[yellow]![/yellow] {warning}")
    return 1 if problems else 0


def _cmd_estimate(project_path: str, provider: str | None) -> int:
    project = VideoProject.load(project_path)
    settings = get_settings()
    provider_name = provider or settings.videogen_tts_provider
    est = estimate_cost(project, settings, provider_name)

    console.print(f"[bold]{project.name}[/bold] via {est.provider}")
    console.print(f"  scenes: {est.total_scenes} ({est.cached_scenes} already cached)")
    console.print(f"  new characters to synthesize: {est.new_chars:,} (of {est.total_chars:,} total)")
    console.print(f"  estimated new narration: ~{est.estimated_new_duration_s:.1f}s")
    console.print(f"  estimated new cost: ~${est.estimated_new_cost_usd:.4f}")
    for note in est.notes:
        console.print(f"  [dim]note: {note}[/dim]")
    return 0


def _cmd_voices(provider: str, language: str | None) -> int:
    settings = get_settings()
    tts_provider = make_provider(provider, settings)
    for v in tts_provider.list_voices(language):
        console.print(f"{v.name:40s} {v.locale:8s} {v.gender}")
    return 0


def _cmd_clone_voice(source: str, consent: str, name: str | None) -> int:
    from videogen.providers.gemini import clone_voice

    settings = get_settings()
    if not settings.has_gemini_credentials():
        console.print("[red]Error:[/red] GEMINI_API_KEY is not set (copy .env.example to .env)")
        return 1

    console.print("[dim]Replicating voice via Gemini (beta) — this can take a moment...[/dim]")
    voice_id = clone_voice(settings.gemini_api_key, Path(source), Path(consent), name)
    console.print(f"[green]Voice cloned:[/green] {voice_id}")
    console.print(f"Use it by setting `voice: {voice_id}` in a project YAML with a Gemini voice, "
                   "and render with --provider gemini.")
    return 0


def _cmd_preview(project_path: str, provider: str | None) -> int:
    project = VideoProject.load(project_path)
    settings = get_settings()
    run_render(
        project=project,
        settings=settings,
        platforms=[project.primary_platform],
        provider_name=provider or "mock",
        canvas_scale=0.45,
        preset="ultrafast",
        crf=30,
        on_progress=lambda msg: console.print(f"[dim]{msg}[/dim]"),
    )
    console.print(f"[green]Preview written to:[/green] out/{project.name}/{project.primary_platform}.mp4")
    return 0


def _cmd_render(
    project_path: str, platform: str | None, provider: str | None, no_cache: bool, concurrency: int
) -> int:
    project = VideoProject.load(project_path)
    settings = get_settings()
    reports = run_render(
        project=project,
        settings=settings,
        platforms=[platform] if platform else None,
        provider_name=provider,
        use_cache=not no_cache,
        max_concurrency=concurrency,
        on_progress=lambda msg: console.print(f"[dim]{msg}[/dim]"),
    )
    for name, report in reports.items():
        console.print(
            f"[green]{name}[/green]: {report.path.relative_to(REPO_ROOT)} "
            f"({report.width}x{report.height}, {report.duration_s:.1f}s)"
        )
        for w in report.warnings:
            console.print(f"  [yellow]![/yellow] {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
