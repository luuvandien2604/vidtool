"""Phase 2A ranking tests: semantic matching, generic penalty, reuse policy."""
from videotool.editorial.media.models import MediaCandidate, MediaSearchPlan
from videotool.editorial.media.ranking import (RankingPolicy, fold, tokens,
                                                rank_candidates, score_candidate)


def plan(kind="portrait", entities=None, locations=None, dates=None,
         query=None):
    return MediaSearchPlan(
        requirement_id="R::1", requirement_kind=kind,
        primary_query=query or " ".join(entities or []) or "photo",
        entity_terms=entities or [], location_terms=locations or [],
        date_terms=dates or [])


def cand(**kw):
    base = dict(candidate_id="c1", provider="fixture", title="",
                description="", media_type="PHOTO", width=1200, height=900,
                license_name="CC BY-SA 4.0")
    base.update(kw)
    return MediaCandidate(**base)


# ---- entity matching -----------------------------------------------------------

def test_full_name_entity_match_beats_surname():
    p = plan(entities=["Gunter Schabowski"])
    full = cand(title="Gunter Schabowski at press conference 1989")
    surname = cand(title="Schabowski reading notes")
    none = cand(title="Berlin crowd photo")
    assert score_candidate(p, full).components["entity_match"] == 1.0
    assert score_candidate(p, surname).components["entity_match"] == 0.6
    assert score_candidate(p, none).components["entity_match"] == 0.0


def test_unicode_folding_in_entity_match():
    p = plan(entities=["Gunter Schabowski"])
    umlaut = cand(title="Günter Schabowski, 9. November 1989")
    assert score_candidate(p, umlaut).components["entity_match"] == 1.0


def test_fold_and_tokens():
    assert fold("Günter Schabowski (1989)") == "gunter schabowski 1989"
    assert tokens("Berlin Wall, 1989!") == {"berlin", "wall", "1989"}


# ---- date matching ---------------------------------------------------------------

def test_date_matching_exact_decade_none():
    p = plan(entities=["x"], dates=["1989"])
    exact = cand(title="x", date_created="9 November 1989")
    decade = cand(title="x", date_created="1985")
    none = cand(title="x")
    assert score_candidate(p, exact).components["date_match"] == 1.0
    assert score_candidate(p, decade).components["date_match"] == 0.6
    assert score_candidate(p, none).components["date_match"] == 0.0


def test_no_date_requirement_is_neutral():
    p = plan(entities=["x"])
    assert score_candidate(p, cand(title="x")).components["date_match"] == 0.5


# ---- type matching + generic penalty -----------------------------------------------

def test_media_type_equivalence():
    p = plan(kind="portrait", entities=["x"])
    assert score_candidate(p, cand(title="x", media_type="PORTRAIT")) \
        .components["media_type_match"] == 1.0
    assert score_candidate(p, cand(title="x", media_type="PHOTO")) \
        .components["media_type_match"] == 1.0
    assert score_candidate(p, cand(title="x", media_type="DOCUMENT")) \
        .components["media_type_match"] == 0.3


def test_generic_image_penalty_hits_when_entity_missing():
    p = plan(kind="portrait", entities=["Gunter Schabowski"])
    specific = cand(title="Gunter Schabowski 1989 portrait",
                    media_type="PORTRAIT")
    generic = cand(title="Berlin skyline panorama, generic cityscape",
                   media_type="PHOTO", width=4000, height=1200)
    s_specific = score_candidate(p, specific)
    s_generic = score_candidate(p, generic)
    assert "generic_image" in s_generic.penalties
    assert s_specific.score > s_generic.score, (
        "specific media must beat high-resolution generic filler")


def test_high_resolution_does_not_rescue_generic():
    p = plan(kind="document", entities=["travel regulation"])
    generic_hd = cand(title="generic archive texture 8000px",
                      media_type="DOCUMENT", width=8000, height=6000,
                      description="old paper texture")
    s = score_candidate(p, generic_hd)
    assert "generic_image" in s.penalties
    assert s.score < 0.5


# ---- resolution + reuse ------------------------------------------------------------

def test_below_minimum_resolution_penalized_not_failed():
    p = plan(kind="map", entities=["berlin"])
    small = cand(title="berlin map", media_type="MAP", width=400)
    big = cand(title="berlin map", media_type="MAP", width=2000)
    s_small = score_candidate(p, small)
    s_big = score_candidate(p, big)
    assert "low_resolution" in s_small.penalties
    assert s_small.score < s_big.score
    assert s_small.score > 0  # stays a fallback candidate, not erased


def test_duplicate_usage_penalties():
    p = plan(kind="photo", entities=["berlin"])
    c = cand(title="berlin", media_type="PHOTO")
    first = score_candidate(p, c)
    immediate = score_candidate(p, c, immediate_reuse=True)
    repeat = score_candidate(p, c, usage_count=2)
    assert "duplicate_immediate" in immediate.penalties
    assert "duplicate_repeat" in repeat.penalties
    assert first.score > immediate.score
    assert first.score > repeat.score


def test_weights_are_configurable():
    p = plan(kind="photo", entities=["x"])
    c = cand(title="x", media_type="PHOTO")
    policy = RankingPolicy(weights={"entity_match": 1.0})
    s = score_candidate(p, c, policy=policy)
    assert s.score == s.components["entity_match"]


def test_ranking_sorted_and_explainable():
    p = plan(kind="portrait", entities=["Gunter Schabowski"])
    ranked = rank_candidates(p, [
        cand(candidate_id="c_generic", title="Berlin skyline panorama",
             media_type="PHOTO"),
        cand(candidate_id="c_best", title="Gunter Schabowski portrait 1989",
             media_type="PORTRAIT"),
    ])
    assert ranked[0].candidate_id == "c_best"
    assert ranked[0].reason  # explainability survives sorting
    assert "entity" in ranked[0].reason


def test_source_quality_prefers_institutions():
    institutional = cand(title="x", provider="wikimedia",
                         categories=["From Wikimedia Commons"])
    anon = cand(title="x", provider="unknown")
    p = plan(kind="photo", entities=["x"])
    assert score_candidate(p, institutional).components["source_quality"] == 1.0
    assert score_candidate(p, anon).components["source_quality"] == 0.6
