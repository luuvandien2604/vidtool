"""Semantic media acquisition tests (spec sections 15-16)."""
from videotool.domain.assets import AssetRequirement
from videotool.editorial.media import CatalogAcquirer

CATALOG = [
    {"asset_id": "archive:portrait:schabowski", "kind": "portrait",
     "description": "portrait of Gunter Schabowski, 1989 press conference",
     "entities": ["Gunter Schabowski"], "quality": 0.85},
    {"asset_id": "archive:document:travel_regulation", "kind": "document",
     "description": "East German travel regulation draft, 1989",
     "entities": ["Gunter Schabowski", "East Berlin"], "quality": 0.8},
    {"asset_id": "archive:photo:generic_europe", "kind": "photo",
     "description": "vintage european street scene, undated",
     "entities": [], "quality": 0.9},
]


def acquire(mode="final"):
    return CatalogAcquirer(CATALOG, mode=mode)


def test_requirement_matches_by_entity_tokens():
    reqs = [AssetRequirement(requirement_id="r1", beat_id="beat_0001",
                             kind="portrait",
                             description="portrait of Schabowski in period context",
                             entities=["Schabowski"])]
    assets = acquire().acquire(reqs)
    assert len(assets) == 1
    assert assets[0].asset_id == "archive:portrait:schabowski"
    assert assets[0].entity_match == 1.0
    assert not assets[0].is_placeholder


def test_asset_not_reused_across_requirements():
    reqs = [
        AssetRequirement(requirement_id="r1", beat_id="b1", kind="portrait",
                         description="portrait of Schabowski", entities=["Schabowski"]),
        AssetRequirement(requirement_id="r2", beat_id="b2", kind="portrait",
                         description="portrait of Schabowski", entities=["Schabowski"]),
    ]
    assets = acquire().acquire(reqs)
    resolved = [a for a in assets if not a.is_placeholder]
    ids = [a.asset_id for a in resolved]
    assert len(ids) == len(set(ids)), "same archive photo must not repeat"


def test_generic_imagery_is_penalized_not_matched():
    reqs = [AssetRequirement(requirement_id="r1", beat_id="b1", kind="photo",
                             description="archival photograph of the checkpoint",
                             entities=["Bornholmer Bridge"])]
    # final mode: no related photo -> nothing resolved (no filler B-roll)
    assets = acquire("final").acquire(reqs)
    assert assets == []
    # draft mode: placeholder marks the hole explicitly
    assets = acquire("draft").acquire(reqs)
    assert len(assets) == 1 and assets[0].is_placeholder


def test_kind_mismatch_never_matches():
    reqs = [AssetRequirement(requirement_id="r1", beat_id="b1", kind="map",
                             description="map of Berlin", entities=["Berlin"])]
    assets = acquire().acquire(reqs)
    assert assets == []


def test_relevance_scores_are_semantic():
    reqs = [AssetRequirement(requirement_id="r1", beat_id="b1", kind="portrait",
                             description="portrait of Schabowski",
                             entities=["Schabowski"])]
    asset = acquire().acquire(reqs)[0]
    assert asset.relevance_score() >= 0.6
