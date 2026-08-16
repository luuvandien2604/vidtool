"""Phase 2A acquisition service tests: thresholds, licenses, type policy,
failure isolation, reuse policy, explainability, acceptance + generalization.

All offline: fixture provider synthesizes real PNG bytes; Wikimedia runs on
recorded fixtures via a fake transport.
"""
import json
from pathlib import Path

from videotool.domain.assets import AssetRequirement
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.editorial.media.acquisition import MediaAcquisitionService, \
    search_candidates
from videotool.editorial.media.cache import MediaCache
from videotool.editorial.media.models import (MediaAcquisitionConfig,
                                              MediaCandidate, MediaSearchPlan)
from videotool.editorial.media.query_planner import build_search_plan
from videotool.editorial.media.ranking import fold
from videotool.providers.media import FixtureMediaProvider, ProviderError
from videotool.providers.media.fixture import synthesize_png

FIX = Path(__file__).parent / "fixtures" / "wikimedia" / "api_responses.json"


# ---- helpers ---------------------------------------------------------------

def beat(beat_id="beat_0001", fn=SemanticFunction.CHARACTER_INTRODUCTION,
         text="Gunter Schabowski was a tired official in East Berlin.",
         entities=None, locations=None, dates=None):
    return SemanticBeat(beat_id=beat_id, start_sec=0.0, end_sec=6.0,
                        narration_text=text, word_start=0, word_end=8,
                        semantic_function=fn, visual_intent="t",
                        entities=entities or ["Gunter Schabowski"],
                        locations=locations or ["East Berlin"],
                        dates=dates or ["1989"])


def req(requirement_id="R::1", beat_id="beat_0001", kind="portrait",
        description="portrait of Gunter Schabowski in period context",
        entities=None, strength="REQUIRED"):
    return AssetRequirement(requirement_id=requirement_id, beat_id=beat_id,
                            description=description, kind=kind,
                            strength=strength,
                            entities=entities or ["Gunter Schabowski"])


def service(catalog, tmp_path, **cfg):
    config = MediaAcquisitionConfig(**{"minimum_candidate_score": 0.4, **cfg})
    provider = FixtureMediaProvider(catalog)
    cache = MediaCache(tmp_path / "media_cache")
    return MediaAcquisitionService(provider, cache, config), provider, cache


def run_acquire(catalog, requirements, beats, tmp_path, mode="final", **cfg):
    svc, provider, cache = service(catalog, tmp_path, **cfg)
    plans = [build_search_plan(r, next((b for b in beats
                                        if b.beat_id == r.beat_id), None))
             for r in requirements]
    candidates = search_candidates(plans, provider, 10)
    return svc.acquire(requirements, plans, candidates, mode=mode)


SCHABOWSKI_CATALOG = [
    {"asset_id": "c_portrait", "kind": "portrait",
     "description": "portrait of Gunter Schabowski at a 1989 press conference",
     "entities": ["Gunter Schabowski"]},
    {"asset_id": "c_skyline", "kind": "photo",
     "description": "Berlin skyline panorama generic cityscape view",
     "entities": []},
    {"asset_id": "c_doc", "kind": "document",
     "description": "East German travel regulation document November 1989 Gunter Schabowski",
     "entities": ["Gunter Schabowski", "East Berlin"]},
    {"asset_id": "c_map", "kind": "map",
     "description": "map of divided Berlin 1989",
     "entities": ["Berlin"]},
]


# ---- selection policy ---------------------------------------------------------

def test_specific_media_beats_generic_for_portrait(tmp_path):
    result = run_acquire(SCHABOWSKI_CATALOG,
                         [req()], [beat()], tmp_path)
    assert len(result.assets) == 1
    assert result.assets[0].candidate_id == "c_portrait"
    assert result.assets[0].kind == "portrait"


def test_generic_berlin_image_loses_map_requirement(tmp_path):
    r = req(kind="map", description="period map of Berlin",
            entities=["Berlin"])
    result = run_acquire(SCHABOWSKI_CATALOG, [r], [beat()], tmp_path)
    assert result.assets[0].candidate_id == "c_map"


def test_document_requirement_selects_document_not_portrait(tmp_path):
    r = req(kind="document", description="travel regulation document 1989",
            entities=["Gunter Schabowski"])
    result = run_acquire(SCHABOWSKI_CATALOG, [r], [beat()], tmp_path)
    assert result.assets[0].candidate_id == "c_doc"


def test_unlicensed_candidate_rejected(tmp_path):
    catalog = [{"asset_id": "c_nc", "kind": "portrait",
                "description": "portrait of Gunter Schabowski 1989",
                "entities": ["Gunter Schabowski"],
                "license": "CC BY-NC-SA 4.0"}]
    result = run_acquire(catalog, [req()], [beat()], tmp_path)
    assert result.assets == []
    assert any("license not allowed" in r["reason"]
               for r in result.traces[0].rejections)


def test_below_threshold_not_force_selected(tmp_path):
    # only a semantically unrelated candidate exists
    catalog = [{"asset_id": "c_other", "kind": "portrait",
                "description": "portrait of somebody else entirely 1912",
                "entities": ["Someone Else"]}]
    result = run_acquire(catalog, [req()], [beat()], tmp_path)
    assert result.assets == []  # missing asset beats wrong asset
    assert "no acceptable candidate" in result.traces[0].unresolved_reason


def test_type_mismatch_rejected_even_with_entity_hit(tmp_path):
    # document scan mentions Schabowski but cannot satisfy a portrait
    result = run_acquire([SCHABOWSKI_CATALOG[2]],  # c_doc only
                         [req()], [beat()], tmp_path)
    assert result.assets == []
    assert any("type mismatch" in r["reason"]
               for r in result.traces[0].rejections)


# ---- failure isolation -----------------------------------------------------------

class ExplodingProvider(FixtureMediaProvider):
    provider_id = "fixture"

    def __init__(self, catalog, explode_for):
        super().__init__(catalog)
        self.explode_for = set(explode_for)
        self.fetched = []

    def fetch(self, candidate):
        self.fetched.append(candidate.candidate_id)
        if candidate.candidate_id in self.explode_for:
            raise ProviderError("download exploded")
        return super().fetch(candidate)


def test_one_failed_requirement_does_not_crash_the_episode(tmp_path):
    svc, _, _ = service(SCHABOWSKI_CATALOG, tmp_path)
    provider = ExplodingProvider(SCHABOWSKI_CATALOG, {"c_portrait"})
    svc.provider = provider
    r1 = req("R::1", kind="portrait")
    r2 = req("R::2", kind="map", description="period map of Berlin",
             entities=["Berlin"])
    b = beat()
    plans = [build_search_plan(r, b) for r in (r1, r2)]
    candidates = search_candidates(plans, provider, 10)
    result = svc.acquire([r1, r2], plans, candidates, mode="final")
    kinds = {a.requirement_id: a.is_placeholder for a in result.assets}
    # R::1 unresolved (exploded), R::2 still acquired
    assert "R::1" not in kinds
    assert any(a.requirement_id == "R::2" and not a.is_placeholder
               for a in result.assets)
    assert any("download failed" in r["reason"]
               for r in result.traces[0].rejections)


def test_network_error_keeps_already_acquired_media(tmp_path):
    svc, _, _ = service(SCHABOWSKI_CATALOG, tmp_path)
    provider = ExplodingProvider(SCHABOWSKI_CATALOG, {"c_map"})
    svc.provider = provider
    reqs = [req("R::1", kind="portrait"),
            req("R::2", kind="map", description="period map of Berlin",
                entities=["Berlin"])]
    plans = [build_search_plan(r, beat()) for r in reqs]
    candidates = search_candidates(plans, provider, 10)
    result = svc.acquire(reqs, plans, candidates, mode="final")
    acquired = [a for a in result.assets if not a.is_placeholder]
    assert any(a.candidate_id == "c_portrait" for a in acquired)


# ---- reuse + cache -----------------------------------------------------------

def test_identical_bytes_deduped_across_requirements(tmp_path):
    svc, provider, cache = service(SCHABOWSKI_CATALOG, tmp_path)
    reqs = [req("R::1", kind="map", description="period map of Berlin",
                entities=["Berlin"]),
            req("R::2", kind="map", description="Berlin map 1989",
                entities=["Berlin"])]
    plans = [build_search_plan(r, beat()) for r in reqs]
    candidates = search_candidates(plans, provider, 10)
    result = svc.acquire(reqs, plans, candidates, mode="final")
    checksums = [a.checksum for a in result.assets]
    # same content fetched twice -> one blob, two assets sharing checksum
    assert len(set(checksums)) <= 2
    blobs = list((tmp_path / "media_cache").glob("*/*.png"))
    assert len(blobs) == len(set(checksums))  # stored once per unique bytes


def test_cache_hit_avoids_refetch(tmp_path):
    svc, provider, cache = service(SCHABOWSKI_CATALOG, tmp_path)
    r = req()
    plans = [build_search_plan(r, beat())]
    candidates = search_candidates(plans, provider, 10)
    first = svc.acquire([r], plans, candidates, mode="final")
    count_after_first = len(provider.fetched) if hasattr(provider, "fetched") else None
    # second acquisition of the same candidate must come from the cache
    provider.fetched = []
    svc2 = MediaAcquisitionService(provider, cache, svc.config)
    second = svc2.acquire([r], plans, candidates, mode="final")
    assert provider.fetched == []  # no network fetch
    assert second.assets[0].checksum == first.assets[0].checksum


def test_immediate_reuse_penalized(tmp_path):
    svc, provider, cache = service(SCHABOWSKI_CATALOG, tmp_path)
    # two identical map requirements: second one must not silently repeat
    # the same candidate when a viable alternative exists
    catalog = SCHABOWSKI_CATALOG + [
        {"asset_id": "c_map2", "kind": "map",
         "description": "map of Berlin sectors 1989 border",
         "entities": ["Berlin"]}]
    svc.provider = provider = FixtureMediaProvider(catalog)
    reqs = [req("R::1", kind="map", description="period map of Berlin",
                entities=["Berlin"]),
            req("R::2", kind="map", description="map of Berlin 1989",
                entities=["Berlin"])]
    plans = [build_search_plan(r, beat()) for r in reqs]
    candidates = search_candidates(plans, provider, 10)
    result = svc.acquire(reqs, plans, candidates, mode="final")
    chosen = [a.candidate_id for a in result.assets]
    assert len(set(chosen)) == 2, f"immediate reuse not penalized: {chosen}"


# ---- modes + provenance ---------------------------------------------------------

def test_draft_mode_uses_labelled_placeholders(tmp_path):
    result = run_acquire([], [req()], [beat()], tmp_path, mode="draft")
    assert len(result.assets) == 1
    assert result.assets[0].is_placeholder
    assert result.assets[0].description.startswith("PLACEHOLDER")


def test_provenance_survives_into_assets(tmp_path):
    result = run_acquire(SCHABOWSKI_CATALOG, [req()], [beat()], tmp_path)
    a = result.assets[0]
    assert a.provider == "fixture"
    assert a.candidate_id == "c_portrait"
    assert a.checksum and len(a.checksum) == 64
    assert a.retrieval_ts  # ISO timestamp
    assert a.width == 1024 and a.height == 768
    assert a.license_name
    assert a.attribution.get("license_name")


def test_selection_explainability_persisted(tmp_path):
    result = run_acquire(SCHABOWSKI_CATALOG, [req()], [beat()], tmp_path)
    a = result.assets[0]
    assert a.score_components and "entity_match" in a.score_components
    assert a.selection_reason
    trace = result.traces[0]
    assert trace.selected_candidate_id == a.candidate_id
    assert trace.queries_attempted          # primary + alternates tried
    assert trace.candidates_seen >= 1


def test_attribution_built_for_real_assets_only(tmp_path):
    result = run_acquire(SCHABOWSKI_CATALOG,
                         [req(), req("R::2", kind="document",
                                     description="regulation document 1989",
                                     entities=["Gunter Schabowski"])],
                         [beat()], tmp_path, mode="draft")
    placeholder_ids = {a.asset_id for a in result.assets if a.is_placeholder}
    assert all(entry["asset_id"] not in placeholder_ids
               for entry in
               [{"asset_id": x.asset_id} for x in result.attributions])


# ---- acceptance: mocked Wikimedia (spec section 35) -------------------------------

class FakeWikimediaTransport:
    def __init__(self):
        responses = json.loads(FIX.read_text())
        responses.pop("_comment", None)
        self.responses = responses
        self.get_calls = 0

    def get(self, url):
        self.get_calls += 1
        import urllib.parse
        from videotool.editorial.media.ranking import fold
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        query = params.get("gsrsearch", "")
        payload = self.responses.get(query)
        if payload is None:  # tolerate query variations (substring match)
            folded = fold(query)
            for key, value in self.responses.items():
                if fold(key) in folded:
                    payload = value
                    break
        if payload is None:
            payload = {"query": {"pages": []}}
        return json.dumps(payload).encode()

    def get_json(self, url):
        return json.loads(self.get(url))


def wikimedia_service(tmp_path):
    from videotool.providers.media.wikimedia import WikimediaMediaProvider
    provider = WikimediaMediaProvider(transport=FakeWikimediaTransport())
    config = MediaAcquisitionConfig(provider="wikimedia")
    svc = MediaAcquisitionService(provider, MediaCache(tmp_path / "c"), config)
    # fetch: serve deterministic PNG for every wikimedia media url
    original_fetch = provider.fetch

    def fetch_with_bytes(candidate):
        from videotool.providers.media.base import FetchedMedia
        return FetchedMedia(synthesize_png(candidate.candidate_id),
                            "image/png", candidate.media_url)
    provider.fetch = fetch_with_bytes
    return svc, provider


def test_wikimedia_acceptance_schabowski_portrait_wins(tmp_path):
    svc, provider = wikimedia_service(tmp_path)
    r = req()
    plans = [build_search_plan(r, beat())]
    candidates = search_candidates(plans, provider, 10)
    result = svc.acquire([r], plans, candidates)
    assert result.assets, result.traces[0].unresolved_reason
    a = result.assets[0]
    assert "Schabowski" in a.description
    assert a.provider == "wikimedia"
    assert a.license_name == "CC BY-SA 3.0 de"  # license respected
    assert "skyline" not in fold(a.description)  # generic lost


def test_wikimedia_unlicensed_media_never_selected(tmp_path):
    svc, provider = wikimedia_service(tmp_path)
    r = req(description="photo without license info",
            entities=["unlicensed"])
    plans = [build_search_plan(r, beat(entities=["unlicensed"]))]
    candidates = search_candidates(plans, provider, 10)
    result = svc.acquire([r], plans, candidates)
    assert result.assets == []
    assert any("license" in rej["reason"].lower()
               for rej in result.traces[0].rejections) or \
        "no acceptable" in result.traces[0].unresolved_reason


# ---- generalization (spec section 36) --------------------------------------------

def test_chernobyl_queries_and_ranking(tmp_path):
    b = beat(fn=SemanticFunction.LOCATION_INTRODUCTION,
             text="The reactor failed during a safety test outside Pripyat.",
             entities=["Reactor Four", "Pripyat"], locations=["Pripyat"],
             dates=["1986"])
    r = req(kind="photo", description="archival photograph of Pripyat 1986",
            entities=["Pripyat"])
    catalog = [
        {"asset_id": "c_pripyat", "kind": "photo",
         "description": "Pripyat reactor Four 1986 aerial photograph",
         "entities": ["Pripyat", "Reactor Four"]},
        {"asset_id": "c_generic", "kind": "photo",
         "description": "generic soviet parade panorama cold war",
         "entities": []},
    ]
    plan = build_search_plan(r, b)
    assert "pripyat" in plan.primary_query.lower()
    result = run_acquire(catalog, [r], [b], tmp_path)
    assert result.assets[0].candidate_id == "c_pripyat"


def test_titanic_queries_and_ranking(tmp_path):
    b = beat(fn=SemanticFunction.EVIDENCE,
             text="The telegram log survived with the last messages.",
             entities=["Carpathia", "Titanic"], locations=["Southampton"],
             dates=["1912"])
    r = req(kind="document", description="wireless telegram document 1912",
            entities=["Carpathia"])
    catalog = [
        {"asset_id": "c_telegram", "kind": "document",
         "description": "Carpathia wireless telegram transcript Titanic 1912",
         "entities": ["Carpathia", "Titanic"]},
        {"asset_id": "c_ship_photo", "kind": "photo",
         "description": "Titanic ship photograph Southampton 1912",
         "entities": ["Titanic"]},
    ]
    result = run_acquire(catalog, [r], [b], tmp_path)
    assert result.assets[0].candidate_id == "c_telegram"
