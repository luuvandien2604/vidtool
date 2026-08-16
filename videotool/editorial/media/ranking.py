"""Deterministic semantic candidate ranking (Phase 2A spec sections 10-12).

Semantic correctness beats visual attractiveness. Every scored candidate
carries its components and a human-readable reason so bad media can be
debugged later. Not naive substring matching: unicode-folded token sets,
surname aliasing, decade-aware date matching.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from videotool.editorial.media.models import (KIND_TO_MEDIA_TYPE, MediaCandidate,
                                              MediaSearchPlan, ScoredCandidate)

MEDIA_RANKING_VERSION = 1

DEFAULT_WEIGHTS = {
    "entity_match": 0.25,
    "event_match": 0.20,
    "date_match": 0.10,
    "location_match": 0.15,
    "media_type_match": 0.10,
    "source_quality": 0.08,
    "resolution": 0.07,
    "license_quality": 0.05,
}

DEFAULT_PENALTIES = {
    "generic_image": 0.35,      # historical-looking but semantically wrong
    "low_resolution": 0.20,
    "duplicate_immediate": 0.30,
    "duplicate_repeat": 0.15,   # per extra reuse of the same content
}

# markers of generic archival filler (matched against folded text)
_GENERIC_MARKERS = (
    "skyline", "cityscape", "panorama", "stock photo", "archive texture",
    "old paper texture", "wall texture", "grunge", "collage",
    "cold war soldiers", "soviet parade", "generic newspaper",
)

_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")

# kind equivalence for type matching (mirrors feasibility KIND_EQUIV)
_TYPE_EQUIV = {
    "PORTRAIT": {"PORTRAIT", "PHOTO"},
    "PHOTO": {"PHOTO", "PORTRAIT"},
}


def fold(text: str) -> str:
    """Unicode-fold for matching: Günter -> gunter."""
    norm = unicodedata.normalize("NFKD", text or "")
    ascii_ = norm.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", ascii_.lower())).strip()


def tokens(text: str) -> set[str]:
    return {t for t in fold(text).split() if len(t) > 2}


@dataclass
class RankingPolicy:
    weights: dict = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    penalties: dict = field(default_factory=lambda: dict(DEFAULT_PENALTIES))
    min_photo_width: int = 800
    min_document_width: int = 1000
    minimum_score: float = 0.40


def entity_match_score(plan: MediaSearchPlan, cand: MediaCandidate) -> float:
    """Person/alias matching: full name > surname > none, folded."""
    wanted = tokens(" ".join(plan.entity_terms))
    if not wanted:
        return 0.5  # requirement has no who/what: neutral
    have = (tokens(cand.title) | tokens(cand.description)
            | tokens(" ".join(cand.entities)))
    if not have:
        return 0.0
    if wanted <= have:
        return 1.0
    # surname-only hit: "kessler" matches "ruth kessler 1985"
    surnames = {fold(w.split()[-1]) for w in plan.entity_terms if w.split()}
    if surnames & have:
        return 0.6
    overlap = len(wanted & have)
    return round(min(0.4, overlap / max(1, len(wanted)) * 0.4), 3)


def date_match_score(plan: MediaSearchPlan, cand: MediaCandidate) -> float:
    wanted_years = {y for term in plan.date_terms for y in _YEAR_RE.findall(term)}
    if not wanted_years:
        return 0.5  # no date requirement: neutral
    cand_text = " ".join([cand.date_created, cand.date_published,
                          cand.title, cand.description])
    cand_years = set(_YEAR_RE.findall(cand_text))
    if wanted_years & cand_years:
        return 1.0
    # decade tolerance: 1989 requirement, 1980s imagery scores partial
    for w in wanted_years:
        decade = int(w) // 10 * 10
        if any(decade <= int(c) < decade + 10 for c in cand_years):
            return 0.6
    return 0.0


def location_match_score(plan: MediaSearchPlan, cand: MediaCandidate) -> float:
    wanted = tokens(" ".join(plan.location_terms))
    if not wanted:
        return 0.5
    have = (tokens(cand.title) | tokens(cand.description)
            | tokens(" ".join(cand.categories)))
    if not wanted:
        return 0.5
    if wanted <= have:
        return 1.0
    return round(len(wanted & have) / len(wanted), 3)


def event_match_score(plan: MediaSearchPlan, cand: MediaCandidate) -> float:
    wanted = tokens(" ".join(plan.event_terms))
    if not wanted:
        # fall back to plan's primary query terms minus kind words
        wanted = tokens(plan.primary_query) - {
            "portrait", "document", "map", "illustration", "photo"}
    if not wanted:
        return 0.5
    have = tokens(cand.title) | tokens(cand.description)
    if wanted <= have:
        return 1.0
    return round(len(wanted & have) / len(wanted), 3)


def media_type_match_score(plan: MediaSearchPlan, cand: MediaCandidate) -> float:
    wanted = KIND_TO_MEDIA_TYPE.get(plan.requirement_kind)
    if wanted is None:
        return 0.5
    got = cand.media_type
    options = _TYPE_EQUIV.get(wanted.value, {wanted.value})
    return 1.0 if got in options else (0.3 if got else 0.0)


def source_quality(cand: MediaCandidate) -> float:
    """Institutional providers rank above anonymous uploads."""
    trusted = ("wikimedia commons", "library of congress", "bundesarchiv",
               "national archives", "internet archive")
    source = fold(" ".join([cand.provider, " ".join(cand.categories)]))
    return 1.0 if any(t in source for t in trusted) else 0.6


def resolution_score(plan: MediaSearchPlan, cand: MediaCandidate,
                     policy: RankingPolicy) -> tuple[float, bool]:
    """(score, below_minimum)."""
    min_width = (policy.min_document_width
                 if plan.requirement_kind in ("map", "document")
                 else policy.min_photo_width)
    if not cand.width or not cand.height:
        return 0.5, False  # unknown dimensions: neutral, not penalized
    ratio = min(1.0, cand.width / max(1, min_width))
    return round(ratio, 3), cand.width < min_width


def generic_image_penalty(plan: MediaSearchPlan, cand: MediaCandidate,
                          entity_score: float, policy: RankingPolicy) -> float:
    """Historical-looking filler must lose when a specific person/event is
    required (spec section 11)."""
    if entity_score >= 0.5:
        return 0.0
    text = fold(cand.searchable_text())
    if any(marker in text for marker in _GENERIC_MARKERS):
        return policy.penalties["generic_image"]
    return 0.0


def score_candidate(plan: MediaSearchPlan, cand: MediaCandidate,
                    policy: RankingPolicy | None = None,
                    usage_count: int = 0,
                    immediate_reuse: bool = False) -> ScoredCandidate:
    policy = policy or RankingPolicy()
    components = {
        "entity_match": entity_match_score(plan, cand),
        "event_match": event_match_score(plan, cand),
        "date_match": date_match_score(plan, cand),
        "location_match": location_match_score(plan, cand),
        "media_type_match": media_type_match_score(plan, cand),
        "source_quality": source_quality(cand),
    }
    resolution, below_min = resolution_score(plan, cand, policy)
    components["resolution"] = resolution
    from videotool.editorial.media.licensing import license_quality
    components["license_quality"] = license_quality(cand.license_name)

    penalties: dict[str, float] = {}
    generic = generic_image_penalty(plan, cand,
                                    components["entity_match"], policy)
    if generic:
        penalties["generic_image"] = generic
    if below_min:
        penalties["low_resolution"] = policy.penalties["low_resolution"]
    if immediate_reuse:
        penalties["duplicate_immediate"] = policy.penalties["duplicate_immediate"]
    elif usage_count > 0:
        penalties["duplicate_repeat"] = round(
            policy.penalties["duplicate_repeat"] * usage_count, 3)

    total = sum(components[k] * w for k, w in policy.weights.items())
    total = round(max(0.0, total - sum(penalties.values())), 4)

    reason = _reason(plan, cand, components, penalties)
    return ScoredCandidate(candidate_id=cand.candidate_id, score=total,
                           components={k: round(v, 3)
                                       for k, v in components.items()},
                           penalties=penalties, reason=reason)


def _reason(plan: MediaSearchPlan, cand: MediaCandidate,
            components: dict, penalties: dict) -> str:
    bits = []
    e = components["entity_match"]
    if e >= 0.9:
        bits.append(f"exact entity match for {plan.entity_terms[:1]}")
    elif e >= 0.5:
        bits.append("partial (surname) entity match")
    else:
        bits.append("no entity match")
    if components["date_match"] >= 0.9:
        bits.append("correct date context")
    elif components["date_match"] >= 0.5:
        bits.append("decade-only date context")
    if components["media_type_match"] >= 0.9:
        bits.append(f"{cand.media_type.lower()} matches {plan.requirement_kind}")
    if penalties.get("generic_image"):
        bits.append("generic historical filler penalized")
    if penalties.get("low_resolution"):
        bits.append("below minimum resolution")
    return "; ".join(bits) or "candidate scored"


def rank_candidates(plan: MediaSearchPlan, candidates: list[MediaCandidate],
                    policy: RankingPolicy | None = None,
                    usage_counts: dict[str, int] | None = None,
                    last_selected: str | None = None) -> list[ScoredCandidate]:
    """Score + sort; rejected entries carry why (below threshold handled
    by the caller, license checked separately)."""
    policy = policy or RankingPolicy()
    usage_counts = usage_counts or {}
    scored = []
    for cand in candidates:
        scored.append(score_candidate(
            plan, cand, policy,
            usage_count=usage_counts.get(cand.candidate_id, 0),
            immediate_reuse=cand.candidate_id == last_selected))
    scored.sort(key=lambda s: (-s.score, s.candidate_id))
    return scored
