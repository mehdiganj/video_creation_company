import itertools

from videogen.providers.base import estimate_duration_s, estimate_word_timings


def test_estimate_duration_scales_with_length():
    short = estimate_duration_s("hi there")
    long = estimate_duration_s("hi there, this is a much longer sentence than the first one")
    assert long > short


def test_estimate_duration_has_a_floor():
    assert estimate_duration_s("hi") >= 0.3


def test_estimate_duration_respects_rate():
    normal = estimate_duration_s("a reasonably long sentence to synthesize", rate=1.0)
    fast = estimate_duration_s("a reasonably long sentence to synthesize", rate=2.0)
    assert fast < normal


def test_estimate_word_timings_covers_full_duration():
    timings = estimate_word_timings("one two three four", 4.0)
    assert len(timings) == 4
    assert timings[0].start_s == 0.0
    assert abs(timings[-1].end_s - 4.0) < 1e-6


def test_estimate_word_timings_are_sequential_and_non_overlapping():
    timings = estimate_word_timings("a short burst of words here", 2.0)
    for a, b in itertools.pairwise(timings):
        assert abs(a.end_s - b.start_s) < 1e-9
