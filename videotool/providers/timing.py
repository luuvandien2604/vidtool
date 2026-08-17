"""Narration timing provider abstraction and deterministic offline provider."""
from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from videotool.domain.narration import Narration, synthetic_word_timings
from videotool.domain.timing import NarrationTiming

NARRATION_TIMING_VERSION = 1


class NarrationTimingProvider(Protocol):
    provider_id: str
    provider_version: int

    def align(self, narration: Narration) -> NarrationTiming: ...


class DeterministicNarrationTimingProvider:
    """Use supplied boundaries, or explicitly mark deterministic estimates."""
    provider_id = "deterministic"
    provider_version = NARRATION_TIMING_VERSION

    def align(self, narration: Narration) -> NarrationTiming:
        if narration.words:
            words = narration.words
            source = "provided_word_boundaries"
            estimated = False
        else:
            words = tuple(replace(word, confidence=0.55)
                          for word in synthetic_word_timings(narration.text))
            source = "deterministic_text_estimate"
            estimated = True
        duration = words[-1].end_sec if words else 0.0
        return NarrationTiming(
            words=tuple(words), duration_sec=round(duration, 3), source=source,
            provider=self.provider_id, provider_version=self.provider_version,
            is_estimated=estimated)
