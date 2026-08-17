"""Semantic phrase alignment and composition-layer timing bindings (Phase 2B)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass

from videotool.domain.composition import LayerType, VisualComposition
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.domain.timing import (AnchorType, NarrationTiming,
                                     SemanticAnchor, TimingBinding)
from videotool.editorial.media.ranking import fold, tokens

ANCHOR_EXTRACTION_VERSION = 1
TIMING_BINDING_VERSION = 1
MOTION_TIMING_VERSION = 2


@dataclass(frozen=True)
class EditorialTimingPolicy:
    entity_lead_sec: float = 0.18
    location_lead_sec: float = 0.12
    date_lead_sec: float = 0.08
    event_lead_sec: float = 0.10
    relationship_lead_sec: float = 0.0
    default_lead_sec: float = 0.08
    portrait_min_visibility_sec: float = 1.5
    document_min_visibility_sec: float = 2.0
    map_min_visibility_sec: float = 1.0
    quote_min_visibility_sec: float = 0.8
    label_min_visibility_sec: float = 1.0
    default_min_visibility_sec: float = 0.8
    collision_window_sec: float = 0.30
    max_high_salience_entrances: int = 2
    collision_stagger_sec: float = 0.16
    entrance_duration_sec: float = 0.45
    emphasis_duration_sec: float = 0.50
    exit_duration_sec: float = 0.35
    minimum_event_duration_sec: float = 0.01
    fallback_ratio: float = 0.35

    def to_dict(self) -> dict:
        return asdict(self)

    def lead_for(self, anchor_type: AnchorType | None) -> float:
        return {
            AnchorType.ENTITY_MENTION: self.entity_lead_sec,
            AnchorType.LOCATION_MENTION: self.location_lead_sec,
            AnchorType.DATE_MENTION: self.date_lead_sec,
            AnchorType.EVENT_MENTION: self.event_lead_sec,
            AnchorType.RELATIONSHIP: self.relationship_lead_sec,
            AnchorType.CAUSE: self.relationship_lead_sec,
            AnchorType.EFFECT: self.relationship_lead_sec,
            AnchorType.CONTRAST: self.relationship_lead_sec,
            AnchorType.QUOTE_MENTION: 0.0,
            AnchorType.EMPHASIS: 0.0,
            AnchorType.REVEAL: 0.0,
        }.get(anchor_type, self.default_lead_sec)

    def minimum_visibility_for(self, layer) -> float:
        if layer.type == LayerType.DOCUMENT or layer.role == "document":
            return self.document_min_visibility_sec
        if layer.type == LayerType.MAP or layer.role == "map":
            return self.map_min_visibility_sec
        if layer.type == LayerType.IMAGE and layer.role == "hero":
            return self.portrait_min_visibility_sec
        if layer.type in (LayerType.TEXT, LayerType.LABEL):
            return (self.quote_min_visibility_sec if layer.role == "hero"
                    else self.label_min_visibility_sec)
        return self.default_min_visibility_sec


def validate_narration_timing(timing: NarrationTiming) -> list[str]:
    errors: list[str] = []
    previous_end = -1.0
    for expected_index, word in enumerate(timing.words):
        if word.index != expected_index:
            errors.append(f"word index {word.index} is not contiguous")
        if not word.text.strip():
            errors.append(f"word {word.index} is empty")
        if word.start_sec < 0 or word.end_sec < word.start_sec:
            errors.append(f"word {word.index} has invalid range")
        if word.start_sec + 1e-6 < previous_end:
            errors.append(f"word {word.index} overlaps previous word")
        if not 0.0 <= word.confidence <= 1.0:
            errors.append(f"word {word.index} has invalid confidence")
        previous_end = word.end_sec
    if not timing.words:
        errors.append("narration timing has no words")
    elif abs(timing.duration_sec - timing.words[-1].end_sec) > 0.01:
        errors.append("duration does not match final word")
    if not timing.source or not timing.provider or timing.provider_version <= 0:
        errors.append("timing provenance missing")
    return errors


def _flat_words(timing: NarrationTiming, beat: SemanticBeat):
    flat: list[tuple[str, int]] = []
    for word in timing.words[beat.word_start:beat.word_end]:
        for term in fold(word.text).split():
            if term:
                flat.append((term, word.index))
    return flat


def _phrase_match(timing: NarrationTiming, beat: SemanticBeat, phrase: str,
                  allow_surname: bool = False):
    wanted = fold(phrase).split()
    if not wanted:
        return None
    flat = _flat_words(timing, beat)
    candidates = [(wanted, "exact_phrase", 1.0)]
    if allow_surname and len(wanted) > 1 and len(wanted[-1]) >= 4:
        candidates.append(([wanted[-1]], "alias_match", 0.9))
    for terms, source, confidence in candidates:
        width = len(terms)
        for index in range(0, len(flat) - width + 1):
            if [part[0] for part in flat[index:index + width]] == terms:
                first = flat[index][1]
                last = flat[index + width - 1][1]
                return first, last + 1, source, confidence
    return None


def _anchor_id(beat_id: str, anchor_type: AnchorType, text: str,
               ordinal: int) -> str:
    raw = f"{beat_id}|{anchor_type.value}|{fold(text)}|{ordinal}"
    return "anchor:" + hashlib.sha256(raw.encode()).hexdigest()[:20]


def _make_anchor(timing: NarrationTiming, beat: SemanticBeat,
                 anchor_type: AnchorType, text: str, ordinal: int,
                 match, importance: float = 0.7) -> SemanticAnchor:
    if match is None:
        midpoint = min(max(beat.word_start, (beat.word_start + beat.word_end) // 2),
                       max(beat.word_start, beat.word_end - 1))
        first, last = midpoint, min(midpoint + 1, len(timing.words))
        source, confidence = "semantic_fallback", 0.5
    else:
        first, last, source, confidence = match
    word_slice = timing.words[first:last]
    if word_slice:
        confidence = min(confidence, min(word.confidence for word in word_slice))
    if timing.is_estimated and source in {"exact_phrase", "alias_match"}:
        source = "estimated_phrase"
    start = word_slice[0].start_sec if word_slice else beat.start_sec
    end = word_slice[-1].end_sec if word_slice else beat.end_sec
    kwargs = {}
    if anchor_type == AnchorType.ENTITY_MENTION:
        kwargs["entity_ids"] = [text]
    elif anchor_type == AnchorType.LOCATION_MENTION:
        kwargs["location_ids"] = [text]
    elif anchor_type == AnchorType.EVENT_MENTION:
        kwargs["event_ids"] = [text]
    elif anchor_type in (AnchorType.RELATIONSHIP, AnchorType.CAUSE,
                         AnchorType.EFFECT, AnchorType.CONTRAST):
        kwargs["relationship_ids"] = [text]
    return SemanticAnchor(
        anchor_id=_anchor_id(beat.beat_id, anchor_type, text, ordinal),
        beat_id=beat.beat_id, anchor_type=anchor_type, text=text,
        normalized_terms=fold(text).split(), start_sec=round(start, 3),
        end_sec=round(end, 3), word_start=first, word_end=last,
        importance=importance, resolution_source=source,
        confidence=confidence, **kwargs)


def extract_semantic_anchors(timing: NarrationTiming,
                             beats: list[SemanticBeat]) -> list[SemanticAnchor]:
    anchors: list[SemanticAnchor] = []
    for beat in beats:
        specs = [
            (AnchorType.ENTITY_MENTION, beat.entities, True, 0.9),
            (AnchorType.LOCATION_MENTION, beat.locations, False, 0.85),
            (AnchorType.DATE_MENTION, beat.dates, False, 0.8),
            (AnchorType.EVENT_MENTION, beat.events, False, 0.8),
            (AnchorType.EVENT_MENTION, beat.objects, False, 0.7),
        ]
        ordinal = 0
        for anchor_type, concepts, aliases, importance in specs:
            for concept in dict.fromkeys(str(c) for c in concepts if str(c).strip()):
                match = _phrase_match(timing, beat, concept, aliases)
                anchors.append(_make_anchor(timing, beat, anchor_type, concept,
                                            ordinal, match, importance))
                ordinal += 1

        if beat.semantic_function == SemanticFunction.QUOTE:
            quoted = re.findall(r'["\u201c]([^"\u201d]+)["\u201d]',
                                beat.narration_text)
            for phrase in quoted:
                anchors.append(_make_anchor(
                    timing, beat, AnchorType.QUOTE_MENTION, phrase, ordinal,
                    _phrase_match(timing, beat, phrase), 0.9))
                ordinal += 1

        # A compact, topic-independent action vocabulary recovers explicit
        # documentary events that the lightweight beat analyzer may not label.
        event_terms = {"opened", "closed", "crossed", "fled", "spread",
                       "protest", "protests", "evacuation", "evacuated",
                       "collapsed", "exploded", "struck", "sank", "launched",
                       "landed", "announced", "refused", "intervene"}
        existing_event_terms = {term for anchor in anchors
                                if anchor.beat_id == beat.beat_id
                                and anchor.anchor_type == AnchorType.EVENT_MENTION
                                for term in anchor.normalized_terms}
        for word in timing.words[beat.word_start:beat.word_end]:
            normalized = fold(word.text)
            if normalized in event_terms and normalized not in existing_event_terms:
                match = (word.index, word.index + 1, "exact_phrase", 1.0)
                anchors.append(_make_anchor(
                    timing, beat, AnchorType.EVENT_MENTION, word.text, ordinal,
                    match, 0.75))
                existing_event_terms.add(normalized)
                ordinal += 1

        # Numeric documentary cues are anchored directly from spoken tokens.
        number_words = {"one", "two", "three", "four", "five", "six",
                        "seven", "eight", "nine", "ten", "hundred",
                        "thousand", "thousands", "million", "millions",
                        "billion", "billions"}
        for word in timing.words[beat.word_start:beat.word_end]:
            normalized = fold(word.text)
            if re.search(r"\d", word.text) or normalized in number_words:
                match = (word.index, word.index + 1, "exact_phrase", 1.0)
                anchors.append(_make_anchor(
                    timing, beat, AnchorType.NUMBER_MENTION, word.text, ordinal,
                    match, 0.75))
                ordinal += 1

        relationship_type = {
            SemanticFunction.CAUSAL_EXPLANATION: AnchorType.CAUSE,
            SemanticFunction.CONSEQUENCE: AnchorType.EFFECT,
            SemanticFunction.COMPARISON: AnchorType.CONTRAST,
            SemanticFunction.REVEAL: AnchorType.REVEAL,
        }.get(beat.semantic_function, AnchorType.RELATIONSHIP)
        for relation in dict.fromkeys(str(r) for r in beat.relationships
                                      if str(r).strip()):
            match = _phrase_match(timing, beat, relation)
            anchors.append(_make_anchor(timing, beat, relationship_type,
                                        relation, ordinal, match, 0.75))
            ordinal += 1

        # Generic emphasis cues support punch timing without topic vocabulary.
        emphasis_terms = {"immediately", "suddenly", "finally", "never",
                          "forever", "only", "without"}
        for word in timing.words[beat.word_start:beat.word_end]:
            normalized = fold(word.text)
            if normalized in emphasis_terms:
                match = (word.index, word.index + 1, "exact_phrase", 1.0)
                anchors.append(_make_anchor(
                    timing, beat, AnchorType.EMPHASIS, word.text, ordinal,
                    match, 0.85))
                ordinal += 1
    return anchors


def validate_anchors(anchors: list[SemanticAnchor], beats: list[SemanticBeat],
                     timing: NarrationTiming) -> list[str]:
    errors: list[str] = []
    beat_by_id = {b.beat_id: b for b in beats}
    seen: set[str] = set()
    for anchor in anchors:
        beat = beat_by_id.get(anchor.beat_id)
        if anchor.anchor_id in seen:
            errors.append(f"duplicate anchor {anchor.anchor_id}")
        seen.add(anchor.anchor_id)
        if beat is None:
            errors.append(f"{anchor.anchor_id}: unknown beat")
            continue
        if not (beat.word_start <= anchor.word_start < anchor.word_end <= beat.word_end):
            errors.append(f"{anchor.anchor_id}: word span outside beat")
        if anchor.start_sec < beat.start_sec - 0.01 or anchor.end_sec > beat.end_sec + 0.01:
            errors.append(f"{anchor.anchor_id}: time outside beat")
        if anchor.end_sec < anchor.start_sec:
            errors.append(f"{anchor.anchor_id}: invalid range")
        if anchor.word_end > len(timing.words):
            errors.append(f"{anchor.anchor_id}: word span outside narration")
        if not 0 <= anchor.confidence <= 1 or not anchor.resolution_source:
            errors.append(f"{anchor.anchor_id}: invalid resolution metadata")
    return errors


def annotate_composition_semantics(composition: VisualComposition,
                                   beat: SemanticBeat) -> None:
    concepts = list(dict.fromkeys(beat.entities + beat.locations + beat.dates
                                  + beat.events + beat.objects
                                  + beat.relationships))
    connector_index = 0
    connector_count = sum(
        1 for layer in composition.layers
        if layer.type in (LayerType.ARROW, LayerType.LINE)
        or layer.role == "connector")
    for layer in composition.layers:
        haystack = fold(" ".join([layer.text or "", layer.reason]))
        refs = [concept for concept in concepts
                if tokens(concept) and tokens(concept) & tokens(haystack)]
        if layer.type == LayerType.MAP or layer.role == "map":
            refs.extend(beat.locations)
        elif layer.type == LayerType.DOCUMENT or layer.role == "document":
            refs.extend(beat.objects or beat.events)
        elif layer.type in (LayerType.ARROW, LayerType.LINE) or layer.role == "connector":
            refs.extend(beat.relationships or beat.events)
            if beat.locations and connector_count != 1:
                location_index = (connector_index - 1
                                  if connector_count >= 3 else connector_index)
                if location_index >= 0:
                    refs.append(beat.locations[min(location_index,
                                                   len(beat.locations) - 1)])
            connector_index += 1
        elif layer.role == "hero":
            refs.extend(beat.entities or beat.events or beat.locations)
        elif layer.type in (LayerType.TEXT, LayerType.LABEL):
            refs.extend(beat.entities + beat.locations + beat.dates)
        layer.semantic_refs = list(dict.fromkeys(str(ref) for ref in refs
                                                if str(ref).strip()))


def _preferred_types(layer) -> set[AnchorType]:
    if layer.type == LayerType.MAP or layer.role == "map":
        return {AnchorType.LOCATION_MENTION}
    if layer.type == LayerType.DOCUMENT or layer.role == "document":
        return {AnchorType.EVENT_MENTION, AnchorType.QUOTE_MENTION,
                AnchorType.EMPHASIS}
    if layer.type == LayerType.IMAGE and layer.role == "hero":
        return {AnchorType.ENTITY_MENTION, AnchorType.EVENT_MENTION}
    if layer.type in (LayerType.ARROW, LayerType.LINE) or layer.role == "connector":
        return {AnchorType.RELATIONSHIP, AnchorType.CAUSE, AnchorType.EFFECT,
                AnchorType.CONTRAST, AnchorType.EVENT_MENTION,
                AnchorType.EMPHASIS, AnchorType.REVEAL}
    if layer.type in (LayerType.TEXT, LayerType.LABEL):
        return {AnchorType.ENTITY_MENTION, AnchorType.LOCATION_MENTION,
                AnchorType.DATE_MENTION, AnchorType.NUMBER_MENTION,
                AnchorType.EMPHASIS}
    return {AnchorType.EVENT_MENTION, AnchorType.ENTITY_MENTION}


def build_timing_bindings(beats: list[SemanticBeat],
                          compositions: list[VisualComposition],
                          anchors: list[SemanticAnchor],
                          policy: EditorialTimingPolicy
                          ) -> list[TimingBinding]:
    beat_by_id = {b.beat_id: b for b in beats}
    anchors_by_beat: dict[str, list[SemanticAnchor]] = {}
    for anchor in anchors:
        anchors_by_beat.setdefault(anchor.beat_id, []).append(anchor)
    bindings: list[TimingBinding] = []
    for comp in compositions:
        beat = beat_by_id[comp.beat_id]
        available = anchors_by_beat.get(comp.beat_id, [])
        unreferenced_preferred_index = 0
        for layer in comp.layers:
            preferred = _preferred_types(layer)
            scored = []
            layer_anchors = [] if layer.type == LayerType.TEXTURE else available
            for anchor in layer_anchors:
                anchor_terms = set(anchor.normalized_terms)
                score = 2.0 if anchor.anchor_type in preferred else 0.0
                for ref in layer.semantic_refs:
                    ref_terms = tokens(ref)
                    if ref_terms and ref_terms == anchor_terms:
                        score += 10.0
                    elif ref_terms and ref_terms <= anchor_terms:
                        score += 8.0
                    elif ref_terms & anchor_terms:
                        score += 4.0 * len(ref_terms & anchor_terms)
                    if fold(ref) == fold(anchor.text):
                        if (ref in beat.entities
                                and anchor.anchor_type == AnchorType.ENTITY_MENTION):
                            score += 3.0
                        if (ref in beat.locations
                                and anchor.anchor_type == AnchorType.LOCATION_MENTION):
                            score += 3.0
                            if (layer.role == "connector"
                                    or layer.type in (LayerType.ARROW,
                                                      LayerType.LINE)):
                                score += 2.0
                        if (ref in beat.dates
                                and anchor.anchor_type == AnchorType.DATE_MENTION):
                            score += 3.0
                        if ((ref in beat.events or ref in beat.objects)
                                and anchor.anchor_type == AnchorType.EVENT_MENTION):
                            score += 3.0
                if score > 0:
                    scored.append((score, anchor.confidence,
                                   -anchor.start_sec, anchor.anchor_id, anchor))
            if scored and not layer.semantic_refs:
                ordered = sorted((item[-1] for item in scored),
                                 key=lambda anchor: (anchor.start_sec,
                                                     anchor.anchor_id))
                chosen = ordered[min(unreferenced_preferred_index,
                                     len(ordered) - 1)]
                unreferenced_preferred_index += 1
            else:
                chosen = max(scored)[-1] if scored else None
            if chosen is not None:
                start, end = chosen.start_sec, chosen.end_sec
                source = chosen.resolution_source
                confidence = chosen.confidence
                reason = (f"Layer represents {layer.semantic_refs or [layer.role]}; "
                          f"bound to {chosen.anchor_type.value} '{chosen.text}' "
                          f"via {source}.")
                anchor_id = chosen.anchor_id
            else:
                fallback_ratio = (0.0 if layer.type == LayerType.TEXTURE
                                  else (layer.enter_at
                                        if layer.enter_at > 0
                                        else policy.fallback_ratio))
                start = beat.start_sec + beat.duration_sec * max(
                    0.0, min(1.0, fallback_ratio))
                end = min(beat.end_sec, start + policy.default_min_visibility_sec)
                source = "beat_fallback"
                confidence = 0.3
                anchor_id = None
                reason = ("No spoken semantic anchor matched this inferred layer; "
                          "used deterministic beat fallback.")
            raw = f"{comp.composition_id}|{layer.id}"
            bindings.append(TimingBinding(
                binding_id="binding:" + hashlib.sha256(raw.encode()).hexdigest()[:20],
                beat_id=beat.beat_id, composition_id=comp.composition_id,
                layer_id=layer.id, semantic_refs=list(layer.semantic_refs),
                anchor_id=anchor_id, start_sec=round(start, 3),
                end_sec=round(end, 3), source=source,
                confidence=confidence, reason=reason))
    return bindings


def validate_timing_bindings(bindings: list[TimingBinding],
                             beats: list[SemanticBeat],
                             compositions: list[VisualComposition],
                             anchors: list[SemanticAnchor]) -> list[str]:
    errors: list[str] = []
    beat_by_id = {b.beat_id: b for b in beats}
    anchor_ids = {a.anchor_id for a in anchors}
    layer_keys = {(c.composition_id, layer.id)
                  for c in compositions for layer in c.layers}
    expected = len(layer_keys)
    seen: set[tuple[str, str]] = set()
    for binding in bindings:
        key = (binding.composition_id, binding.layer_id)
        if key not in layer_keys:
            errors.append(f"{binding.binding_id}: unknown layer")
        if key in seen:
            errors.append(f"duplicate binding for {binding.layer_id}")
        seen.add(key)
        beat = beat_by_id.get(binding.beat_id)
        if beat is None or not (beat.start_sec - 0.01 <= binding.start_sec
                                <= binding.end_sec <= beat.end_sec + 0.01):
            errors.append(f"{binding.binding_id}: range outside beat")
        if binding.anchor_id is not None and binding.anchor_id not in anchor_ids:
            errors.append(f"{binding.binding_id}: unknown anchor")
        if not 0 <= binding.confidence <= 1 or not binding.source:
            errors.append(f"{binding.binding_id}: invalid confidence/source")
    if len(seen) != expected:
        errors.append(f"timing bindings cover {len(seen)} of {expected} layers")
    return errors
