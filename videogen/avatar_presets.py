"""Named avatar photo presets. Kept in their own tiny module (no imports of `models` or
`templates`) so both can depend on it without a circular import.

These are flat, opaque portrait images — not a layered sprite sheet (no transparent cutout,
no separate mouth/eye layers). The `avatar` template treats one as a scene's full background
with a gentle Ken-Burns-style zoom for a sense of life; it does not lip-sync. Swap in a layered
asset set later (see assets/avatar/README.md) if true mouth animation is ever wanted.
"""

AVATAR_PRESETS: dict[str, str] = {
    "male": "assets/avatar/male.png",
    "female": "assets/avatar/female.png",
}


def resolve_avatar_path(avatar: str) -> str:
    """`avatar` is either a preset name ("male"/"female") or a direct repo-root-relative
    path, as an escape hatch for a custom portrait."""
    return AVATAR_PRESETS.get(avatar, avatar)
