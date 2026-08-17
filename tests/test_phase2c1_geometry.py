"""Phase 2C.1 semantic geometry domain, integrity and acceptance tests."""
from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from videotool.artifacts import ArtifactStore
from videotool.domain.geometry import (CanvasRegion, ConstraintStrength,
                                       ConstraintType, EdgeType, GeometryHistory,
                                       GeometryPlan, VisualRole)
from videotool.domain.narration import Narration
from videotool.editorial.geometry import (GEOMETRY_POLICY_VERSION,
                                           GEOMETRY_SIGNATURE_VERSION,
                                           SEMANTIC_GEOMETRY_VERSION,
                                           SemanticGeometryBuilder,
                                           debug_geometry_plan,
                                           geometry_input_projection,
                                           validate_geometry_plan)
from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.fingerprints import STAGE_VERSIONS, stable_hash
from videotool.pipeline.runner import EpisodeInput, PipelineRunner
from videotool.providers.media.base import FetchedMedia
from videotool.providers.media.fixture import (FixtureMediaProvider,
                                                synthesize_png)


def run_berlin(root, data=None, runner_cls=PipelineRunner):
    data = data or load_episode()
    return runner_cls(ArtifactStore(root), mode="final").run(
        EpisodeInput(**data))


def test_geometry_domain_round_trip_and_debug_representation(berlin_run):
    plan = berlin_run["result"].geometry_plans[6]
    restored = GeometryPlan.from_dict(plan.to_dict())
    assert restored.to_dict() == plan.to_dict()
    assert restored.nodes and restored.groups
    assert all(node.preferred_regions for node in restored.nodes)
    text = debug_geometry_plan(restored)
    assert "Nodes:" in text and "Constraints:" in text
    assert "Reading:" in text and restored.semantic_geometry_signature in text


def test_geometry_versions_are_explicit_and_stage_is_registered():
    assert SEMANTIC_GEOMETRY_VERSION >= 1
    assert GEOMETRY_POLICY_VERSION >= 1
    assert GEOMETRY_SIGNATURE_VERSION >= 1
    assert STAGE_VERSIONS["semantic_geometry"] >= 1


def test_node_bounds_safe_zones_and_constraint_strengths(berlin_run):
    plans = berlin_run["result"].geometry_plans
    for plan in plans:
        assert validate_geometry_plan(
            plan, {asset.asset_id for asset in berlin_run["result"].assets}).ok
        assert {zone.zone_id for zone in plan.safe_zones} == {
            "subtitle_safe_zone", "edge_safe_zone", "title_safe_zone"}
        assert all(0 <= node.importance <= 1 and 0 <= node.salience <= 1
                   for node in plan.nodes)
        assert all(node.min_width > 0 and node.min_height > 0
                   for node in plan.nodes)
        assert all(constraint.reason for constraint in plan.constraints)
        assert any(constraint.strength == ConstraintStrength.HARD
                   for constraint in plan.constraints)
        assert any(constraint.strength != ConstraintStrength.HARD
                   for constraint in plan.constraints)


def test_visual_edge_and_group_validation_rejects_unknown_or_self_refs(
        berlin_run):
    causal = next(plan for plan in berlin_run["result"].geometry_plans
                  if plan.visual_family == "causal_network")
    broken_edge = GeometryPlan.from_dict(causal.to_dict())
    broken_edge.edges[0].target_node_id = broken_edge.edges[0].source_node_id
    assert any("self-edge" in error
               for error in validate_geometry_plan(broken_edge).errors)

    grouped = next(plan for plan in berlin_run["result"].geometry_plans
                   if plan.groups)
    broken_group = GeometryPlan.from_dict(grouped.to_dict())
    broken_group.groups[0].node_ids.append("unknown-node")
    assert any("group membership" in error
               for error in validate_geometry_plan(broken_group).errors)


def test_importance_salience_and_safe_zone_corruption_is_rejected(berlin_run):
    plan = GeometryPlan.from_dict(
        berlin_run["result"].geometry_plans[0].to_dict())
    plan.nodes[0].importance = 1.1
    plan.nodes[0].salience = -0.1
    subtitle = next(zone for zone in plan.safe_zones
                    if zone.zone_id == "subtitle_safe_zone")
    object.__setattr__(subtitle, "bounds", replace(subtitle.bounds, y=0.95,
                                                    height=0.20))
    errors = validate_geometry_plan(plan).errors
    assert any("importance" in error for error in errors)
    assert any("salience" in error for error in errors)
    assert any("safe zone outside" in error for error in errors)


def test_containment_map_routes_and_reading_hierarchy(berlin_run):
    plans = berlin_run["result"].geometry_plans
    document = next(plan for plan in plans
                    if plan.visual_family == "document_evidence")
    contained = [constraint for constraint in document.constraints
                 if constraint.constraint_type == ConstraintType.CONTAINED_IN]
    assert contained
    node_by_id = {node.node_id: node for node in document.nodes}
    assert all(node_by_id[item.node_ids[1]].media_kind == "document"
               for item in contained)

    maps = [plan for plan in plans if plan.visual_family == "geographic_map"]
    assert maps
    for plan in maps:
        map_ids = {node.node_id for node in plan.nodes
                   if node.role == VisualRole.MAP or node.media_kind == "map"}
        assert map_ids
        for node in plan.nodes:
            if node.role == VisualRole.CONNECTOR_ENDPOINT:
                assert any(
                    constraint.constraint_type == ConstraintType.CONTAINED_IN
                    and constraint.node_ids[0] == node.node_id
                    and constraint.node_ids[1] in map_ids
                    for constraint in plan.constraints)
    assert all(plan.hierarchy.reading_order
               and plan.hierarchy.primary_node_id
               == plan.hierarchy.reading_order[0] for plan in plans)


def test_asset_aspect_ratio_and_text_estimates_propagate(berlin_run):
    assets = {asset.asset_id: asset for asset in berlin_run["result"].assets}
    asset_nodes = [node for plan in berlin_run["result"].geometry_plans
                   for node in plan.nodes if node.asset_id]
    assert asset_nodes
    for node in asset_nodes:
        asset = assets[node.asset_id]
        assert node.preferred_aspect_ratio == pytest.approx(
            asset.width / asset.height, abs=1e-5)
        if node.media_kind in {"document", "map"}:
            assert not node.can_crop
    text_nodes = [node for plan in berlin_run["result"].geometry_plans
                  for node in plan.nodes if node.text_role is not None]
    assert text_nodes
    assert all(node.estimated_width and node.estimated_height
               and node.max_lines for node in text_nodes)


def test_geometry_signature_and_history_are_semantic_and_deterministic(
        berlin_run):
    result = berlin_run["result"]
    signatures = [plan.semantic_geometry_signature
                  for plan in result.geometry_plans]
    assert len(set(signatures)) >= 5
    history = GeometryHistory(max_window=5)
    for index, signature in enumerate(signatures):
        assert result.geometry_plans[index].recent_geometry_context == \
            history.recent()
        history.record(signature)
    assert history.recent() == signatures[-5:]
    assert all("primary=" in signature and "reading=" in signature
               for signature in signatures)


def test_berlin_semantic_geometry_acceptance(berlin_run):
    result = berlin_run["result"]
    assert len(result.beats) == 12
    assert len(result.geometry_plans) == 12
    assert not any(plan.is_fallback for plan in result.geometry_plans)
    assert any(plan.visual_family == "causal_network" and plan.edges
               for plan in result.geometry_plans)
    character = next(plan for plan in result.geometry_plans
                     if plan.visual_family == "archival_subject")
    assert any(group.semantic_role == "character" for group in character.groups)
    assert any(node.media_kind in {"portrait", "photo"}
               for node in character.nodes)
    known_assets = {asset.asset_id for asset in result.assets}
    assert all(node.asset_id in known_assets
               for plan in result.geometry_plans for node in plan.nodes
               if node.asset_id)


@pytest.mark.parametrize("topic_id", ["chernobyl_gen", "titanic_gen"])
def test_generalization_geometry_has_semantic_structures(
        tmp_path, topic_id):
    from test_generalization import TOPICS
    topic = next(item for item in TOPICS if item["episode_id"] == topic_id)
    from videotool.domain.narration import synthetic_word_timings
    text = topic["text"]
    result = PipelineRunner(ArtifactStore(tmp_path / topic_id),
                            mode="final").run(EpisodeInput(
        episode_id=topic_id, subject=topic["subject"],
        narration=Narration(text=text, words=synthetic_word_timings(text)),
        catalog=[]))
    assert result.ok
    assert len(result.geometry_plans) == len(result.beats)
    assert len({plan.semantic_geometry_signature
                for plan in result.geometry_plans}) >= 3
    assert any(plan.groups for plan in result.geometry_plans)
    assert any(plan.edges for plan in result.geometry_plans)


def test_identical_second_run_resumes_geometry(tmp_path):
    first = run_berlin(tmp_path / "artifacts")
    second = run_berlin(tmp_path / "artifacts")
    assert first.geometry_plans[0].to_dict() == second.geometry_plans[0].to_dict()
    assert second.manifest["stages"]["semantic_geometry"]["status"] == "resumed"


def test_one_beat_builder_failure_uses_valid_semantic_fallback(tmp_path):
    class FailOneBuilder(SemanticGeometryBuilder):
        def build_plan(self, beat, *args, **kwargs):
            if beat.beat_id == "beat_0004":
                raise RuntimeError("injected geometry failure")
            return super().build_plan(beat, *args, **kwargs)

    data = load_episode()
    runner = PipelineRunner(ArtifactStore(tmp_path / "artifacts"), mode="final")
    runner.geometry_builder = FailOneBuilder()
    result = runner.run(EpisodeInput(**data))
    fallbacks = [plan for plan in result.geometry_plans if plan.is_fallback]
    assert result.ok and len(fallbacks) == 1
    assert fallbacks[0].beat_id == "beat_0004"
    assert validate_geometry_plan(fallbacks[0]).ok
    assert any(repair["stage"] == "semantic_geometry"
               for repair in result.manifest["repairs"])


def test_meta_consistent_semantic_geometry_corruption_invalidates(tmp_path):
    root = tmp_path / "artifacts"
    run_berlin(root)
    store = ArtifactStore(root)
    episode_id = "berlin_wall_phase1"
    payload = store.load(episode_id, "semantic_geometry")
    grouped = next(plan for plan in payload if plan["groups"])
    grouped["groups"][0]["node_ids"].append("unknown-node")
    store.save(episode_id, "semantic_geometry", payload)
    meta = store.load(episode_id, "stage_meta")
    meta["semantic_geometry"]["output_hash"] = stable_hash(payload)
    store.save(episode_id, "stage_meta", meta)
    result = run_berlin(root)
    assert result.ok
    assert result.manifest["stages"]["semantic_geometry"]["status"] == \
        "invalidated"


def test_geometry_version_change_invalidates_only_geometry_branch(tmp_path):
    root = tmp_path / "artifacts"
    run_berlin(root)
    store = ArtifactStore(root)
    meta = store.load("berlin_wall_phase1", "stage_meta")
    meta["semantic_geometry"]["stage_version"] = \
        STAGE_VERSIONS["semantic_geometry"] - 1
    store.save("berlin_wall_phase1", "stage_meta", meta)
    result = run_berlin(root)
    assert result.manifest["stages"]["semantic_geometry"]["status"] == \
        "invalidated"
    assert result.manifest["stages"]["motion_plan"]["status"] == "resumed"


def test_strategy_and_geometry_relevant_art_direction_invalidate_geometry(
        tmp_path):
    root = tmp_path / "artifacts"
    run_berlin(root)
    store = ArtifactStore(root)
    episode_id = "berlin_wall_phase1"

    art = store.load(episode_id, "episode_art_direction")
    art["geometry"].append("precise structured grid")
    store.save(episode_id, "episode_art_direction", art)
    meta = store.load(episode_id, "stage_meta")
    meta["episode_art_direction"]["output_hash"] = stable_hash(art)
    store.save(episode_id, "stage_meta", meta)
    changed_art = run_berlin(root)
    assert changed_art.manifest["stages"]["semantic_geometry"]["status"] == \
        "invalidated"

    feasibility = store.load(episode_id, "strategy_feasibility")
    feasibility["records"][0]["selected_strategy"] = "full_frame_archival"
    feasibility["records"][0]["visual_family"] = "archival_subject"
    store.save(episode_id, "strategy_feasibility", feasibility)
    meta = store.load(episode_id, "stage_meta")
    meta["strategy_feasibility"]["output_hash"] = stable_hash(feasibility)
    store.save(episode_id, "stage_meta", meta)
    changed_strategy = run_berlin(root)
    assert changed_strategy.manifest["stages"]["semantic_geometry"]["status"] == \
        "invalidated"
    assert changed_strategy.geometry_plans[0].visual_family == "archival_subject"


def test_unrelated_art_direction_metadata_does_not_invalidate_geometry(tmp_path):
    root = tmp_path / "artifacts"
    run_berlin(root)
    store = ArtifactStore(root)
    episode_id = "berlin_wall_phase1"
    art = store.load(episode_id, "episode_art_direction")
    art["accent"]["primary"] = "different_non_geometry_accent"
    store.save(episode_id, "episode_art_direction", art)
    meta = store.load(episode_id, "stage_meta")
    meta["episode_art_direction"]["output_hash"] = stable_hash(art)
    store.save(episode_id, "stage_meta", meta)
    result = run_berlin(root)
    assert result.manifest["stages"]["visual_compositions"]["status"] == \
        "invalidated"
    assert result.manifest["stages"]["semantic_geometry"]["status"] == "resumed"


class _DimensionFixtureProvider(FixtureMediaProvider):
    provider_version = 91

    def fetch(self, candidate):
        return FetchedMedia(
            synthesize_png(candidate.candidate_id,
                           candidate.width, candidate.height),
            content_type="image/png", media_url=candidate.media_url)


class _DimensionRunner(PipelineRunner):
    def _build_media_provider(self, ep, cfg):
        return _DimensionFixtureProvider(ep.catalog)


def test_selected_media_aspect_change_invalidates_geometry(tmp_path):
    first_data = load_episode()
    first_data["catalog"] = [
        {**row, "width": 1000, "height": 800}
        for row in first_data["catalog"]]
    root = tmp_path / "artifacts"
    first = run_berlin(root, first_data, _DimensionRunner)

    second_data = load_episode()
    second_data["catalog"] = [
        {**row, "asset_id": f"{row['asset_id']}:square",
         "width": 1100, "height": 1100}
        for row in second_data["catalog"]]
    second = run_berlin(root, second_data, _DimensionRunner)
    assert {node.preferred_aspect_ratio for plan in first.geometry_plans
            for node in plan.nodes if node.asset_id} != \
        {node.preferred_aspect_ratio for plan in second.geometry_plans
         for node in plan.nodes if node.asset_id}
    assert second.manifest["stages"]["semantic_geometry"]["status"] == \
        "invalidated"


def test_geometry_projection_ignores_timing_but_tracks_asset_metadata(
        berlin_run):
    result = berlin_run["result"]
    projection = geometry_input_projection(
        result.compositions, result.assets, result.strategy_plan,
        result.art_direction, result.semantic_anchors, result.timing_bindings)
    changed_assets = copy.deepcopy(result.assets)
    changed_assets[0].width *= 2
    changed = geometry_input_projection(
        result.compositions, changed_assets, result.strategy_plan,
        result.art_direction, result.semantic_anchors, result.timing_bindings)
    assert stable_hash(projection) != stable_hash(changed)
    changed_bindings = copy.deepcopy(result.timing_bindings)
    changed_bindings[0].start_sec += 10
    changed_bindings[0].end_sec += 10
    retimed = geometry_input_projection(
        result.compositions, result.assets, result.strategy_plan,
        result.art_direction, result.semantic_anchors, changed_bindings)
    assert stable_hash(projection) == stable_hash(retimed)


def test_production_geometry_has_no_fixture_vocabulary():
    from pathlib import Path
    package = Path(__file__).resolve().parents[1] / "videotool"
    roots = [package / "domain" / "geometry.py",
             package / "editorial" / "geometry"]
    terms = ("schabowski", "chernobyl", "titanic")
    hits = []
    paths = [roots[0], *roots[1].rglob("*.py")]
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        if any(term in text for term in terms):
            hits.append(str(path))
    assert not hits, hits


def test_required_constraint_abstractions_are_available():
    required = {
        "INSIDE_CANVAS", "OUTSIDE_SAFE_ZONE", "MIN_SIZE", "MAX_SIZE",
        "ASPECT_RATIO", "PREFER_REGION", "AVOID_REGION", "NEAR",
        "FAR_FROM", "ALIGN", "STACK", "ORDER_LEFT_TO_RIGHT",
        "ORDER_TOP_TO_BOTTOM", "NO_OVERLAP", "CONTAINED_IN", "CONNECT",
        "ANCHOR_TO", "GROUP", "BALANCE", "READING_ORDER",
    }
    assert required <= {item.value for item in ConstraintType}
    assert {"HARD", "STRONG", "MEDIUM", "WEAK"} == {
        item.value for item in ConstraintStrength}
    assert CanvasRegion.FULL.value == "FULL"
    assert EdgeType.CAUSES.value == "CAUSES"
