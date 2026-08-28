"""Visual strategy catalog + scored planner (spec sections 6, 10, 21).

Every semantic function offers MULTIPLE candidate strategies. Selection is a
weighted score with novelty penalties from recent visual history. Identical
composition signatures are forbidden; one family may run at most
`max_family_streak` consecutive beats.
"""
from __future__ import annotations

from dataclasses import dataclass

from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.domain.strategy import ScoredCandidate, SelectionRecord, StrategyDefinition
from videotool.domain.visual_history import HistoryEntry, VisualHistory

# Weighted score (spec section 10) - configurable via PlanningConfig.
DEFAULT_WEIGHTS = {
    "semantic_match": 0.40,
    "storytelling_value": 0.25,
    "visual_novelty": 0.20,
    "transition_quality": 0.10,
    "asset_quality": 0.05,
}

DEFAULT_PENALTIES = {
    "same_family_immediately_before": 0.18,
    "family_seen_in_recent_window": 0.15,
    "dense_strategy_for_thin_beat": 0.20,
    "thin_strategy_for_dense_beat": 0.20,
}

MAX_FAMILY_STREAK = 2

S = StrategyDefinition

STRATEGY_CATALOG: dict[str, StrategyDefinition] = {
    s.strategy_id: s for s in [
        # --- character / subject -------------------------------------
        S("archival_portrait", "archival_subject",
          ("CHARACTER_INTRODUCTION", "QUOTE", "TURNING_POINT"),
          "A person carried by an archival portrait plus identity metadata.",
          (0.1, 0.6), 0.85),
        S("portrait_plus_document", "archival_subject",
          ("CHARACTER_INTRODUCTION", "EVIDENCE", "CAUSAL_EXPLANATION"),
          "Portrait paired with a document the person signed or produced.",
          (0.4, 0.9), 0.8),
        S("portrait_plus_location", "archival_subject",
          ("CHARACTER_INTRODUCTION", "LOCATION_INTRODUCTION"),
          "Portrait contextualized by where the person acted.",
          (0.2, 0.7), 0.75),
        S("portrait_plus_quote", "archival_subject",
          ("CHARACTER_INTRODUCTION", "QUOTE"),
          "Portrait anchored by the person's own words.",
          (0.2, 0.6), 0.8),
        S("full_frame_archival", "archival_subject",
          ("HOOK", "ATMOSPHERE", "REVEAL", "SUMMARY", "CHARACTER_INTRODUCTION"),
          "One arresting archival frame allowed to breathe.",
          (0.0, 0.3), 0.7),
        S("silhouette_to_archive_reveal", "archival_subject",
          ("REVEAL", "TURNING_POINT"),
          "Withheld identity disclosed by progressive reveal.",
          (0.1, 0.4), 0.75),
        # --- documents / evidence -------------------------------------
        S("single_document_focus", "document_evidence",
          ("EVIDENCE", "QUOTE", "REVEAL"),
          "One primary source fills the frame; details highlighted.",
          (0.2, 0.6), 0.8),
        S("document_stack", "document_evidence",
          ("EVIDENCE", "ESCALATION", "ESTABLISHING_CONTEXT"),
          "Corroborating documents accumulate into a paper trail.",
          (0.5, 1.0), 0.8),
        S("document_plus_quote", "document_evidence",
          ("QUOTE", "EVIDENCE"),
          "Document shown alongside the sentence that matters.",
          (0.2, 0.7), 0.85),
        S("clip_plus_annotation", "document_evidence",
          ("EVIDENCE", "TECHNICAL_EXPLANATION", "COMPARISON"),
          "Region of the source enlarged and annotated.",
          (0.4, 0.9), 0.75),
        # --- geography ---------------------------------------------------
        S("region_map", "geographic_map",
          ("LOCATION_INTRODUCTION", "ESTABLISHING_CONTEXT", "ATMOSPHERE"),
          "Map that anchors a named place.",
          (0.1, 0.6), 0.8),
        S("route_map", "geographic_map",
          ("GEOGRAPHIC_MOVEMENT", "PROCESS", "CHRONOLOGY"),
          "Route drawn between origin and destination.",
          (0.3, 0.8), 0.9),
        S("map_plus_archival", "geographic_map",
          ("LOCATION_INTRODUCTION", "GEOGRAPHIC_MOVEMENT", "EVIDENCE"),
          "Map overlaid with archival imagery of the place.",
          (0.4, 0.9), 0.8),
        S("migration_flow_map", "geographic_map",
          ("GEOGRAPHIC_MOVEMENT", "ESCALATION", "DATA"),
          "Flow thickness communicates volume of movement.",
          (0.5, 1.0), 0.85),
        # --- chronology -------------------------------------------------
        S("linear_timeline", "chronological_timeline",
          ("CHRONOLOGY", "PROCESS", "ESTABLISHING_CONTEXT"),
          "Events ordered along one directional line.",
          (0.3, 0.9), 0.85),
        S("vertical_sequence", "chronological_timeline",
          ("CHRONOLOGY", "ESCALATION", "PROCESS"),
          "Events stack downward as pressure builds.",
          (0.3, 0.9), 0.75),
        S("branching_timeline", "chronological_timeline",
          ("CHRONOLOGY", "CAUSAL_EXPLANATION"),
          "Timeline that forks where outcomes diverge.",
          (0.5, 1.0), 0.8),
        # --- causal -------------------------------------------------------
        S("causal_network", "causal_network",
          ("CAUSAL_EXPLANATION", "ESCALATION", "ESTABLISHING_CONTEXT"),
          "Independent factors converging into one event.",
          (0.5, 1.0), 0.9),
        S("evidence_board", "causal_network",
          ("EVIDENCE", "CAUSAL_EXPLANATION", "REVEAL"),
          "People, documents and places connected into one investigation.",
          (0.6, 1.0), 0.85),
        S("cause_effect_pair", "causal_network",
          ("CAUSAL_EXPLANATION", "CONSEQUENCE", "COMPARISON"),
          "Cause and its consequence set against each other.",
          (0.3, 0.8), 0.85),
        S("object_relationship_diagram", "causal_network",
          ("TECHNICAL_EXPLANATION", "PROCESS"),
          "System parts and how they influence each other.",
          (0.5, 1.0), 0.75),
        # --- full frame -------------------------------------------------
        S("cinematic_hold", "full_frame_cinematic",
          ("HOOK", "ATMOSPHERE", "SUMMARY", "REVEAL", "TURNING_POINT"),
          "Full-bleed cinematic image; nothing competes with it.",
          (0.0, 0.3), 0.75),
        S("cinematic_plus_quote", "full_frame_cinematic",
          ("QUOTE", "ATMOSPHERE", "SUMMARY"),
          "Full-bleed image with one editorial line of text.",
          (0.1, 0.4), 0.8),
        # --- paper collage hero -----------------------------------------
        S("paper_collage_opener", "paper_collage_hero",
          ("ESTABLISHING_CONTEXT", "HOOK", "SUMMARY", "LOCATION_INTRODUCTION"),
          "Editorial torn-paper sidebar with chapter badge, context text and hero backdrop.",
          (0.2, 0.8), 0.88),
        S("editorial_collage_quote", "paper_collage_hero",
          ("QUOTE", "TURNING_POINT", "EVIDENCE"),
          "Torn-paper editorial layout anchoring prominent keyword-highlighted quote banner.",
          (0.3, 0.9), 0.86),
    ]
}

# Primary candidate pools per semantic function (planner may add cross-function
# candidates when beat entities justify them).
FUNCTION_CANDIDATES: dict[SemanticFunction, list[str]] = {
    SemanticFunction.HOOK: ["paper_collage_opener", "cinematic_hold", "full_frame_archival", "silhouette_to_archive_reveal"],
    SemanticFunction.ESTABLISHING_CONTEXT: ["paper_collage_opener", "region_map", "document_stack", "causal_network", "linear_timeline"],
    SemanticFunction.CHARACTER_INTRODUCTION: ["archival_portrait", "portrait_plus_document", "portrait_plus_location", "portrait_plus_quote", "full_frame_archival", "cinematic_hold"],
    SemanticFunction.LOCATION_INTRODUCTION: ["region_map", "map_plus_archival", "portrait_plus_location"],
    SemanticFunction.CHRONOLOGY: ["linear_timeline", "vertical_sequence", "branching_timeline", "route_map"],
    SemanticFunction.CAUSAL_EXPLANATION: ["causal_network", "evidence_board", "cause_effect_pair", "branching_timeline", "document_stack", "object_relationship_diagram"],
    SemanticFunction.EVIDENCE: ["single_document_focus", "document_stack", "clip_plus_annotation", "evidence_board", "document_plus_quote"],
    SemanticFunction.COMPARISON: ["cause_effect_pair", "clip_plus_annotation"],
    SemanticFunction.PROCESS: ["route_map", "vertical_sequence", "linear_timeline", "object_relationship_diagram"],
    SemanticFunction.TECHNICAL_EXPLANATION: ["object_relationship_diagram", "clip_plus_annotation"],
    SemanticFunction.ESCALATION: ["migration_flow_map", "document_stack", "causal_network", "vertical_sequence"],
    SemanticFunction.TURNING_POINT: ["editorial_collage_quote", "silhouette_to_archive_reveal", "full_frame_archival", "cinematic_hold"],
    SemanticFunction.CONSEQUENCE: ["cause_effect_pair", "cinematic_hold", "map_plus_archival"],
    SemanticFunction.QUOTE: ["editorial_collage_quote", "document_plus_quote", "portrait_plus_quote", "single_document_focus", "cinematic_plus_quote"],
    SemanticFunction.DATA: ["migration_flow_map", "linear_timeline", "document_stack"],
    SemanticFunction.GEOGRAPHIC_MOVEMENT: ["route_map", "migration_flow_map", "map_plus_archival", "vertical_sequence"],
    SemanticFunction.ATMOSPHERE: ["cinematic_hold", "full_frame_archival", "region_map"],
    SemanticFunction.REVEAL: ["silhouette_to_archive_reveal", "single_document_focus", "cinematic_hold"],
    SemanticFunction.TRANSITION: ["region_map", "cinematic_hold"],
    SemanticFunction.SUMMARY: ["paper_collage_opener", "cinematic_plus_quote", "cinematic_hold", "full_frame_archival"],
}

# transition compatibility between previous function family and candidate
# (high-level heuristic; refined again by the transition planner)
_TRANSITION_AFFINITY: dict[str, set[str]] = {
    "map_like": {"geographic_map"},
    "document_like": {"document_evidence"},
    "person_like": {"archival_subject"},
    "time_like": {"chronological_timeline"},
    "logic_like": {"causal_network"},
    "mood_like": {"full_frame_cinematic"},
    "editorial_like": {"paper_collage_hero"},
}


def _transition_quality(prev_family: str | None, candidate_family: str) -> float:
    """Transition scoring using the actual previous visual family."""
    if not prev_family:
        return 1.0
    # moving between family "modes" reads as an editorial change - good
    if prev_family == candidate_family:
        return 0.55
    return 0.9


@dataclass
class PlanningConfig:
    weights: dict = None           # type: ignore[assignment]
    penalties: dict = None         # type: ignore[assignment]
    max_family_streak: int = MAX_FAMILY_STREAK

    def __post_init__(self):
        self.weights = {**DEFAULT_WEIGHTS, **(self.weights or {})}
        self.penalties = {**DEFAULT_PENALTIES, **(self.penalties or {})}


class StrategyPlanner:
    """Scores candidate strategies per beat against semantic fit + novelty."""

    def __init__(self, config: PlanningConfig | None = None):
        self.config = config or PlanningConfig()

    def candidates_for(self, beat: SemanticBeat) -> list[StrategyDefinition]:
        ids = list(FUNCTION_CANDIDATES.get(beat.semantic_function, ["cinematic_hold"]))
        # entity-driven cross candidates keep selection meaning-based
        if beat.locations and "region_map" not in ids:
            ids.append("region_map")
        if beat.dates and "linear_timeline" not in ids:
            ids.append("linear_timeline")
        return [STRATEGY_CATALOG[i] for i in ids if i in STRATEGY_CATALOG]

    def select(
        self,
        beats: list[SemanticBeat],
        history: VisualHistory | None = None,
        intents: dict[str, Any] | None = None,
    ) -> list[SelectionRecord]:
        """Score candidates per beat with optional AI Editorial Director intent.

        The planner simulates its own selections into `history` as it walks
        the beats, so novelty penalties and streak limits apply BETWEEN beats
        even though compositions are generated later.
        """
        history = history if history is not None else VisualHistory()
        records: list[SelectionRecord] = []
        for i, beat in enumerate(beats):
            intent = intents.get(beat.beat_id) if intents else None
            record = self._select_one(beat, beats[i - 1] if i else None, history, intent=intent)
            records.append(record)
            history.record(HistoryEntry(
                beat_id=beat.beat_id,
                visual_family=record.visual_family,
                strategy=record.selected_strategy,
                composition_signature=f"planned:{record.selected_strategy}",
                information_density=beat.information_density,
            ))
        return records

    def _select_one(
        self,
        beat: SemanticBeat,
        prev_beat: SemanticBeat | None,
        history: VisualHistory,
        intent: Any | None = None,
    ) -> SelectionRecord:
        candidates = self.candidates_for(beat)
        scored: list[ScoredCandidate] = []
        streak_family, streak_len = history.family_streak()
        at_streak_limit = (streak_len >= self.config.max_family_streak)

        recent = history.recent(1)
        prev_family: str | None = recent[0].visual_family if recent else None

        for cand in candidates:
            scores: dict[str, float] = {}
            scores["semantic_match"] = self._semantic_match(beat, cand)
            scores["storytelling_value"] = self._storytelling(beat, cand)
            scores["visual_novelty"] = self._novelty(history, cand)
            scores["transition_quality"] = _transition_quality(prev_family, cand.visual_family)
            scores["asset_quality"] = self._asset_quality(beat, cand)

            penalty = 0.0
            rejected = ""
            recent = history.recent(1)
            if recent and recent[0].visual_family == cand.visual_family:
                penalty += self.config.penalties["same_family_immediately_before"]
                rejected = f"family {cand.visual_family} used on previous beat"
            if at_streak_limit and cand.visual_family == streak_family:
                penalty = 1.0
                rejected = (f"family streak limit "
                            f"({self.config.max_family_streak}) reached for "
                            f"{streak_family}")
            density_lo, density_hi = cand.density_fit
            if beat.information_density < density_lo - 0.15:
                penalty += self.config.penalties["thin_strategy_for_dense_beat"]
            if beat.information_density > density_hi + 0.15:
                penalty += self.config.penalties["dense_strategy_for_thin_beat"]

            total = sum(scores[k] * w for k, w in self.config.weights.items())
            total = round(max(0.0, total - penalty), 4)

            # Optional Bounded AI Editorial Director nudge (Phase 3A)
            if (
                intent is not None
                and not getattr(intent, "is_fallback", False)
                and float(getattr(intent, "confidence", 0.0)) > 0.0
                and not at_streak_limit  # AI never overrides hard streak limits
            ):
                max_ai_delta = 0.10
                ai_weight = min(max(float(getattr(intent, "confidence", 1.0)), 0.0), 1.0)
                ai_delta = 0.0

                cand_strats = getattr(intent, "candidate_strategies", [])
                if cand.strategy_id in cand_strats:
                    ai_delta += max_ai_delta * ai_weight

                avoid_fams = getattr(intent, "avoid_visual_families", [])
                if cand.visual_family in avoid_fams:
                    ai_delta -= max_ai_delta * ai_weight

                pref_fams = getattr(intent, "preferred_visual_families", [])
                if cand.visual_family in pref_fams:
                    ai_delta += (max_ai_delta * 0.5) * ai_weight

                # Clamp AI delta within [-max_ai_delta, max_ai_delta]
                ai_delta = max(-max_ai_delta, min(max_ai_delta, ai_delta))
                total = round(max(0.0, min(1.0, total + ai_delta)), 4)
                scores["ai_alignment"] = round(ai_delta, 3)

            scored.append(ScoredCandidate(
                strategy_id=cand.strategy_id,
                visual_family=cand.visual_family,
                scores={k: round(v, 3) for k, v in scores.items()},
                total=total,
                rejected_reason=rejected,
            ))

        scored.sort(key=lambda c: (-c.total, c.strategy_id))
        winner = scored[0]
        cand_def = STRATEGY_CATALOG[winner.strategy_id]
        novelty = winner.scores["visual_novelty"]
        reason = self._reason(beat, cand_def, prev_beat, novelty, scored[1:])
        return SelectionRecord(
            beat_id=beat.beat_id,
            semantic_function=beat.semantic_function.value,
            selected_strategy=winner.strategy_id,
            visual_family=cand_def.visual_family,
            reason=reason,
            novelty_score=novelty,
            rejected_recent_family=(history.recent(1)[0].visual_family
                                    if history.recent(1) else None),
            candidates=scored,
        )

    # ---- component scores --------------------------------------------
    def _semantic_match(self, beat: SemanticBeat, cand: StrategyDefinition) -> float:
        base = 1.0 if beat.semantic_function.value in cand.functions else 0.35
        n = len(cand.functions)
        return round(min(1.0, base + 0.02 * n), 3)

    def _storytelling(self, beat: SemanticBeat, cand: StrategyDefinition) -> float:
        v = cand.base_storytelling_value
        if beat.semantic_function.value in cand.functions:
            v += 0.05
        if beat.entities and "portrait" in cand.strategy_id:
            v += 0.05
        if beat.locations and "map" in cand.strategy_id:
            v += 0.05
        if beat.relationships and "causal" in cand.strategy_id:
            v += 0.05
        return round(min(1.0, v), 3)

    def _novelty(self, history: VisualHistory, cand: StrategyDefinition) -> float:
        fam_rec = history.family_recency(cand.visual_family)
        # family never seen = fully novel
        return round(fam_rec, 3)

    def _asset_quality(self, beat: SemanticBeat, cand: StrategyDefinition) -> float:
        has_people = bool(beat.entities)
        has_places = bool(beat.locations)
        has_docs = bool(beat.objects)
        fam = cand.visual_family
        score = 0.5
        if fam == "archival_subject" and has_people:
            score = 0.9
        elif fam == "geographic_map" and has_places:
            score = 0.9
        elif fam == "document_evidence" and has_docs:
            score = 0.9
        elif fam == "causal_network" and (has_people or has_docs or has_places):
            score = 0.8
        elif fam == "chronological_timeline" and beat.dates:
            score = 0.9
        elif fam == "full_frame_cinematic":
            score = 0.7
        return score

    def _reason(self, beat: SemanticBeat, cand: StrategyDefinition,
                prev_beat: SemanticBeat | None, novelty: float,
                others: list[ScoredCandidate]) -> str:
        intent = beat.visual_intent[:1].lower() + beat.visual_intent[1:]
        runner = others[0].strategy_id if others else "none"
        return (f"Beat intends to {intent}. '{cand.strategy_id}' fits "
                f"{beat.semantic_function.value} because: {cand.storytelling_note} "
                f"Runner-up '{runner}' scored lower on novelty/fit "
                f"(novelty={novelty:.2f}).")
