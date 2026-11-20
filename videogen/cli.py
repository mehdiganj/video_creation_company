from __future__ import annotations

import argparse
import sys

from rich.console import Console

from videogen.core import ffmpeg
from videogen.core.pipeline import make_provider
from videogen.core.pipeline import render as run_render
from videogen.errors import VideogenError
from videogen.models import VideoProject
from videogen.platforms import PLATFORMS
from videogen.settings import REPO_ROOT, get_settings

console = Console()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="videogen", description="Code-driven social video generator.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="Check ffmpeg, fonts, and Azure credentials.")

    p_new = sub.add_parser("new", help="Scaffold a new project YAML from a template.")
    p_new.add_argument("name")
    p_new.add_argument("--template", choices=["faceless", "text_card", "avatar"], required=True)
    p_new.add_argument("--language", choices=["en", "fa"], required=True)

    p_validate = sub.add_parser("validate", help="Check a project file's schema and referenced assets.")
    p_validate.add_argument("project")

    p_voices = sub.add_parser("voices", help="List available Azure neural voices.")
    p_voices.add_argument("--language", choices=["en", "fa"], default=None)

    p_preview = sub.add_parser("preview", help="Fast, low-res draft render of a project.")
    p_preview.add_argument("project")
    p_preview.add_argument("--real-tts", action="store_true", help="Use real Azure TTS instead of the mock provider.")

    p_render = sub.add_parser("render", help="Render a project to one or more platforms.")
    p_render.add_argument("project")
    p_render.add_argument("--platform", choices=sorted(PLATFORMS), default=None, help="Render only this platform.")
    p_render.add_argument("--provider", choices=["azure", "mock"], default=None)
    p_render.add_argument("--no-cache", action="store_true", help="Ignore the TTS cache and re-synthesize.")

    args = parser.parse_args(argv)

    try:
        if args.command == "doctor":
            return _cmd_doctor()
        if args.command == "new":
            return _cmd_new(args.name, args.template, args.language)
        if args.command == "validate":
            return _cmd_validate(args.project)
        if args.command == "voices":
            return _cmd_voices(args.language)
        if args.command == "preview":
            return _cmd_preview(args.project, real_tts=args.real_tts)
        if args.command == "render":
            return _cmd_render(args.project, platform=args.platform, provider=args.provider, no_cache=args.no_cache)
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


def _cmd_voices(language: str | None) -> int:
    settings = get_settings()
    provider = make_provider("azure", settings)
    for v in provider.list_voices(language):
        console.print(f"{v.name:40s} {v.locale:8s} {v.gender}")
    return 0


def _cmd_preview(project_path: str, real_tts: bool) -> int:
    project = VideoProject.load(project_path)
    settings = get_settings()
    run_render(
        project=project,
        settings=settings,
        platforms=[project.primary_platform],
        provider_name="azure" if real_tts else "mock",
        canvas_scale=0.45,
        preset="ultrafast",
        crf=30,
        on_progress=lambda msg: console.print(f"[dim]{msg}[/dim]"),
    )
    console.print(f"[green]Preview written to:[/green] out/{project.name}/{project.primary_platform}.mp4")
    return 0


def _cmd_render(project_path: str, platform: str | None, provider: str | None, no_cache: bool) -> int:
    project = VideoProject.load(project_path)
    settings = get_settings()
    reports = run_render(
        project=project,
        settings=settings,
        platforms=[platform] if platform else None,
        provider_name=provider,
        use_cache=not no_cache,
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
