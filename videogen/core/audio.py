"""Builds the master audio track: per-scene voice clips concatenated with the same inter-scene
gaps `timeline.py` used to compute word offsets, then (if the project has a music bed) ducked
under the voice and mixed, then loudness-normalized to a social-media-standard level.

This runs once per project, not once per platform — audio doesn't change across export sizes.
"""

from __future__ import annotations

from pathlib import Path

from videogen.core import ffmpeg
from videogen.errors import ConfigError
from videogen.models import VideoProject
from videogen.providers.base import SynthesisResult
from videogen.settings import REPO_ROOT

_FADE_OUT_S = 1.0
_DUCK_THRESHOLD = 0.08
_DUCK_RATIO = 8
_DUCK_ATTACK_MS = 20
_DUCK_RELEASE_MS = 300


def build_voice_track(
    project: VideoProject, synth_results: list[SynthesisResult], work_dir: Path
) -> tuple[Path, float]:
    """Concatenates scene WAVs with `scene.pause_after_s` silence between them — the exact
    gap `timeline.build_timeline` assumes when it computes absolute word offsets. Returns the
    concatenated file's path and its *actual* duration (probed, not estimated), since that's
    what the rest of the pipeline should treat as ground truth."""
    if not synth_results:
        raise ConfigError("cannot build a voice track with zero scenes")

    inputs: list[str] = []
    filter_parts: list[str] = []
    concat_refs: list[str] = []

    for i, synth in enumerate(synth_results):
        inputs += ["-i", str(synth.wav_path)]
        concat_refs.append(f"[{i}:a]")
        is_last = i == len(synth_results) - 1
        if not is_last:
            gap_s = max(0.0, project.scenes[i].pause_after_s)
            if gap_s > 0:
                filter_parts.append(f"anullsrc=r=48000:cl=mono:d={gap_s:.3f}[sil{i}]")
                concat_refs.append(f"[sil{i}]")

    n = len(concat_refs)
    filter_parts.append(f"{''.join(concat_refs)}concat=n={n}:v=0:a=1[voice]")
    filter_complex = ";".join(filter_parts)

    out_path = work_dir / "voice.wav"
    ffmpeg.run(
        [*inputs, "-filter_complex", filter_complex, "-map", "[voice]", str(out_path)],
        log_path=work_dir / "voice.cmd.txt",
    )
    duration_s = _probe_duration(out_path)
    return out_path, duration_s


def build_master_audio(
    project: VideoProject, voice_path: Path, voice_duration_s: float, work_dir: Path, brand: dict
) -> Path:
    """Mixes the voice track with the project's music bed (if any), ducked and loudness
    normalized, into one master WAV that every platform export reuses."""
    out_path = work_dir / "master.wav"
    target_lufs = brand["audio"]["target_lufs"]

    if project.music is None:
        ffmpeg.run(
            [
                "-i", str(voice_path),
                "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
                str(out_path),
            ],
            log_path=work_dir / "master.cmd.txt",
        )
        return out_path

    music_abs_path = REPO_ROOT / project.music.track
    fade_start = max(0.0, voice_duration_s - _FADE_OUT_S)
    gain_db = project.music.gain_db

    music_chain = (
        f"[1:a]volume={gain_db}dB,atrim=0:{voice_duration_s:.3f},"
        f"afade=t=out:st={fade_start:.3f}:d={_FADE_OUT_S}[music_g]"
    )

    if project.music.duck:
        duck_chain = (
            f"[music_g][0:a]sidechaincompress=threshold={_DUCK_THRESHOLD}:ratio={_DUCK_RATIO}:"
            f"attack={_DUCK_ATTACK_MS}:release={_DUCK_RELEASE_MS}[ducked]"
        )
        filter_complex = f"{music_chain};{duck_chain};[ducked][0:a]amix=inputs=2:duration=first[mixed]"
    else:
        filter_complex = f"{music_chain};[music_g][0:a]amix=inputs=2:duration=first[mixed]"

    filter_complex += f";[mixed]loudnorm=I={target_lufs}:TP=-1.5:LRA=11[out]"

    ffmpeg.run(
        [
            "-i", str(voice_path),
            "-stream_loop", "-1", "-i", str(music_abs_path),
            "-filter_complex", filter_complex,
            "-map", "[out]",
            str(out_path),
        ],
        log_path=work_dir / "master.cmd.txt",
    )
    return out_path


def _probe_duration(path: Path) -> float:
    info = ffmpeg.probe(path)
    return float(info["format"]["duration"])
