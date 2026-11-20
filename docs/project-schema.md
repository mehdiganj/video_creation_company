# Project YAML reference

The schema lives in `videogen/models.py` (`VideoProject` and friends) — this is a guided tour,
not a copy of the code. Run `videogen validate <file>.yaml` to check a project against it.

```yaml
name: my-reel                 # required — also the output folder name under out/
template: avatar               # required — avatar | faceless | text_card
language: en                   # required — en | fa
voice: en-US-AndrewMultilingualNeural   # required — `videogen voices --provider azure --language en`
                                #   (for Gemini: a stock name like "Kore", or a cloned voice id
                                #   from `videogen clone-voice` / AI Studio)
rate: 1.0                      # optional, 0.3-2.5 — Azure SSML prosody rate multiplier.
                                #   Not applied on Gemini (no documented rate parameter there).

avatar: male                   # only used by template: avatar — male | female | a custom path

platforms: [instagram, linkedin, youtube_shorts]   # required, at least one — see platforms.py
primary_platform: instagram    # optional — defaults to platforms[0]; used by `videogen preview`
reframe:                       # optional per-platform override (default: native for all)
  linkedin: pad                # native | pad | crop

music:                         # optional — omit entirely for no music
  track: assets/music/lofi_calm.mp3   # required if `music` is present
  gain_db: -22                 # optional, default -22
  duck: true                   # optional, default true — sidechain-compress music under voice

captions:                      # optional — defaults live on CaptionStyle (models.py)
  style: karaoke                # karaoke | block | none
  max_words_per_cue: 4
  position: 0.78                # fraction of canvas height, 0 = top
  font_size_ratio: 0.04         # fraction of canvas height
  highlight_color: "#E8B339"    # optional — defaults to brand.yaml colors.accent

scenes:                        # required, at least one
  - text: "What this scene says — this is what gets synthesized and captioned."
    pause_after_s: 0.4          # optional, default 0.4 — silence before the next scene
    visual:                     # optional (ignored entirely by template: avatar)
      kind: solid                # solid | image | video
      color: "#101418"           # solid only
      src: assets/backgrounds/x.jpg   # image/video only, required for those kinds
      motion: ken_burns           # image only — none | ken_burns
```

## Notes

- `scenes[].visual` is ignored by `template: avatar` (the avatar photo is always the
  background) and by `template: text_card` except for its `color` (background fill) — an
  `image`/`video` visual.kind on a text_card scene is simply unused, not an error.
- `videogen validate` checks every referenced file (`music.track`, `scenes[].visual.src`,
  `avatar`) actually exists on disk, in addition to the schema itself — run it before a full
  render, especially one that will hit real Azure TTS.
- `voice`/`language` mismatches are a warning, not an error (`videogen validate` and
  `render` both print it) — Azure's multilingual voices can legitimately speak a language other
  than their name implies.
- The TTS provider itself (`azure` / `gemini` / `mock`) isn't a project YAML field — it's
  chosen at render time with `--provider`, or `VIDEOGEN_TTS_PROVIDER` in `.env`. A project's
  `voice:` only makes sense for whichever provider you render it with.
