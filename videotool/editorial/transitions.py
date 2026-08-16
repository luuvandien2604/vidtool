"""Editorial transitions between adjacent beats (spec section 14).

Category is derived from the MEANING PAIR of the two beats, never random.
"""
from __future__ import annotations

from videotool.domain.motion import TransitionCategory, TransitionPlan
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction as SF

MAX_TRANSITION_SEC = 0.6

# (from, to) -> category; specific pairs first, generic families after
_PAIR_RULES: list[tuple[tuple[str, str], TransitionCategory]] = [
    ((SF.CAUSAL_EXPLANATION.value, SF.CONSEQUENCE.value), TransitionCategory.CAUSE_TO_EFFECT),
    ((SF.CAUSAL_EXPLANATION.value, SF.ESCALATION.value), TransitionCategory.ESCALATION),
    ((SF.EVIDENCE.value, SF.REVEAL.value), TransitionCategory.EVIDENCE_TO_REVEAL),
    ((SF.HOOK.value, SF.EVIDENCE.value), TransitionCategory.QUESTION_TO_EVIDENCE),
    ((SF.HOOK.value, SF.ESTABLISHING_CONTEXT.value), TransitionCategory.CONTINUATION),
    ((SF.EVIDENCE.value, SF.TECHNICAL_EXPLANATION.value), TransitionCategory.ZOOM_TO_DETAIL),
    ((SF.ESTABLISHING_CONTEXT.value, SF.EVIDENCE.value), TransitionCategory.ZOOM_TO_DETAIL),
    ((SF.LOCATION_INTRODUCTION.value, SF.GEOGRAPHIC_MOVEMENT.value), TransitionCategory.MAP_TO_LOCATION),
    ((SF.EVIDENCE.value, SF.CHRONOLOGY.value), TransitionCategory.DOCUMENT_TO_EVENT),
    ((SF.EVIDENCE.value, SF.CONSEQUENCE.value), TransitionCategory.DOCUMENT_TO_EVENT),
    ((SF.CHARACTER_INTRODUCTION.value, SF.PROCESS.value), TransitionCategory.CHARACTER_TO_ACTION),
    ((SF.CHARACTER_INTRODUCTION.value, SF.GEOGRAPHIC_MOVEMENT.value), TransitionCategory.CHARACTER_TO_ACTION),
    ((SF.COMPARISON.value, SF.CONSEQUENCE.value), TransitionCategory.BEFORE_TO_AFTER),
    ((SF.CHRONOLOGY.value, SF.SUMMARY.value), TransitionCategory.PAST_TO_PRESENT),
    ((SF.CONSEQUENCE.value, SF.SUMMARY.value), TransitionCategory.PAST_TO_PRESENT),
    ((SF.ESCALATION.value, SF.TURNING_POINT.value), TransitionCategory.ESCALATION),
]

_TO_RULES: dict[str, TransitionCategory] = {
    SF.REVEAL.value: TransitionCategory.EVIDENCE_TO_REVEAL,
    SF.SUMMARY.value: TransitionCategory.PAST_TO_PRESENT,
    SF.CONSEQUENCE.value: TransitionCategory.CAUSE_TO_EFFECT,
}

_FROM_RULES: dict[str, TransitionCategory] = {
    SF.EVIDENCE.value: TransitionCategory.DOCUMENT_TO_EVENT,
    SF.CHRONOLOGY.value: TransitionCategory.DOCUMENT_TO_EVENT,
    SF.CHARACTER_INTRODUCTION.value: TransitionCategory.CHARACTER_TO_ACTION,
    SF.LOCATION_INTRODUCTION.value: TransitionCategory.MAP_TO_LOCATION,
    SF.ESCALATION.value: TransitionCategory.ESCALATION,
}


def select_transition_category(prev: SemanticBeat, nxt: SemanticBeat) -> tuple[TransitionCategory, str]:
    key = (prev.semantic_function.value, nxt.semantic_function.value)
    for pair_key, cat in _PAIR_RULES:
        if pair_key == key:
            return cat, (f"{pair_key[0]} -> {pair_key[1]} reads as {cat.value}")
    # chapter break: entity continuity resets into fresh context
    if (nxt.semantic_function == SF.ESTABLISHING_CONTEXT
            and prev.entities and nxt.entities
            and not set(e.lower() for e in prev.entities) & set(e.lower() for e in nxt.entities)):
        return TransitionCategory.HARD_CHAPTER_BREAK, "no shared entities and new context: chapter break"
    if nxt.semantic_function.value in _TO_RULES:
        cat = _TO_RULES[nxt.semantic_function.value]
        return cat, f"entering {nxt.semantic_function.value} reads as {cat.value}"
    if prev.semantic_function.value in _FROM_RULES:
        cat = _FROM_RULES[prev.semantic_function.value]
        return cat, f"leaving {prev.semantic_function.value} reads as {cat.value}"
    return TransitionCategory.CONTINUATION, "continuous narration thought"


def plan_transitions(beats: list[SemanticBeat]) -> list[TransitionPlan]:
    out: list[TransitionPlan] = []
    for prev, nxt in zip(beats, beats[1:]):
        cat, reason = select_transition_category(prev, nxt)
        window = min(MAX_TRANSITION_SEC, prev.duration_sec * 0.25, nxt.duration_sec * 0.25)
        out.append(TransitionPlan(
            from_beat=prev.beat_id, to_beat=nxt.beat_id, category=cat,
            start_sec=round(prev.end_sec - window, 3),
            end_sec=round(prev.end_sec, 3), reason=reason))
    return out
