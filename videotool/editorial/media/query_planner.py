"""Deterministic semantic search planner (Phase 2A spec sections 6-7).

Search queries are built from the requirement's semantic terms (entities,
locations, dates, events) - never from generic scene descriptions like
"historical photo". Deterministic by default; an AI query-expansion
provider can be plugged in later behind the same interface.
"""
from __future__ import annotations

import re

from videotool.domain.assets import AssetRequirement
from videotool.domain.semantic_beat import SemanticBeat
from videotool.editorial.media.models import MediaSearchPlan

MEDIA_QUERY_VERSION = 1

# queries shaped like these must never be generated (spec section 38)
FORBIDDEN_GENERIC_QUERIES = {
    "historical photo", "old city", "war image", "documentary image",
    "historical footage", "archive texture", "generic newspaper",
}

_KIND_CONTEXT = {
    "portrait": "portrait",
    "document": "document",
    "map": "map",
    "photo": "",
    "illustration": "illustration",
}

_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")


def _clean_terms(terms: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for t in terms:
        t = (t or "").strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def build_search_plan(requirement: AssetRequirement,
                      beat: SemanticBeat | None = None) -> MediaSearchPlan:
    entities = _clean_terms(list(requirement.entities) +
                            (beat.entities if beat else []))
    locations = _clean_terms(beat.locations if beat else [])
    narration_dates = _YEAR_RE.findall(beat.narration_text if beat else "")
    desc_dates = _YEAR_RE.findall(requirement.description)
    dates = _clean_terms((beat.dates if beat else []) + desc_dates + narration_dates)
    events = _clean_terms(beat.events if beat else [])
    kind_context = _KIND_CONTEXT.get(requirement.kind, "")

    # primary: requirement's own entities take precedence; if multiple entities in requirement, join them
    req_entities = _clean_terms(list(requirement.entities))
    if len(req_entities) >= 2:
        lead_entity = " ".join(req_entities[:2])
    elif req_entities:
        lead_entity = req_entities[0]
    elif entities:
        lead_entity = entities[0]
    else:
        lead_entity = ""

    primary_terms = [lead_entity, kind_context]
    primary_date = dates[0] if dates else ""
    if primary_date and primary_date not in lead_entity:
        primary_terms.append(primary_date)
    primary_query = " ".join(t for t in primary_terms if t).strip()
    if not primary_query:
        # no entity/date/location at all: the beat's own narration words are
        # the most semantic query available (never a generic scene term)
        primary_query = " ".join((beat.narration_text if beat else "").split()[:6])

    alternates: list[str] = []
    if entities:
        # full entity set + strongest location
        alt = " ".join(entities[:2] + ([kind_context] if kind_context else []))
        alternates.append(alt.strip())
        if len(entities[0].split()) > 1:
            # surname-only form is a common archive search pattern
            surname = entities[0].split()[-1]
            alternates.append(" ".join(
                t for t in [surname, kind_context, primary_date] if t))
    if locations:
        alternates.append(" ".join(
            t for t in [locations[0], kind_context] if t))
        if lead_entity:
            alternates.append(" ".join([lead_entity, locations[0]] +
                                       ([primary_date] if primary_date else [])))
    if events:
        alternates.append(" ".join(
            t for t in [events[0].title(), primary_date] if t))
    if dates and len(dates) > 1:
        alternates.append(" ".join(
            t for t in [lead_entity, dates[-1], kind_context] if t))

    # de-dup, drop empties and generic-only strings, keep order
    seen: set[str] = set()
    cleaned_alternates: list[str] = []
    for q in alternates:
        q = re.sub(r"\s+", " ", q).strip()
        key = q.lower()
        if (q and key != primary_query.lower() and key not in seen
                and key not in FORBIDDEN_GENERIC_QUERIES):
            seen.add(key)
            cleaned_alternates.append(q)

    return MediaSearchPlan(
        requirement_id=requirement.requirement_id,
        requirement_kind=requirement.kind,
        primary_query=primary_query,
        alternate_queries=cleaned_alternates[:4],
        entity_terms=entities[:6],
        location_terms=locations[:4],
        date_terms=dates[:4],
        event_terms=events[:3],
        negative_terms=["stock", "generic", "texture"],
    )


def plan_search(requirements: list[AssetRequirement],
                beats: list[SemanticBeat]) -> list[MediaSearchPlan]:
    beat_by_id = {b.beat_id: b for b in beats}
    plans = []
    for req in requirements:
        plans.append(build_search_plan(req, beat_by_id.get(req.beat_id)))
    return plans
