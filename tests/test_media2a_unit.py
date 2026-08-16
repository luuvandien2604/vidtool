"""Phase 2A unit tests: query planner, licensing, validation, cache."""
import json
from pathlib import Path

from videotool.domain.assets import AssetRequirement
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.editorial.media.cache import MediaCache, checksum_bytes
from videotool.editorial.media.licensing import (license_allowed,
                                                 license_quality)
from videotool.editorial.media.query_planner import (FORBIDDEN_GENERIC_QUERIES,
                                                     build_search_plan,
                                                     plan_search)
from videotool.editorial.media.validation import (sanitize_stem,
                                                  validate_media)
from videotool.providers.media.fixture import synthesize_png

FIX = Path(__file__).parent / "fixtures" / "wikimedia"


def make_beat(beat_id="beat_0001", fn=SemanticFunction.CHARACTER_INTRODUCTION,
              text="Gunter Schabowski was a tired official in East Berlin."):
    return SemanticBeat(beat_id=beat_id, start_sec=0.0, end_sec=6.0,
                        narration_text=text, word_start=0, word_end=8,
                        semantic_function=fn, visual_intent="t",
                        entities=["Gunter Schabowski"],
                        locations=["East Berlin"], dates=["1989"],
                        events=["press conference"])


def make_req(**kw):
    base = dict(requirement_id="R::opaque::1", beat_id="beat_0001",
                description="portrait of Gunter Schabowski in period context",
                kind="portrait", strength="REQUIRED",
                entities=["Gunter Schabowski"])
    base.update(kw)
    return AssetRequirement(**base)


# ---- query planner -----------------------------------------------------------

def test_queries_are_semantic_not_generic():
    plan = build_search_plan(make_req(), make_beat())
    assert plan.primary_query
    assert "schabowski" in plan.primary_query.lower()
    assert plan.primary_query.lower() not in FORBIDDEN_GENERIC_QUERIES
    assert all(q.lower() not in FORBIDDEN_GENERIC_QUERIES
               for q in plan.alternate_queries)


def test_planner_generates_surname_alternate():
    plan = build_search_plan(make_req(), make_beat())
    assert any(q.lower().startswith("schabowski")
               for q in plan.alternate_queries)


def test_planner_uses_dates_and_locations():
    plan = build_search_plan(make_req(), make_beat())
    assert "1989" in plan.date_terms
    assert "East Berlin" in plan.location_terms
    assert any("east berlin" in q.lower() for q in plan.alternate_queries)


def test_planner_never_emits_empty_primary():
    beat = make_beat(fn=SemanticFunction.TURNING_POINT,
                     text="That evening, crowds suddenly flooded the checkpoints.")
    beat.entities, beat.locations, beat.dates = [], [], []
    req = make_req(description="archival photograph of the subject matter",
                   kind="photo", entities=[])
    plan = build_search_plan(req, beat)
    assert plan.primary_query  # falls back to the beat's own narration words
    assert "crowds" in plan.primary_query.lower()


def test_planner_is_deterministic_and_opaque():
    a = build_search_plan(make_req(), make_beat())
    b = build_search_plan(make_req(), make_beat())
    assert a.to_dict() == b.to_dict()
    assert a.requirement_id == "R::opaque::1"  # ids pass through untouched


def test_plan_search_covers_every_requirement():
    reqs = [make_req(), make_req(requirement_id="R::2", kind="map",
                                 description="period map of Berlin",
                                 entities=["Berlin"])]
    plans = plan_search(reqs, [make_beat()])
    assert {p.requirement_id for p in plans} == {"R::opaque::1", "R::2"}


# ---- licensing ----------------------------------------------------------------

def test_allowed_licenses():
    for name in ("Public domain", "CC0 1.0", "CC BY 4.0", "CC BY-SA 3.0 de",
                 "PD-old", "Creative Commons Zero"):
        assert license_allowed(name), name


def test_denied_licenses():
    for name in ("", "All rights reserved", "CC BY-NC-SA 4.0", "CC BY-ND",
                 "Fair use", None or ""):
        assert not license_allowed(name), name


def test_license_quality_ordering():
    assert license_quality("Public domain") == 1.0
    assert license_quality("CC BY-SA 4.0") == 0.9
    assert license_quality("") == 0.0


# ---- download validation --------------------------------------------------------

def test_valid_png_passes_with_dimensions():
    data = synthesize_png("seed-a")
    result = validate_media(data)
    assert result.ok, result.reason
    assert result.media_format == "png"
    assert (result.width, result.height) == (1024, 768)
    assert result.extension == "png"


def test_html_masquerading_as_image_rejected():
    html = b"<!DOCTYPE html><html><body>404 not found</body></html>" + b"x" * 5000
    result = validate_media(html)
    assert not result.ok
    assert "masquerading" in result.reason


def test_too_small_blob_rejected():
    result = validate_media(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    assert not result.ok and "too small" in result.reason


def test_truncated_png_rejected():
    data = synthesize_png("seed-b")
    result = validate_media(data[:40])  # headers only, IDAT missing
    assert not result.ok


def test_unrecognized_binary_rejected():
    result = validate_medium = validate_media(b"\x00\x01\x02GarbageData" * 2000)
    assert not result.ok and "unrecognized" in result.reason


def test_size_ceiling_enforced():
    data = synthesize_png("seed-c")[:64] * 500_000
    result = validate_media(data, max_bytes=100_000)
    assert not result.ok and "too large" in result.reason


def test_gif_dimensions_parsed():
    import struct
    gif = b"GIF89a" + struct.pack("<HH", 320, 240) + b"\x00" * 6000
    result = validate_media(gif)
    assert result.ok and (result.width, result.height) == (320, 240)


def test_sanitize_stem_blocks_path_traversal():
    assert "/" not in sanitize_stem("../../etc/passwd")
    assert ".." not in sanitize_stem("..\\..\\win")
    assert sanitize_stem("") == "media"


# ---- content-addressed cache -----------------------------------------------------

def test_cache_dedupes_identical_bytes(tmp_path):
    cache = MediaCache(tmp_path)
    data = synthesize_png("same")
    sha1, newly1 = cache.put(data, "png", {"candidate_id": "c1"})
    sha2, newly2 = cache.put(data, "png", {"candidate_id": "c1"})
    assert sha1 == sha2
    assert newly1 and not newly2  # stored exactly once


def test_cache_different_bytes_differ(tmp_path):
    cache = MediaCache(tmp_path)
    sha1, _ = cache.put(synthesize_png("a"), "png", {})
    sha2, _ = cache.put(synthesize_png("b"), "png", {})
    assert sha1 != sha2


def test_cache_roundtrip_and_candidate_lookup(tmp_path):
    cache = MediaCache(tmp_path)
    data = synthesize_png("lookup")
    sha, _ = cache.put(data, "png", {"candidate_id": "cand-42"})
    assert cache.get(sha) == data
    assert cache.metadata(sha)["checksum"] == sha
    hit = cache.find_by_candidate("cand-42")
    assert hit is not None and hit[0] == sha and hit[1] == data
    assert cache.find_by_candidate("unknown") is None


def test_checksum_is_content_sha256():
    assert checksum_bytes(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
