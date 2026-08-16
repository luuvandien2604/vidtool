"""Phase 1.2.1 patch tests (final review round).

1. Stage-version upgrade: artifacts written by OLDER stage versions must be
   invalidated when the code's semantics changed, even with identical inputs.
2. Requirement ids are opaque END TO END: weird id -> asset resolves ->
   feasibility sees it -> composition receives it -> layer.asset_id bound.
3. _hero_layer fallback never returns a TEXTURE layer.
"""
import pytest

import videotool.pipeline.runner as runner_module
from videotool.artifacts import ArtifactStore
from videotool.domain.assets import AssetRequirement, MediaAsset
from videotool.domain.composition import (CompositionLayer, LayerType,
                                          MotionStyle, VisualComposition)
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.editorial.composition import assets_for_beat
from videotool.domain.visual_history import derive_signature
from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.fingerprints import STAGE_VERSIONS
from videotool.pipeline.runner import EpisodeInput, PipelineRunner

# stage versions as they were BEFORE this patch (Phase 1.2.1 initial)
OLD_VERSIONS = {
    "visual_strategy_plan": 1,
    "strategy_feasibility": 1,
    "visual_compositions": 2,
    "visual_history": 2,
    "timeline": 1,
}
NEW_VERSIONS = {k: STAGE_VERSIONS[k] for k in OLD_VERSIONS}


def test_versions_were_actually_bumped():
    for stage, old in OLD_VERSIONS.items():
        assert STAGE_VERSIONS[stage] > old, (
            f"{stage} semantics changed; version must be bumped "
            f"({old} -> {STAGE_VERSIONS[stage]})")


def test_upgrade_from_old_stage_versions_invalidates_changed_stages(
        tmp_path, monkeypatch):
    """Simulate: artifacts produced by older code, then `git pull` new code
    (bumped versions), same episode inputs. Changed stages must recompute;
    untouched stages must resume."""
    data = load_episode()
    store = ArtifactStore(tmp_path / "artifacts")

    # --- phase A: create artifacts with the OLD stage versions ---
    for stage, old in OLD_VERSIONS.items():
        monkeypatch.setitem(STAGE_VERSIONS, stage, old)
    monkeypatch.setattr(runner_module, "FAMILIES_VERSION", 1)
    old_run = PipelineRunner(store, mode="final").run(EpisodeInput(**data))
    assert old_run.ok
    monkeypatch.undo()  # restore the new (current) code constants

    assert NEW_VERSIONS == {k: STAGE_VERSIONS[k] for k in OLD_VERSIONS}

    # --- phase B: same episode, upgraded code ---
    res = PipelineRunner(store, mode="final").run(EpisodeInput(**data))
    st = {s: v["status"] for s, v in res.manifest["stages"].items()}

    assert st["semantic_beats"] == "resumed"          # semantics unchanged
    assert st["episode_art_direction"] == "resumed"
    assert st["asset_requirements"] == "resumed"
    assert st["media_assets"] == "resumed"
    assert st["visual_strategy_plan"] == "invalidated"   # bumped versions
    assert st["strategy_feasibility"] == "invalidated"
    assert st["visual_compositions"] == "invalidated"
    assert st["visual_history"] == "invalidated"
    assert st["timeline"] == "invalidated"
    assert res.ok


def test_upgraded_run_rewrites_stage_meta_versions(tmp_path, monkeypatch):
    data = load_episode()
    store = ArtifactStore(tmp_path / "artifacts")
    for stage, old in OLD_VERSIONS.items():
        monkeypatch.setitem(STAGE_VERSIONS, stage, old)
    PipelineRunner(store, mode="final").run(EpisodeInput(**data))
    monkeypatch.undo()

    PipelineRunner(store, mode="final").run(EpisodeInput(**data))
    meta = store.load("berlin_wall_phase1", "stage_meta")
    for stage in OLD_VERSIONS:
        assert meta[stage]["stage_version"] == STAGE_VERSIONS[stage]


# ---- opaque requirement ids, end to end ------------------------------------

def _weird_reqs(beats):
    from videotool.editorial.composition import semantic_asset_requirements
    reqs = semantic_asset_requirements(beats)
    for r in reqs:
        r.requirement_id = f"R::{r.beat_id}::{r.kind} (opaque/2026)"
    return reqs


def test_opaque_requirement_ids_flow_to_composition_layers(tmp_path, monkeypatch):
    """weird requirement id -> acquisition -> feasibility -> composition
    binding: layer.asset_id must equal the resolved asset."""
    data = load_episode()
    store = ArtifactStore(tmp_path / "artifacts")
    runner = PipelineRunner(store, mode="final")
    monkeypatch.setattr(runner_module, "semantic_asset_requirements",
                        _weird_reqs)
    res = runner.run(EpisodeInput(**data))

    assert res.ok, res.validation
    assert res.assets and all("::" in a.requirement_id for a in res.assets)

    req_by_id = {r.requirement_id: r for r in res.requirements}
    asset_by_req = {a.requirement_id: a for a in res.assets
                    if not a.is_placeholder}

    # find the portrait requirement of the CHARACTER beat
    portrait_req = next(r for r in res.requirements
                        if r.kind == "portrait" and r.beat_id == "beat_0003")
    portrait_asset = asset_by_req.get(portrait_req.requirement_id)
    assert portrait_asset is not None, "weird ids must not break acquisition"

    # the composition for that beat must actually carry the asset on a layer
    comp3 = next(c for c in res.compositions if c.beat_id == "beat_0003")
    bound = {l.asset_id for l in comp3.layers if l.asset_id}
    assert portrait_asset.asset_id in bound, (
        f"composition must receive assets through opaque ids; "
        f"bound={bound}, expected {portrait_asset.asset_id}")

    # sanity: every bound asset id is one we acquired
    acquired = {a.asset_id for a in res.assets}
    for comp in res.compositions:
        for layer in comp.layers:
            if layer.asset_id:
                assert layer.asset_id in acquired


def test_assets_for_beat_groups_via_requirements_not_prefixes():
    reqs = [AssetRequirement(requirement_id="R::b1::map (opaque)", beat_id="beat_0001",
                             description="map", kind="map"),
            AssetRequirement(requirement_id="req_beat_0002_map", beat_id="beat_0002",
                             description="map", kind="map")]
    assets = [MediaAsset(asset_id="a1", requirement_id="R::b1::map (opaque)",
                         description="m", kind="map"),
              MediaAsset(asset_id="a2", requirement_id="req_beat_0002_map",
                         description="m", kind="map")]
    beat1 = assets_for_beat(assets, reqs, "beat_0001")
    assert [a.asset_id for a in beat1] == ["a1"]
    beat2 = assets_for_beat(assets, reqs, "beat_0002")
    assert [a.asset_id for a in beat2] == ["a2"]


# ---- hero fallback never picks texture --------------------------------------

def _tex_comp(first_texture: bool) -> VisualComposition:
    comp = VisualComposition(composition_id="c", beat_id="b",
                             visual_family="full_frame_cinematic",
                             strategy="s", duration_sec=4.0)
    tex = CompositionLayer(id="tex", type=LayerType.TEXTURE, x=0, y=0,
                           width=1, height=1, z_index=1, role="texture",
                           entrance=MotionStyle.DISSOLVE,
                           exit=MotionStyle.DISSOLVE)
    content = CompositionLayer(id="cap", type=LayerType.TEXT, x=0.1, y=0.2,
                               width=0.5, height=0.1, z_index=10,
                               entrance=MotionStyle.TYPE_ON,
                               exit=MotionStyle.DISSOLVE)
    comp.layers = [tex, content] if first_texture else [content, tex]
    return comp


def test_hero_layer_never_falls_back_to_texture():
    sig = derive_signature(_tex_comp(first_texture=True))
    assert "hero=TEXTURE" not in sig
    assert "hero=TEXT" in sig  # first non-texture layer became hero


def test_texture_only_composition_has_no_hero():
    comp = VisualComposition(composition_id="c", beat_id="b",
                             visual_family="f", strategy="s", duration_sec=4.0)
    comp.layers.append(CompositionLayer(
        id="tex", type=LayerType.TEXTURE, x=0, y=0, width=1, height=1,
        z_index=1, role="texture", entrance=MotionStyle.DISSOLVE,
        exit=MotionStyle.DISSOLVE))
    sig = derive_signature(comp)
    assert "hero=none" in sig


# ---- signature lifecycle: stored == derived from FINAL state ---------------

def _sig_ctx(family_id, fn):
    from videotool.domain.art_direction import EpisodeArtDirection
    from videotool.editorial.composition.base import CompositionContext
    from videotool.editorial.strategies import STRATEGY_CATALOG

    beat = SemanticBeat(beat_id="beat_0001", start_sec=0.0, end_sec=6.0,
                        narration_text="A document was found in the archive.",
                        word_start=0, word_end=6, semantic_function=fn,
                        visual_intent="t", entities=["Berlin Wall"],
                        locations=["Berlin"], dates=["1989"],
                        objects=["document"], relationships=["cause"])
    art = EpisodeArtDirection(
        episode_id="ep", subject="T", visual_motifs=["paper"],
        archival_language=["newsprint"], geometry=["frames"],
        typography_character=["editorial"],
        accent={"primary": "r", "warning": "r", "neutral": "k"},
        motion_character=["tactile"], forbidden_patterns=[])
    strategy = next(s for s in STRATEGY_CATALOG.values()
                    if s.visual_family == family_id)
    assets = [MediaAsset(asset_id=f"archive:{k}:{i}",
                         requirement_id=f"req_{k}",
                         description=f"{k}", kind=k, entity_match=1.0)
              for i, k in enumerate(("photo", "document", "map", "portrait"))]
    return CompositionContext(beat=beat, strategy=strategy, art_direction=art,
                              assets=assets, episode_id="ep")


_SIG_FAMILY_CASES = [
    ("archival_subject", SemanticFunction.CHARACTER_INTRODUCTION),
    ("document_evidence", SemanticFunction.EVIDENCE),
    ("geographic_map", SemanticFunction.LOCATION_INTRODUCTION),
    ("chronological_timeline", SemanticFunction.CHRONOLOGY),
    ("causal_network", SemanticFunction.CAUSAL_EXPLANATION),
    ("full_frame_cinematic", SemanticFunction.ATMOSPHERE),
]


@pytest.mark.parametrize("family_id,fn", _SIG_FAMILY_CASES,
                         ids=[f[0] for f in _SIG_FAMILY_CASES])
def test_stored_signature_describes_final_composition(family_id, fn):
    """The stored novelty_signature must equal derive_signature() of the
    FINISHED composition (signature is now derived after reading_order
    staggering - Phase 1.2.1 final patch)."""
    from videotool.editorial.composition import FAMILIES

    ctx = _sig_ctx(family_id, fn)
    comp = FAMILIES[family_id].compose(ctx)
    assert comp.reading_order, "staggering must generate a reading_order"
    assert comp.novelty_signature == derive_signature(comp), (
        f"{family_id}: stored signature was derived before the composition "
        f"reached its final structural state")


@pytest.mark.parametrize("family_id,fn", _SIG_FAMILY_CASES,
                         ids=[f[0] for f in _SIG_FAMILY_CASES])
def test_mirrored_variant_signature_describes_final_composition(family_id, fn):
    """Odd variants are mirrored after compose(); their signature must be
    re-derived from the mirrored final state too."""
    from videotool.editorial.composition import FAMILIES
    from videotool.editorial.composition.base import (
        compose_with_distinct_signature)

    # force the search past variant 0 by pre-seeding its signature
    ctx = _sig_ctx(family_id, fn)
    first = FAMILIES[family_id].compose(_sig_ctx(family_id, fn))
    comp = compose_with_distinct_signature(
        FAMILIES[family_id], _sig_ctx(family_id, fn), {first.novelty_signature})
    assert comp.novelty_signature not in (first.novelty_signature,)
    assert comp.novelty_signature == derive_signature(comp)
    assert comp.reading_order


def test_fallback_composition_signature_matches_final_state():
    from videotool.editorial.validation import deterministic_fallback_composition
    beat = SemanticBeat(beat_id="beat_0001", start_sec=0.0, end_sec=5.0,
                        narration_text="t", word_start=0, word_end=1,
                        semantic_function=SemanticFunction.EVIDENCE,
                        visual_intent="t")
    comp = deterministic_fallback_composition(beat, 0, [])
    assert comp.reading_order
    assert comp.novelty_signature == derive_signature(comp)
