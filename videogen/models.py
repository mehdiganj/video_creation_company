"""Project schema. A VideoProject YAML file is the single source of truth for one video:
its script (as scenes), language/voice, visuals, captions, music, and target platforms.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from videogen.avatar_presets import resolve_avatar_path
from videogen.platforms import PLATFORMS

Language = Literal["en", "fa"]
TemplateName = Literal["faceless", "text_card", "avatar"]
ReframeMode = Literal["native", "pad", "crop"]


class Visual(BaseModel):
    kind: Literal["solid", "image", "video"] = "solid"
    color: str | None = None            # for kind == "solid", e.g. "#101418"
    src: str | None = None              # for kind == "image" / "video", repo-root-relative path
    motion: Literal["none", "ken_burns"] = "none"

    @model_validator(mode="after")
    def _require_fields_for_kind(self) -> Visual:
        if self.kind == "solid" and not self.color:
            self.color = "#101418"
        if self.kind in ("image", "video") and not self.src:
            raise ValueError(f"visual.kind == {self.kind!r} requires a 'src' path")
        return self


class Scene(BaseModel):
    text: str
    visual: Visual | None = None
    pause_after_s: float = 0.4

    @field_validator("text")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("scene.text must not be empty")
        return v


class MusicSpec(BaseModel):
    track: str                     # repo-root-relative path, e.g. assets/music/lofi_calm.mp3
    gain_db: float = -22.0
    duck: bool = True


class CaptionStyle(BaseModel):
    style: Literal["karaoke", "block", "none"] = "karaoke"
    max_words_per_cue: int = 4
    position: float = Field(default=0.78, ge=0.0, le=1.0)
    # Calibrated so a typical 4-word English/Farsi cue fits on one line at the default safe
    # margin (see core/captions.py) — a cue that doesn't fit falls back to a wrapped block
    # (no per-word highlight), so this errs on the smaller side rather than overflowing.
    font_size_ratio: float = Field(default=0.04, gt=0.0, lt=0.5)
    highlight_color: str | None = None  # None -> falls back to brand.yaml colors.accent


class VideoProject(BaseModel):
    name: str
    template: TemplateName
    language: Language
    voice: str
    rate: float = Field(default=1.0, gt=0.3, lt=2.5)

    # Only meaningful when template == "avatar": a preset name ("male" / "female", see
    # assets/avatar/) or a direct repo-root-relative path to a custom portrait image.
    avatar: str = "male"

    platforms: list[str] = Field(default_factory=lambda: ["instagram"])
    primary_platform: str | None = None
    reframe: dict[str, ReframeMode] = Field(default_factory=dict)

    music: MusicSpec | None = None
    captions: CaptionStyle = Field(default_factory=CaptionStyle)
    scenes: list[Scene]

    @field_validator("scenes")
    @classmethod
    def _at_least_one_scene(cls, v: list[Scene]) -> list[Scene]:
        if not v:
            raise ValueError("project must have at least one scene")
        return v

    @field_validator("platforms")
    @classmethod
    def _known_platforms(cls, v: list[str]) -> list[str]:
        unknown = [p for p in v if p not in PLATFORMS]
        if unknown:
            valid = ", ".join(sorted(PLATFORMS))
            raise ValueError(f"unknown platform(s) {unknown}; valid platforms: {valid}")
        if not v:
            raise ValueError("project must list at least one platform")
        return v

    @model_validator(mode="after")
    def _default_primary_platform(self) -> VideoProject:
        if self.primary_platform is None:
            self.primary_platform = self.platforms[0]
        elif self.primary_platform not in self.platforms:
            raise ValueError("primary_platform must be one of the project's platforms")
        return self

    def reframe_for(self, platform_name: str) -> ReframeMode:
        return self.reframe.get(platform_name, "native")

    def voice_language_warning(self) -> str | None:
        """Soft check only — Azure multilingual voices can legitimately speak another
        language than their name implies, so this never raises, just flags for review."""
        locale_prefix = {"en": "en-", "fa": "fa-"}[self.language]
        if self.voice.startswith(locale_prefix) or "Multilingual" in self.voice:
            return None
        return (
            f"voice '{self.voice}' does not look like a '{self.language}' voice "
            f"(expected it to start with {locale_prefix!r} or contain 'Multilingual'). "
            "This is only a warning — double-check with `videogen voices`."
        )

    def asset_problems(self, repo_root: Path) -> list[str]:
        """Check that every referenced file on disk actually exists. Returns human-readable
        problem strings (empty list == clean). Deliberately not a pydantic validator: this
        does I/O and should run explicitly (CLI `validate`, or first thing in the pipeline),
        not implicitly on every model parse."""
        problems: list[str] = []
        if self.music and not (repo_root / self.music.track).is_file():
            problems.append(f"music.track not found: {self.music.track}")
        if self.template == "avatar":
            avatar_path = resolve_avatar_path(self.avatar)
            if not (repo_root / avatar_path).is_file():
                problems.append(f"avatar {self.avatar!r} not found: {avatar_path}")
        for i, scene in enumerate(self.scenes):
            v = scene.visual
            if v and v.kind in ("image", "video") and v.src and not (repo_root / v.src).is_file():
                problems.append(f"scenes[{i}].visual.src not found: {v.src}")
        return problems

    @classmethod
    def load(cls, path: str | Path) -> VideoProject:
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)
