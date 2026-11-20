# Avatar photos

| File | Preset name | Used for |
|---|---|---|
| `male.png` | `male` | `avatar` template, `avatar: male` (default) — headshot, blue background |
| `female.png` | `female` | `avatar` template, `avatar: female` — headshot, blue background |
| `male_casual.png` | `male_casual` | full-body, olive jacket, white background |
| `female_formal.png` | `female_formal` | portrait, green blazer, white background |
| `couple.png` | `couple` | two-person portrait, white background |

All are flat, opaque illustrations — not a layered sprite sheet. The `avatar` template
(`videogen/templates/avatar.py`) uses one as the scene's full background with a slow Ken-Burns-
style zoom for a sense of life. There's no lip-sync or mouth animation: these images have no
transparent cutout and no separate mouth/eye layers to drive.

The full-body/portrait presets (`male_casual`, `female_formal`, `couple`) are closer to a 2:3
aspect ratio than the original two (1:1) — on a 9:16 canvas the cover-crop will zoom in more
tightly than on the 1:1 headshots. Check how a new preset actually crops with `videogen preview`
before relying on it.

To add a new preset, drop a PNG/JPG here and add it to `AVATAR_PRESETS` in
`videogen/avatar_presets.py`, or reference it directly by path in a project's `avatar:` field
(e.g. `avatar: assets/avatar/my_photo.png`) without touching the preset list.

To eventually support real mouth animation, a layered set would be needed instead (transparent
base + a handful of mouth-shape sprites + an eyes-closed sprite) — the rest of this pipeline
(timeline, word timings, captions, audio) is already positioned to drive that; only a new
per-frame background renderer would need to be added.
