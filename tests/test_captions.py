import itertools

from PIL import Image

from videogen.brand import load_brand
from videogen.core.captions import render_caption_overlays
from videogen.core.timeline import Cue
from videogen.models import CaptionStyle
from videogen.platforms import PLATFORMS
from videogen.providers.base import WordTiming

CANVAS = PLATFORMS["instagram"]
BRAND = load_brand()


def _cue(words: list[str], start: float = 0.0, step: float = 0.3) -> Cue:
    timings = [WordTiming(text=w, start_s=start + i * step, duration_s=step) for i, w in enumerate(words)]
    return Cue(scene_index=0, words=timings)


def test_karaoke_emits_one_png_per_word(tmp_path):
    cue = _cue(["hello", "world", "this", "works"])
    overlays = render_caption_overlays(
        [cue], "en", CaptionStyle(style="karaoke", max_words_per_cue=4), CANVAS, BRAND, tmp_path
    )
    assert len(overlays) == 4
    # spans must be contiguous and cover the whole cue
    assert overlays[0].span.start_s == cue.start_s
    assert overlays[-1].span.end_s == cue.end_s
    for a, b in itertools.pairwise(overlays):
        assert a.span.end_s == b.span.start_s


def test_karaoke_pngs_are_valid_rgba(tmp_path):
    cue = _cue(["one", "two"])
    overlays = render_caption_overlays(
        [cue], "en", CaptionStyle(style="karaoke"), CANVAS, BRAND, tmp_path
    )
    for ov in overlays:
        img = Image.open(ov.png_path)
        assert img.mode == "RGBA"
        assert img.width == CANVAS.width
        assert img.height > 0


def test_block_style_emits_one_png_per_cue(tmp_path):
    cues = [_cue(["a", "b", "c"]), _cue(["d", "e"], start=5.0)]
    overlays = render_caption_overlays(
        cues, "en", CaptionStyle(style="block"), CANVAS, BRAND, tmp_path
    )
    assert len(overlays) == 2


def test_none_style_emits_nothing(tmp_path):
    cue = _cue(["a", "b"])
    overlays = render_caption_overlays(
        [cue], "en", CaptionStyle(style="none"), CANVAS, BRAND, tmp_path
    )
    assert overlays == []


def test_farsi_karaoke_does_not_crash(tmp_path):
    cue = _cue(["من", "با", "Claude", "۲۰۲۶"])
    overlays = render_caption_overlays(
        [cue], "fa", CaptionStyle(style="karaoke", max_words_per_cue=4), CANVAS, BRAND, tmp_path
    )
    assert len(overlays) == 4
    for ov in overlays:
        assert ov.png_path.is_file()


def test_long_cue_falls_back_to_block_when_it_does_not_fit_one_line(tmp_path):
    long_words = [f"word{i}" for i in range(40)]  # guaranteed not to fit on one line
    cue = _cue(long_words, step=0.1)
    overlays = render_caption_overlays(
        [cue], "en", CaptionStyle(style="karaoke", max_words_per_cue=40), CANVAS, BRAND, tmp_path
    )
    assert len(overlays) == 1  # one wrapped block, not one PNG per word
    assert overlays[0].span.start_s == cue.start_s
    assert overlays[0].span.end_s == cue.end_s
