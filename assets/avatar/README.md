# Avatar photos

| File | Preset name | Used for |
|---|---|---|
| `male.png` | `male` | `avatar` template, `avatar: male` (default) |
| `female.png` | `female` | `avatar` template, `avatar: female` |

Both are flat, opaque 1254x1254 portrait illustrations — not a layered sprite sheet. The
`avatar` template (`videogen/templates/avatar.py`) uses one as the scene's full background with
a slow Ken-Burns-style zoom for a sense of life. There's no lip-sync or mouth animation: these
images have no transparent cutout and no separate mouth/eye layers to drive.

To add a new preset, drop a PNG/JPG here and add it to `AVATAR_PRESETS` in
`videogen/avatar_presets.py`, or reference it directly by path in a project's `avatar:` field
(e.g. `avatar: assets/avatar/my_photo.png`) without touching the preset list.

To eventually support real mouth animation, a layered set would be needed instead (transparent
base + a handful of mouth-shape sprites + an eyes-closed sprite) — the rest of this pipeline
(timeline, word timings, captions, audio) is already positioned to drive that; only a new
per-frame background renderer would need to be added.
