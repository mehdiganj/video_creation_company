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

## Gemini errors

- `GEMINI_API_KEY is not set` — copy `.env.example` to `.env` and fill it in, or pass
  `--provider mock` to render/preview without real TTS.
- `Gemini voice replication failed (HTTP ...)` from `videogen clone-voice` — this endpoint is
  new (~Sep 2026) and has reported instability (REST 500s) on Google's own developer forum.
  Try cloning the voice directly in [Google AI Studio](https://aistudio.google.com) instead —
  Google's own primary documented path — and paste the resulting voice id into a project's
  `voice:` field; it works exactly the same way either way.
- Captions drift noticeably more on Gemini-voiced renders than Azure-voiced ones — expected,
  not a bug. Gemini's TTS response carries no word-level timing (a confirmed, open limitation,
  not a gap in this integration), so word timings are estimated from character count — see
  `providers/gemini.py`'s module docstring. Switch to `--provider azure` if exact caption sync
  matters more than voice cloning for a given video.
- `rate:` in a project YAML has no effect when rendering with `--provider gemini` — no
  documented numeric speaking-rate parameter was found for this API; it's silently ignored
  there (still applied on Azure).

## Costs & limits

Azure's free tier (F0) is roughly 0.5M characters/month of neural TTS (~180 minutes), billed
per character past that. Gemini bills per-token (input text + output audio tokens) and has no
free tier here — it's the pricier option; its main value is self-serve voice cloning, not cost.

Run `videogen estimate <project>.yaml --provider azure|gemini` before a real render to see
projected new characters, duration, and cost. Every synthesis is cached on
`(text, voice, language, rate, provider)` in `.cache/tts/` — re-rendering after only changing
captions, music, or a background never re-bills unchanged narration, and `estimate` reflects
that (already-cached scenes show as free). Use `--no-cache` on `videogen render` only when you
deliberately want to force re-synthesis — in practice this shouldn't be necessary, since the
scene's own text is already part of the cache key.

## Renders are slow

Two different things can be slow — treat them separately:

- **TTS synthesis** (network calls to Azure/Gemini): uncached scenes synthesize concurrently
  (`--concurrency`, default 4, on `videogen render`) since each call is dominated by network
  round-trip latency, not local compute — this is the main lever for multi-scene projects. A
  lower `--concurrency` trades speed for staying further under a provider's rate limits.
- **Compositing/encoding** (ffmpeg): `videogen preview` renders at ~45% resolution with the
  `mock` TTS provider and ffmpeg's `ultrafast` preset by default — use it while iterating on a
  script/layout, and `render` only for the final pass. This project deliberately doesn't use
  moviepy/per-frame Python compositing (see the architecture note at the top of
  `core/compose.py`); if a real render is still slow, check
  `out/<name>/_work/<platform>/<platform>.cmd.txt` for the exact ffmpeg command and profile it
  directly (e.g. try `-preset faster` or drop `-crf` a few points).
