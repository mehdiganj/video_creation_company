# video_creation_company

Code-driven video generator for social media — Instagram Reels, LinkedIn, YouTube Shorts —
in Farsi and English. No editing software: write a script in a YAML file, run one command, get
an MP4 per platform.

Three templates share one pipeline (script -> voice -> captions -> music -> export):

- **`avatar`** — a static portrait (see `assets/avatar/`) as the background, with a slow
  Ken-Burns-style zoom, captions, and optional music. No lip-sync — see
  [`assets/avatar/README.md`](assets/avatar/README.md).
- **`faceless`** — voiceover over a solid color, still image (with Ken Burns pan/zoom), or
  looping video clip. No avatar.
- **`text_card`** — big on-screen text that reveals word-by-word in sync with the voiceover
  (lyric-video style). No separate captions needed.

## Quick start

```bash
brew install ffmpeg
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
cp .env.example .env   # then fill in AZURE_SPEECH_KEY / AZURE_SPEECH_REGION
videogen doctor
```

Get an Azure Speech key: [portal.azure.com](https://portal.azure.com) -> create a "Speech"
resource (Cognitive Services). The free tier (F0) covers roughly 180 minutes/month of neural
TTS — see [docs/troubleshooting.md](docs/troubleshooting.md#costs--limits).

Render one of the committed examples (works with no Azure key at all, via the mock provider):

```bash
videogen render projects/example_avatar_en.yaml --provider mock
videogen render projects/example_faceless_en.yaml --provider mock
videogen render projects/example_textcard_fa.yaml --provider mock
```

Output lands in `out/<project name>/<platform>.mp4`. Drop `--provider mock` once your `.env`
has a real Azure key.

## Make a video

```bash
videogen new my-reel --template avatar --language en
# edit projects/my-reel.yaml — your script, voice, platforms
videogen validate projects/my-reel.yaml
videogen preview projects/my-reel.yaml      # fast, low-res draft
videogen render projects/my-reel.yaml       # full render, every platform in the file
```

See [docs/project-schema.md](docs/project-schema.md) for every field a project YAML accepts.

## How it works

One project config renders to several platforms without re-running TTS for each:

```
load + validate  ->  per-scene Azure TTS (cached)  ->  timeline (word timings, caption cues)
                  ->  master audio (voice + music, ducked, loudness-normalized)
                  ->  [per platform] backgrounds + captions + template overlays
                  ->  ffmpeg compose  ->  encode  ->  ffprobe self-check
```

The TTS/audio stages run once per project; only the visual compose+encode step repeats per
platform (`platforms: [instagram, linkedin, youtube_shorts]` in a project YAML) — each platform
re-does *layout* (captions re-wrap, backgrounds re-fit) rather than cropping one fixed render,
so a 9:16 project genuinely re-composes for 1:1 or 16:9, not just pads/crops.

Every `ffmpeg` command actually run is logged next to its output (`out/<name>/_work/.../*.cmd.txt`)
so you can copy, tweak, and re-run it by hand if something looks off.

## Farsi

Farsi text is reshaped (`arabic_reshaper`) and bidi-reordered (`python-bidi`) per rendered line
before drawing with Pillow, since Pillow has no built-in complex-script shaping (RAQM) in this
project's target environment. This handles Mehdi's actual writing style — Farsi sentences with
embedded English terms and Latin digits — correctly; see `core/text_shaping.py`'s docstring and
`tests/test_text_shaping.py` for the specifics and the one known simplification (karaoke caption
reveal at a word boundary, not a guaranteed-exact glyph boundary).

## Platforms

| Preset | Size | Notes |
|---|---|---|
| `instagram` | 1080x1920 | Reels, 90s hard cap |
| `linkedin` | 1080x1080 | `linkedin_wide` = 1920x1080 |
| `youtube` | 1920x1080 | no cap |
| `youtube_shorts` | 1080x1920 | 180s cap, 60s recommended |
| `tiktok` | 1080x1920 | 60s recommended |

## Adding a new template

Subclass `Template` in `videogen/templates/base.py`, implement `build_backgrounds` (and
`build_extra_overlays` if it needs visuals beyond captions — see `text_card.py`), then register
it in `videogen/templates/__init__.py`. See [docs/adding-a-template.md](docs/adding-a-template.md).
You never touch TTS, timeline, captions, audio, or export code to add a template.

## Adding a new TTS provider

Implement `TTSProvider` in `videogen/providers/base.py` (see `providers/mock.py` for the
simplest possible example). Wire it into `core/pipeline.py:make_provider`.

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) — ffmpeg missing, Farsi rendering as
disconnected letters, Azure quota/auth errors, slow renders.

## Costs, caching, licensing

- Azure TTS is metered; every synthesis is cached on a hash of `(text, voice, language, rate)`
  in `.cache/tts/` — editing captions/music/background never re-bills unchanged narration.
- `assets/music/` and `assets/backgrounds/` are gitignored (bring your own licensed tracks and
  footage); `assets/fonts/` (Inter, Vazirmatn, both OFL) and `assets/avatar/` are committed.
- Code is MIT-licensed (see `LICENSE`).
