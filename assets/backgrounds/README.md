# Backgrounds

Drop your own images or video clips here for the `faceless` template's `visual.src` field.
Gitignored except for this file, for the same reason as `assets/music/` — licensing varies per
asset, and binary media bloats a git repo fast.

- Images: any size works — `compose.py` scales/crops to cover each platform's canvas.
  Set `motion: ken_burns` on a scene's `visual` for a slow pan/zoom.
- Video clips: looped/trimmed to the scene's spoken duration automatically.
