"""Turns per-scene TTS results into one global timeline: absolute word timings, scene spans
(for picking which visual is on screen), and caption cue groups (for rendering captions).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from videogen.models import Scene, VideoProject
from videogen.providers.base import SynthesisResult, WordTiming


@dataclass(frozen=True)
class SceneSpan:
    scene_index: int
    scene: Scene
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


@dataclass(frozen=True)
class Cue:
    scene_index: int
    words: list[WordTiming]  # absolute-time (already offset by scene start)

    @property
    def start_s(self) -> float:
        return self.words[0].start_s

    @property
    def end_s(self) -> float:
        return self.words[-1].end_s

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words if w.text)


@dataclass
class Timeline:
    scene_spans: list[SceneSpan]
    cues: list[Cue]
    words: list[WordTiming]
    total_duration_s: float
    per_scene_audio_offsets: list[float] = field(default_factory=list)


def build_timeline(
    project: VideoProject, synth_results: list[SynthesisResult], gap_s: float = 0.0
) -> Timeline:
    """`synth_results[i]` is the TTS output for `project.scenes[i]`, with word timings relative
    to that scene's own audio clip. `gap_s` is the silence inserted between scenes in the
    concatenated master audio (see audio.py) — scene offsets must line up with that exactly."""
    if len(synth_results) != len(project.scenes):
        raise ValueError("one SynthesisResult is required per scene")

    speech_end_s: list[float] = []  # end of this scene's actual narration (excludes trailing pause)
    all_words: list[WordTiming] = []
    offsets: list[float] = []
    cursor = 0.0

    for i, (scene, synth) in enumerate(zip(project.scenes, synth_results)):
        offsets.append(cursor)
        start_s = cursor
        end_s = cursor + synth.duration_s
        speech_end_s.append(end_s)
        for w in synth.words:
            all_words.append(
                WordTiming(text=w.text, start_s=start_s + w.start_s, duration_s=w.duration_s)
            )
        cursor = end_s + max(scene.pause_after_s, gap_s if i < len(project.scenes) - 1 else 0.0)

    # A scene's *visual* span extends through the pause that follows it, up to the next
    # scene's start (the last scene has no trailing pause — see audio.py/pipeline.py, neither
    # inserts one after the final scene either). Using the bare speech-end here would leave a
    # silent gap with no background for every inter-scene pause: concatenated backgrounds would
    # then fall short of the real audio by the sum of every pause_after_s, which `-shortest` on
    # the final ffmpeg encode would then silently truncate the END of the narration to match —
    # caught via a real multi-scene render whose last ~3s of audio were getting cut.
    scene_spans: list[SceneSpan] = []
    for i, scene in enumerate(project.scenes):
        start_s = offsets[i]
        visual_end_s = offsets[i + 1] if i + 1 < len(offsets) else speech_end_s[i]
        scene_spans.append(SceneSpan(scene_index=i, scene=scene, start_s=start_s, end_s=visual_end_s))

    total_duration_s = speech_end_s[-1] if speech_end_s else 0.0

    cues = _group_into_cues(
        scene_spans=scene_spans,
        words=all_words,
        max_words_per_cue=project.captions.max_words_per_cue,
    )

    return Timeline(
        scene_spans=scene_spans,
        cues=cues,
        words=all_words,
        total_duration_s=total_duration_s,
        per_scene_audio_offsets=offsets,
    )


def _group_into_cues(
    scene_spans: list[SceneSpan], words: list[WordTiming], max_words_per_cue: int
) -> list[Cue]:
    """Groups words into caption cues of up to `max_words_per_cue`, never spanning a scene
    boundary (a cue switching scenes mid-group would be visually confusing)."""
    cues: list[Cue] = []
    for span in scene_spans:
        scene_words = [w for w in words if span.start_s <= w.start_s < span.end_s]
        for i in range(0, len(scene_words), max(1, max_words_per_cue)):
            chunk = scene_words[i : i + max_words_per_cue]
            if chunk:
                cues.append(Cue(scene_index=span.scene_index, words=chunk))
    return cues
