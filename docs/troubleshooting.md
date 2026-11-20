# Troubleshooting

## `ffmpeg/ffprobe not found on PATH`

```bash
brew install ffmpeg
```

On older macOS + Homebrew setups, `brew install` can fail with a permissions error like
`/usr/local/libexec` not writable. Fix it once with:

```bash
sudo chown -R "$(whoami)" /usr/local/libexec
brew install ffmpeg
```

Run `videogen doctor` afterward to confirm.

## Farsi renders as disconnected letters, or in the wrong order

This project doesn't ship a shaping engine (Pillow's RAQM support isn't available in the
target environment) — `core/text_shaping.py` hand-rolls reshaping (`arabic_reshaper`) and
bidi reordering (`python-bidi`) per rendered line instead. If something looks wrong:

- Confirm the text is going through `text_shaping.shape_for_display(text, "fa")` before
  `draw.text(...)` — every Farsi-drawing call site should (`core/captions.py`,
  `templates/text_card.py`). A raw unshaped string drawn directly is the most common cause.
- Mixed Farsi + English + digits on one line is the trickiest case — see
  `tests/test_text_shaping.py` for the cases this is tested against. If you hit a real mixed-
  script bug, add a fixture there before fixing it.
- Karaoke caption word-highlighting reveals a *reshaped prefix* anchored to the reading-start
  edge (right edge for Farsi) rather than computing an exact glyph boundary — in rare cases
  (a prefix cut mid-join) the highlight boundary can be off by a character. This is a known,
  accepted simplification, not a sign something else is broken.

## Azure errors

- `AZURE_SPEECH_KEY / AZURE_SPEECH_REGION are not set` — copy `.env.example` to `.env` and
  fill them in, or pass `--provider mock` to render/preview without real TTS.
- `Azure TTS synthesis failed for voice=...` — usually a wrong/retired voice name
  (`videogen voices --language en` / `--language fa` to list current ones) or a free-tier
  resource that's been deprovisioned from inactivity (recreate it in the Azure portal).
- A render that used to work now fails after weeks of not running it — Azure can deprovision
  an idle free-tier (F0) Speech resource; check the portal.

## Costs & limits

Azure's free tier (F0) is roughly 0.5M characters/month of neural TTS (~180 minutes). Every
synthesis is cached on `(text, voice, language, rate)` in `.cache/tts/` — re-rendering after
only changing captions, music, or a background never re-bills unchanged narration. Use
`--no-cache` on `videogen render` only when you deliberately want to force re-synthesis (e.g.
after editing a scene's text but keeping the same cache key would be wrong — in practice this
shouldn't happen, since the text itself is part of the cache key).

## Renders are slow

`videogen preview` renders at ~45% resolution with the `mock` TTS provider and ffmpeg's
`ultrafast` preset by default — use it while iterating on a script/layout, and `render` only
for the final pass. This project deliberately doesn't use moviepy/per-frame Python compositing
(see the architecture note at the top of `core/compose.py`); if a real render is still slow,
check `out/<name>/_work/<platform>/<platform>.cmd.txt` for the exact ffmpeg command and profile
it directly (e.g. try `-preset faster` or drop `-crf` a few points).
