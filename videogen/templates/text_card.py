"""Big on-screen text, timed to the voiceover — a "quote card" / lyric-video style reel.
The scene's `visual` is ignored (a text-card is defined by its text, not a picture); only a
solid background is used.

Two reveal modes (`brand.yaml: text_card.reveal`):
- "all": the scene's full (wrapped) text appears as one static slide for the whole scene.
- "word": words pop in as they're spoken. Lines before the currently-speaking line stay fully
  visible; the current line reveals left-to-right (English) or right-to-left (Farsh) one word
  at a time, by drawing only the already-spoken prefix — no masking needed, the same technique
  `core/captions.py` uses for karaoke captions.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from videogen.core import text_shaping
from videogen.core.fonts import get_font
from videogen.core.layers import BackgroundLayer, OverlayLayer, TimeSpan
from videogen.core.layout import font_size_px, safe_margin_px
from videogen.core.timeline import Timeline
from videogen.models import VideoProject
from videogen.platforms import Platform
from videogen.templates.base import Template, scene_words


class TextCardTemplate(Template):
    def build_backgrounds(
        self, project: VideoProject, timeline: Timeline, canvas: Platform
    ) -> list[BackgroundLayer]:
        layers = []
        for span in timeline.scene_spans:
            visual = span.scene.visual
            color = visual.color if (visual and visual.kind == "solid" and visual.color) else "#101418"
            layers.append(
                BackgroundLayer(kind="solid", span=TimeSpan(span.start_s, span.end_s), color=color)
            )
        return layers

    def build_extra_overlays(
        self,
        project: VideoProject,
        timeline: Timeline,
        canvas: Platform,
        brand: dict,
        work_dir: Path,
    ) -> list[OverlayLayer]:
        cfg = brand["text_card"]
        font_size = font_size_px(canvas, cfg["font_size_ratio"])
        font = get_font(brand, project.language, font_size, bold=True)
        margin = safe_margin_px(canvas, fraction=0.1)
        max_w = canvas.width - 2 * margin
        line_h = round(font_size * cfg["line_spacing"])
        text_color = brand["colors"]["text"]
        reveal_mode = cfg.get("reveal", "word")

        out_dir = work_dir / "text_card"
        out_dir.mkdir(parents=True, exist_ok=True)

        overlays: list[OverlayLayer] = []
        for scene_idx, span in enumerate(timeline.scene_spans):
            words = [w for w in scene_words(timeline, scene_idx) if w.text]
            if not words:
                continue
            lines = text_shaping.wrap_words([w.text for w in words], font, max_w)
            display_lines = [text_shaping.shape_for_display(line, project.language) for line in lines]
            block_h = len(display_lines) * line_h
            top = (canvas.height - block_h) / 2 + line_h / 2
            line_rects = [
                (i, top + i * line_h, font.getlength(display_lines[i])) for i in range(len(lines))
            ]

            if reveal_mode != "word":
                img = Image.new("RGBA", (canvas.width, canvas.height), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                for i, line in enumerate(display_lines):
                    draw.text((canvas.width / 2, top + i * line_h), line, font=font, fill=text_color, anchor="mm")
                png_path = out_dir / f"scene_{scene_idx:03d}_all.png"
                img.save(png_path)
                overlays.append(
                    OverlayLayer(png_path=png_path, x_px=0, y_px=0, span=TimeSpan(span.start_s, span.end_s), z=5)
                )
                continue

            overlays.extend(
                self._render_word_reveal_states(
                    scene_idx, span, words, lines, display_lines, line_rects, line_h,
                    font, project.language, canvas, text_color, out_dir,
                )
            )
        return overlays

    @staticmethod
    def _render_word_reveal_states(
        scene_idx, span, words, lines, display_lines, line_rects, line_h,
        font, language, canvas, text_color, out_dir,
    ) -> list[OverlayLayer]:
        overlays: list[OverlayLayer] = []
        line_word_counts = [len(line.split(" ")) for line in lines]
        word_cursor = 0
        line_starts: list[int] = []
        for count in line_word_counts:
            line_starts.append(word_cursor)
            word_cursor += count

        n_lines = len(lines)
        for line_i in range(n_lines):
            count = line_word_counts[line_i]
            start_idx = line_starts[line_i]
            line_words = words[start_idx : start_idx + count]
            _, y, full_w = line_rects[line_i]
            left_edge = canvas.width / 2 - full_w / 2
            right_edge = canvas.width / 2 + full_w / 2

            for wi in range(len(line_words)):
                start_s = line_words[wi].start_s
                if wi + 1 < len(line_words):
                    end_s = line_words[wi + 1].start_s
                elif line_i + 1 < n_lines:
                    end_s = words[line_starts[line_i + 1]].start_s
                else:
                    end_s = span.end_s

                img = Image.new("RGBA", (canvas.width, canvas.height), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                for prev_i in range(line_i):
                    _, prev_y, _ = line_rects[prev_i]
                    draw.text((canvas.width / 2, prev_y), display_lines[prev_i], font=font, fill=text_color, anchor="mm")

                prefix_text = " ".join(w.text for w in line_words[: wi + 1])
                prefix_display = text_shaping.shape_for_display(prefix_text, language)
                if language == "fa":
                    draw.text((right_edge, y), prefix_display, font=font, fill=text_color, anchor="rm")
                else:
                    draw.text((left_edge, y), prefix_display, font=font, fill=text_color, anchor="lm")

                png_path = out_dir / f"scene_{scene_idx:03d}_line{line_i:02d}_word{wi:02d}.png"
                img.save(png_path)
                overlays.append(
                    OverlayLayer(png_path=png_path, x_px=0, y_px=0, span=TimeSpan(start_s, end_s), z=5)
                )
        return overlays
