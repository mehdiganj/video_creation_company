"""Per-platform export presets: canvas size, frame rate, and duration caps."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Platform:
    name: str
    width: int
    height: int
    fps: int = 30
    max_duration_s: float | None = None   # hard cap: export.py raises if exceeded
    warn_duration_s: float | None = None  # soft cap: export.py warns but still exports

    @property
    def aspect(self) -> str:
        from math import gcd

        g = gcd(self.width, self.height)
        return f"{self.width // g}:{self.height // g}"


PLATFORMS: dict[str, Platform] = {
    "instagram": Platform("instagram", 1080, 1920, 30, max_duration_s=90),
    "linkedin": Platform("linkedin", 1080, 1080, 30, max_duration_s=600),
    "linkedin_wide": Platform("linkedin_wide", 1920, 1080, 30, max_duration_s=600),
    "youtube": Platform("youtube", 1920, 1080, 30, max_duration_s=None),
    "youtube_shorts": Platform(
        "youtube_shorts", 1080, 1920, 30, max_duration_s=180, warn_duration_s=60
    ),
    "tiktok": Platform("tiktok", 1080, 1920, 30, max_duration_s=600, warn_duration_s=60),
}


def get_platform(name: str) -> Platform:
    try:
        return PLATFORMS[name]
    except KeyError as e:
        valid = ", ".join(sorted(PLATFORMS))
        raise KeyError(f"Unknown platform {name!r}. Valid platforms: {valid}") from e
