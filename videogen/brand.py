"""Loads brand.yaml — shared defaults (fonts, colors, caption/text-card sizing, audio levels)
that every project draws on unless its own project YAML overrides a specific field."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from videogen.settings import REPO_ROOT

DEFAULT_BRAND_PATH = REPO_ROOT / "brand.yaml"


@lru_cache(maxsize=1)
def load_brand(path: Path = DEFAULT_BRAND_PATH) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
