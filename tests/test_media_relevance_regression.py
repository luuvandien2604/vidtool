"""Regression tests for media relevance scoring fixes.

Guarantees that:
1. Gunter Schabowski portrait outscores Berlin Tierpark cattle photo.
2. 1989-era Hungary/Austria border map outscores 1910 Arabic-script ethnic map.
3. Location phrase adjacency prevents 'east of Berlin' from scoring 1.0 for 'East Berlin'.
4. Event match returns neutral 0.5 when no event_terms exist (no circular query matching).
5. Non-Latin script detection applies soft penalty without hard exclusion.
"""
from __future__ import annotations

from videotool.editorial.media.models import MediaCandidate, MediaSearchPlan
from videotool.editorial.media.ranking import (
    entity_match_score,
    event_match_score,
    has_non_latin_script,
    location_match_score,
    rank_candidates,
    score_candidate,
)


def test_schabowski_portrait_outscores_cattle_photo():
    """Case 1 Regression: Portrait requirement must choose human portrait over zoo cattle."""
    plan = MediaSearchPlan(
        requirement_id="req_beat_0003_portrait",
        requirement_kind="portrait",
        primary_query="Gunter Schabowski portrait",
        alternate_queries=[
            "Gunter Schabowski East Berlin portrait",
            "Schabowski portrait",
            "East Berlin portrait",
        ],
        entity_terms=["Gunter Schabowski", "East Berlin"],
        location_terms=["East Berlin"],
        date_terms=[],
        event_terms=[],
        negative_terms=["stock", "generic", "texture"],
    )

    # Actual candidate data from Wikimedia Commons
    cattle_photo = MediaCandidate(
        candidate_id="wikimedia:176277425",
        provider="wikimedia",
        title="Berlin Tierpark lub 2025-09-13 img17 Fjäll-Rind.jpg",
        description="Fjäll in the zoo in the east of Berlin, Germany",
        media_type="PHOTO",
        width=7952,
        height=5304,
        license_name="CC BY 4.0",
        categories=["Berlin Tierpark lub 2025-09-13 img17 Fjäll-Rind"],
    )

    schabowski_portrait = MediaCandidate(
        candidate_id="wikimedia:1726759",
        provider="wikimedia",
        title="Schabowski-portrait.jpg",
        description="",
        media_type="PHOTO",
        width=1600,
        height=1200,
        license_name="CC BY-SA 3.0",
        categories=["Schabowski-portrait"],
    )

    s_cattle = score_candidate(plan, cattle_photo)
    s_schabowski = score_candidate(plan, schabowski_portrait)

    # 1. Schabowski must win over cattle
    assert s_schabowski.score > s_cattle.score, (
        f"Real portrait ({s_schabowski.score}) must outscore cattle ({s_cattle.score})"
    )

    # 2. Cattle must NOT receive surname entity credit for 'Berlin'
    assert s_cattle.components["entity_match"] <= 0.25, (
        f"Cattle entity match should be low, got {s_cattle.components['entity_match']}"
    )

    # 3. Cattle must receive unmatched_portrait_entity penalty
    assert "unmatched_portrait_entity" in s_cattle.penalties

    # 4. Schabowski gets valid surname match (0.6) and no mismatch penalty
    assert s_schabowski.components["entity_match"] == 0.6
    assert "unmatched_portrait_entity" not in s_schabowski.penalties

    # 5. In rank_candidates, Schabowski ranks first
    ranked = rank_candidates(plan, [cattle_photo, schabowski_portrait])
    assert ranked[0].candidate_id == "wikimedia:1726759"


def test_hungary_austria_1989_map_outscores_1910_arabic_map():
    """Case 2 Regression: 1989 Cold War border map must outscore 1910 Arabic ethnic map."""
    plan = MediaSearchPlan(
        requirement_id="req_beat_0004_map",
        requirement_kind="map",
        primary_query="Hungary Austria map 1989",
        alternate_queries=[
            "Hungary Austria border map",
            "Hungary Austria",
        ],
        entity_terms=["Hungary", "Austria", "East Germans", "West"],
        location_terms=["Hungary", "Austria", "West"],
        date_terms=["1989"],
        event_terms=["border opening"],
        negative_terms=["stock", "generic", "texture"],
    )

    # Actual candidate from Wikimedia Commons (1910 Austro-Hungarian ethnic map in Arabic)
    arabic_1910_map = MediaCandidate(
        candidate_id="wikimedia:64766890",
        provider="wikimedia",
        title="Austria Hungary ethnic-ar.svg",
        description="The ethnic groups of Austria-Hungary in 1910. Based on Distribution of Races...",
        media_type="MAP",
        width=1360,
        height=1052,
        license_name="Public domain",
        categories=["Austria Hungary ethnic-ar"],
    )

    # Plausible 1989 border opening map candidate
    border_1989_map = MediaCandidate(
        candidate_id="wikimedia:border_1989",
        provider="wikimedia",
        title="Hungary Austria border opening September 1989 map.svg",
        description="Map showing the border opening between Hungary and Austria in September 1989.",
        media_type="MAP",
        width=1920,
        height=1080,
        license_name="CC BY-SA 4.0",
        categories=["1989 events in Hungary", "Austria-Hungary border"],
        date_created="1989",
    )

    s_arabic = score_candidate(plan, arabic_1989_candidate := arabic_1910_map)
    s_1989 = score_candidate(plan, border_1989_map)

    # 1. 1989 border map must outscore the 1910 Arabic map
    assert s_1989.score > s_arabic.score, (
        f"1989 map ({s_1989.score}) must outscore 1910 Arabic map ({s_arabic.score})"
    )

    # 2. Arabic map must be penalized for non-Latin script
    assert "non_latin_script" in s_arabic.penalties

    # 3. 1989 map gets high date match (1.0 vs 0.0)
    assert s_1989.components["date_match"] == 1.0
    assert s_arabic.components["date_match"] == 0.0


def test_location_phrase_adjacency():
    """Verify that location matching requires adjacent phrase for full credit."""
    plan = MediaSearchPlan(
        requirement_id="req_test_loc",
        requirement_kind="photo",
        primary_query="East Berlin photo",
        location_terms=["East Berlin"],
    )

    # Candidate A: Exact phrase in text
    cand_adjacent = MediaCandidate(
        candidate_id="c_adj",
        provider="wikimedia",
        title="Checkpoint in East Berlin 1989.jpg",
        description="A military checkpoint located in East Berlin",
    )

    # Candidate B: Tokens present but separated ('east of Berlin')
    cand_separated = MediaCandidate(
        candidate_id="c_sep",
        provider="wikimedia",
        title="Tierpark in the east of Berlin.jpg",
        description="Located in the east of Berlin",
    )

    score_adj = location_match_score(plan, cand_adjacent)
    score_sep = location_match_score(plan, cand_separated)

    assert score_adj == 1.0
    assert score_sep <= 0.4, f"Separated tokens should not exceed 0.4, got {score_sep}"


def test_event_match_neutrality():
    """Verify event_match returns neutral 0.5 when event_terms is empty."""
    plan_no_events = MediaSearchPlan(
        requirement_id="req_test_no_ev",
        requirement_kind="map",
        primary_query="Hungary map",
        event_terms=[],
    )

    cand = MediaCandidate(
        candidate_id="c1",
        provider="wikimedia",
        title="Hungary map 1941.png",
        description="Map of Hungary in 1941",
    )

    # Must be neutral 0.5, NOT self-satisfying 1.0 from primary query words
    assert event_match_score(plan_no_events, cand) == 0.5


def test_non_latin_script_soft_penalty():
    """Verify non-Latin script detection and soft penalty application."""
    cand_arabic = MediaCandidate(
        candidate_id="c_ar",
        provider="wikimedia",
        title="Austria Hungary ethnic-ar.svg",
        description="خريطة المجر والنمسا",
    )

    cand_latin = MediaCandidate(
        candidate_id="c_lat",
        provider="wikimedia",
        title="Austria Hungary ethnic map.svg",
        description="Ethnic groups of Austria-Hungary",
    )

    assert has_non_latin_script(cand_arabic) is True
    assert has_non_latin_script(cand_latin) is False
