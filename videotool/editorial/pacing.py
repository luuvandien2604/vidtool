"""Speech pacing and rhythm auditor for editorial timing analysis.

Analyzes the density and rhythm between spoken narration and visual cuts:
- Token Rate: WPS (Words Per Second for English) vs SPS (Syllables Per Second for Vietnamese).
- Reading Speed: CPS (Characters Per Second) against broadcast subtitle comfort limits.
- Boundary Cut Alignment: Detects whether visual beat transitions land on natural pauses.
"""
from __future__ import annotations

from videotool.domain.timing import BeatPacingMetric, NarrationTiming, PacingReport


def audit_speech_pacing(timeline: dict, timing: NarrationTiming,
                        language: str = "en") -> PacingReport:
    """Audit speech pacing, reading speed, and visual cut alignment."""
    segments = timeline.get("segments", [])
    total_duration = float(timeline.get("total_duration_sec", timing.duration_sec))
    lang = (language or "en").lower().strip()
    is_vi = lang.startswith("vi")

    # Threshold configuration with explicit units
    if is_vi:
        optimal_min = 2.4
        optimal_max = 4.8
        rushed_thresh = 5.2
        dragging_thresh = 1.8
        max_cps = 22.0
        unit_label = "SPS (syllables/sec)"
    else:
        optimal_min = 2.0
        optimal_max = 3.4
        rushed_thresh = 3.8
        dragging_thresh = 1.4
        max_cps = 17.0
        unit_label = "WPS (words/sec)"

    beat_metrics: list[BeatPacingMetric] = []
    episode_warnings: list[str] = []
    clean_cuts = 0

    all_words = list(timing.words)

    for i, seg in enumerate(segments):
        beat_id = seg["beat_id"]
        start_sec = float(seg["start_sec"])
        end_sec = float(seg["end_sec"])
        dur = max(0.1, end_sec - start_sec)

        # Words within this visual beat
        beat_words = [w for w in all_words if w.end_sec > start_sec and w.start_sec < end_sec]
        token_count = len(beat_words)
        char_count = sum(len(w.text) for w in beat_words)

        token_rate = round(token_count / dur, 2)
        char_rate = round(char_count / dur, 2)

        # Pause gap calculations
        if beat_words:
            pause_before = max(0.0, beat_words[0].start_sec - start_sec)
            pause_after = max(0.0, end_sec - beat_words[-1].end_sec)
        else:
            pause_before = dur
            pause_after = dur

        # Mid-word cut check at beat end
        mid_word_cut = any(w.start_sec < end_sec < w.end_sec for w in all_words)
        if not mid_word_cut:
            clean_cuts += 1

        warnings: list[str] = []
        status = "OPTIMAL"

        if mid_word_cut:
            warnings.append(f"Cut at {end_sec:.2f}s cuts through a spoken word")

        if token_count > 0:
            if token_rate > rushed_thresh:
                status = "RUSHED"
                warnings.append(f"Rushed speech density: {token_rate} {unit_label} > {rushed_thresh}")
            elif token_rate < dragging_thresh:
                status = "DRAGGING"
                warnings.append(f"Dragging speech density: {token_rate} {unit_label} < {dragging_thresh}")

        if char_rate > max_cps:
            warnings.append(f"Subtitle reading speed too fast: {char_rate} CPS > {max_cps} max")

        beat_metrics.append(BeatPacingMetric(
            beat_id=beat_id,
            duration_sec=round(dur, 2),
            token_count=token_count,
            token_rate=token_rate,
            char_count=char_count,
            char_rate=char_rate,
            pause_gap_before_sec=round(pause_before, 2),
            pause_gap_after_sec=round(pause_after, 2),
            status=status,
            warnings=warnings,
        ))

    total_tokens = len(all_words)
    total_chars = sum(len(w.text) for w in all_words)
    avg_token_rate = round(total_tokens / max(0.1, total_duration), 2)
    avg_char_rate = round(total_chars / max(0.1, total_duration), 2)

    cut_score = round(clean_cuts / max(1, len(segments)), 2)

    # Compute overall pacing score (penalize rushed/dragging beats and dirty cuts)
    penalties = 0.0
    for m in beat_metrics:
        if m.status != "OPTIMAL":
            penalties += 0.05
        if any("cuts through" in w for w in m.warnings):
            penalties += 0.15
        if any("Subtitle reading speed" in w for w in m.warnings):
            penalties += 0.05

    overall_score = max(0.0, round(1.0 - penalties, 2))

    return PacingReport(
        episode_id=timeline.get("episode_id", "episode"),
        language=lang,
        total_duration_sec=round(total_duration, 2),
        total_tokens=total_tokens,
        avg_token_rate=avg_token_rate,
        avg_char_rate=avg_char_rate,
        beat_metrics=beat_metrics,
        cut_alignment_score=cut_score,
        overall_pacing_score=overall_score,
        warnings=episode_warnings,
    )


__all__ = ["audit_speech_pacing"]
