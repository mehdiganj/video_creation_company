from PIL import ImageFont

from videogen.core import text_shaping
from videogen.settings import REPO_ROOT

VAZIRMATN = REPO_ROOT / "assets/fonts/Vazirmatn-Regular.ttf"
INTER = REPO_ROOT / "assets/fonts/Inter-Variable.ttf"


def test_english_is_passthrough():
    text = "Claude Code ships every week"
    assert text_shaping.shape_for_display(text, "en") == text


def test_farsi_reshapes_to_a_different_string():
    text = "من هر هفته یک پروژه می‌سازم"
    shaped = text_shaping.shape_for_display(text, "fa")
    assert shaped != text
    assert len(shaped) > 0


def test_farsi_with_embedded_english_and_digits_does_not_crash():
    text = "من با Claude Code کار می‌کنم و سال ۲۰۲۶ خیلی شلوغ بوده."
    shaped = text_shaping.shape_for_display(text, "fa")
    assert "Claude" in shaped or "Claude"[::-1] in shaped  # bidi may reverse the LTR run's position, not its glyphs
    assert len(shaped) > 0


def test_wrap_words_respects_max_width():
    font = ImageFont.truetype(str(INTER), size=40)
    words = ["this", "is", "a", "reasonably", "long", "sentence", "that", "should", "wrap", "across", "multiple", "lines"]
    max_w = 300
    lines = text_shaping.wrap_words(words, font, max_w)
    assert len(lines) > 1
    for line in lines:
        assert font.getlength(line) <= max_w + 1  # small tolerance for rounding


def test_wrap_words_single_short_line():
    font = ImageFont.truetype(str(INTER), size=20)
    lines = text_shaping.wrap_words(["hi", "there"], font, 1000)
    assert lines == ["hi there"]


def test_is_rtl():
    assert text_shaping.is_rtl("fa") is True
    assert text_shaping.is_rtl("en") is False
