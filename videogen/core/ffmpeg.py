"""Thin, explicit wrapper over the `ffmpeg`/`ffprobe` binaries via subprocess.

Deliberately not using the `ffmpeg-python` package: filter graphs in this project get
conditional and many-layered, and a plain list of CLI args stays easy to log, copy-paste,
and debug by hand. Every invocation can be dumped to a `.cmd.txt` file for exactly that reason.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from videogen.errors import MissingDependencyError, RenderError

_INSTALL_HINT = "Install it with: brew install ffmpeg"


def ffmpeg_path() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise MissingDependencyError(f"ffmpeg was not found on PATH. {_INSTALL_HINT}")
    return path


def ffprobe_path() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise MissingDependencyError(f"ffprobe was not found on PATH. {_INSTALL_HINT}")
    return path


def is_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def run(args: list[str], log_path: Path | None = None) -> subprocess.CompletedProcess:
    """Run ffmpeg with `args` (excluding the binary itself, which is resolved here).
    `-y` (overwrite) and `-hide_banner` are added automatically. Always captures output;
    raises RenderError with the stderr tail on a non-zero exit."""
    full_cmd = [ffmpeg_path(), "-hide_banner", "-y", *args]

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(" \\\n  ".join(full_cmd) + "\n", encoding="utf-8")

    proc = subprocess.run(full_cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-25:])
        raise RenderError(
            f"ffmpeg exited with code {proc.returncode}.\n"
            f"Command logged to: {log_path}\n"
            f"--- ffmpeg stderr (tail) ---\n{tail}"
        )
    return proc


def probe(path: Path) -> dict:
    """Return ffprobe's JSON report (format + streams) for a media file."""
    cmd = [
        ffprobe_path(),
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RenderError(f"ffprobe failed on {path}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)
