"""Lowers a list of BackgroundLayer (one per scene, concatenated) and OverlayLayer (captions,
text-card slides) into a single ffmpeg `filter_complex` and encodes the final MP4. This is the
one place in the codebase that speaks ffmpeg filter syntax — everything upstream only deals in
plain Python layer objects.
"""

from __future__ import annotations

from pathlib import Path

from videogen.core import ffmpeg
from videogen.core.layers import BackgroundLayer, OverlayLayer
from videogen.platforms import Platform

_KEN_BURNS_OVERSCAN = 1.15
_KEN_BURNS_ZOOM_RATE = 0.0008
_KEN_BURNS_MAX_ZOOM = 1.12


def render_platform_video(
    canvas: Platform,
    backgrounds: list[BackgroundLayer],
    overlays: list[OverlayLayer],
    master_audio_path: Path,
    out_video_path: Path,
    work_dir: Path,
    target_duration_s: float,
    preset: str = "medium",
    crf: int = 20,
) -> None:
    if not backgrounds:
        raise ValueError("at least one background layer is required")

    inputs: list[str] = []
    filter_parts: list[str] = []
    next_index = 0

    def add_input(*args: str) -> int:
        nonlocal next_index
        inputs.extend(args)
        idx = next_index
        next_index += 1
        return idx

    bg_labels: list[str] = []
    for i, bg in enumerate(backgrounds):
        duration = max(0.04, bg.span.duration_s)
        label = f"bg{i}"
        if bg.kind == "solid":
            color = bg.color or "#101418"
            filter_parts.append(
                f"color=c={color}:s={canvas.width}x{canvas.height}:d={duration:.3f}:"
                f"r={canvas.fps}[{label}]"
            )
        elif bg.kind == "image":
            idx = add_input("-loop", "1", "-t", f"{duration:.3f}", "-framerate", str(canvas.fps), "-i", str(bg.src))
            if bg.ken_burns:
                ow = int(canvas.width * _KEN_BURNS_OVERSCAN)
                oh = int(canvas.height * _KEN_BURNS_OVERSCAN)
                n_frames = max(1, round(duration * canvas.fps))
                filter_parts.append(
                    f"[{idx}:v]scale={ow}:{oh}:force_original_aspect_ratio=increase,"
                    f"crop={ow}:{oh},"
                    f"zoompan=z='min(zoom+{_KEN_BURNS_ZOOM_RATE},{_KEN_BURNS_MAX_ZOOM})':"
                    f"d={n_frames}:s={canvas.width}x{canvas.height}:fps={canvas.fps}[{label}]"
                )
            else:
                filter_parts.append(
                    f"[{idx}:v]scale={canvas.width}:{canvas.height}:force_original_aspect_ratio=increase,"
                    f"crop={canvas.width}:{canvas.height},setsar=1,fps={canvas.fps}[{label}]"
                )
        elif bg.kind == "video":
            idx = add_input("-stream_loop", "-1", "-i", str(bg.src))
            filter_parts.append(
                f"[{idx}:v]trim=0:{duration:.3f},setpts=PTS-STARTPTS,"
                f"scale={canvas.width}:{canvas.height}:force_original_aspect_ratio=increase,"
                f"crop={canvas.width}:{canvas.height},setsar=1,fps={canvas.fps}[{label}]"
            )
        else:
            raise ValueError(f"unknown background kind: {bg.kind!r}")
        bg_labels.append(f"[{label}]")

    filter_parts.append(f"{''.join(bg_labels)}concat=n={len(bg_labels)}:v=1:a=0[concat]")
    # Hard-pin the concatenated background to the real audio's duration. Individual background
    # segments (solid/image/video, with or without Ken Burns) are each built to their own exact
    # target length, but concatenating several ffmpeg-filter-generated segments has been observed
    # to drift by up to a couple seconds in one direction or the other depending on background
    # kind (caught via a real multi-scene render) — trimming here is a correctness guarantee
    # that doesn't depend on tracking down every filter's exact frame-accounting behavior.
    filter_parts.append(f"[concat]trim=duration={target_duration_s:.3f},setpts=PTS-STARTPTS[base]")

    current = "[base]"
    for k, ov in enumerate(sorted(overlays, key=lambda o: o.z)):
        idx = add_input("-i", str(ov.png_path))
        out_label = f"ov{k}"
        enable = f"between(t,{ov.span.start_s:.3f},{ov.span.end_s:.3f})"
        filter_parts.append(f"{current}[{idx}:v]overlay={ov.x_px}:{ov.y_px}:enable='{enable}'[{out_label}]")
        current = f"[{out_label}]"

    filter_parts.append(f"{current}format=yuv420p[vout]")

    audio_idx = add_input("-i", str(master_audio_path))

    out_video_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        *inputs,
        "-filter_complex", ";".join(filter_parts),
        "-map", "[vout]",
        "-map", f"{audio_idx}:a",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-r", str(canvas.fps),
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-movflags", "+faststart",
        "-shortest",
        str(out_video_path),
    ]
    ffmpeg.run(args, log_path=work_dir / f"{canvas.name}.cmd.txt")
