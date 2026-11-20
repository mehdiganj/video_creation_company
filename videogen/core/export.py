"""Self-checks a rendered MP4 with ffprobe before calling the render done — catches a wrong
canvas size, a missing audio stream, or an over-length Reel before Mehdi uploads it and finds
out from the platform instead."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from videogen.core import ffmpeg
from videogen.errors import RenderError
from videogen.platforms import Platform


@dataclass
class ExportReport:
    path: Path
    width: int
    height: int
    duration_s: float
    video_codec: str
    audio_codec: str
    warnings: list[str] = field(default_factory=list)


def validate_export(path: Path, platform: Platform) -> ExportReport:
    info = ffmpeg.probe(path)
    streams = info.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if video_stream is None:
        raise RenderError(f"{path}: no video stream in output — something is wrong upstream")
    if audio_stream is None:
        raise RenderError(f"{path}: no audio stream in output — something is wrong upstream")

    width, height = int(video_stream["width"]), int(video_stream["height"])
    duration_s = float(info["format"]["duration"])

    if (width, height) != (platform.width, platform.height):
        raise RenderError(
            f"{path}: rendered at {width}x{height}, expected {platform.width}x{platform.height} "
            f"for platform {platform.name!r}"
        )

    if platform.max_duration_s is not None and duration_s > platform.max_duration_s + 0.5:
        raise RenderError(
            f"{path}: duration {duration_s:.1f}s exceeds {platform.name}'s hard limit of "
            f"{platform.max_duration_s:.0f}s — trim the script or split into multiple videos"
        )

    warnings: list[str] = []
    if platform.warn_duration_s is not None and duration_s > platform.warn_duration_s:
        warnings.append(
            f"{duration_s:.1f}s is longer than {platform.name}'s recommended "
            f"{platform.warn_duration_s:.0f}s — it will still upload, but may be deprioritized"
        )

    return ExportReport(
        path=path,
        width=width,
        height=height,
        duration_s=duration_s,
        video_codec=video_stream.get("codec_name", "?"),
        audio_codec=audio_stream.get("codec_name", "?"),
        warnings=warnings,
    )
