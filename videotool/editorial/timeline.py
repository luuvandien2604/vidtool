"""Timeline composition (planning-level, renderer agnostic).

Merges beats, compositions, motion events and subtitles into one resolved
timeline artifact. Subtitles are independent from composition and live in
the reserved safe zone.
"""
from __future__ import annotations

from videotool.domain.composition import VisualComposition
from videotool.domain.motion import MotionPlan
from videotool.domain.narration import Narration
from videotool.domain.timing import NarrationTiming
from videotool.domain.semantic_beat import SemanticBeat

from .composition.base import CANVAS, SUBTITLE_SAFE_ZONE

SUBTITLE_MAX_WORDS = 7
SUBTITLE_MAX_SEC = 3.5


def build_subtitles(narration: Narration | NarrationTiming) -> list[dict]:
    lines: list[dict] = []
    current: list = []
    for word in narration.words:
        if not current:
            current = [word]
            continue
        span = word.end_sec - current[0].start_sec
        if (len(current) >= SUBTITLE_MAX_WORDS or span >= SUBTITLE_MAX_SEC
                or word.text.endswith((".", "!", "?"))):
            current.append(word)
            lines.append({
                "start_sec": round(current[0].start_sec, 3),
                "end_sec": round(current[-1].end_sec, 3),
                "text": " ".join(w.text for w in current),
            })
            current = []
        else:
            current.append(word)
    if current:
        lines.append({
            "start_sec": round(current[0].start_sec, 3),
            "end_sec": round(current[-1].end_sec, 3),
            "text": " ".join(w.text for w in current),
        })
    return lines


def build_timeline(episode_id: str, narration: Narration,
                   beats: list[SemanticBeat],
                   compositions: list[VisualComposition],
                   motion: MotionPlan,
                   narration_timing: NarrationTiming | None = None) -> dict:
    """Compose the resolved timeline.

    Transitions are DATA of the motion plan / timeline - this function must
    never mutate VisualComposition (Phase 1.2.1: post-artifact mutation made
    fresh and resumed runs diverge in memory).
    """
    comp_by_beat = {c.beat_id: c for c in compositions}
    segments = []
    for index, beat in enumerate(beats):
        comp = comp_by_beat.get(beat.beat_id)
        transition_in = next(
            (t.category.value for t in motion.transitions
             if t.to_beat == beat.beat_id), None)
        if transition_in is None:
            transition_in = "CUT_IN" if index == 0 else "CONTINUATION"
        transition_out = next(
            (t.category.value for t in motion.transitions
             if t.from_beat == beat.beat_id), None)
        segments.append({
            "beat_id": beat.beat_id,
            "composition_id": comp.composition_id if comp else None,
            "semantic_function": beat.semantic_function.value,
            "visual_family": comp.visual_family if comp else None,
            "strategy": comp.strategy if comp else None,
            "start_sec": beat.start_sec,
            "end_sec": beat.end_sec,
            "transition_in": transition_in,
            "transition_out": transition_out,
        })

    canonical_timing = narration_timing or narration
    return {
        "episode_id": episode_id,
        "canvas": dict(CANVAS),
        "subtitle_safe_zone": {"x": SUBTITLE_SAFE_ZONE[0], "y": SUBTITLE_SAFE_ZONE[1],
                               "width": SUBTITLE_SAFE_ZONE[2], "height": SUBTITLE_SAFE_ZONE[3]},
        "total_duration_sec": round(canonical_timing.duration_sec, 3),
        "segments": segments,
        "motion_events": [e.to_dict() for plan in motion.plans for e in plan.events],
        "transitions": [t.to_dict() for t in motion.transitions],
        "subtitles": build_subtitles(canonical_timing),
        "narration_timing_source": getattr(canonical_timing, "source", "legacy"),
    }
