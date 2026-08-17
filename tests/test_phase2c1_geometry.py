"""Phase 2C.1 semantic geometry domain, integrity and acceptance tests."""
from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from videotool.artifacts import ArtifactStore
from videotool.domain.art_direction import EpisodeArtDirection
from videotool.domain.composition import (CompositionLayer, LayerType,
                                          VisualComposition)
from videotool.domain.geometry import (CanvasRegion, ConstraintStrength,
                                       ConstraintType, EdgeType, GeometryHistory,
                                       GeometryPlan, NormalizedRect,
                                       SolvedPlacement, VisualRole)
from videotool.domain.narration import Narration
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.editorial.geometry import (GEOMETRY_POLICY_VERSION,
                                           GEOMETRY_SIGNATURE_VERSION,
                                           GEOMETRY_SOLVER_VERSION,
                                           SEMANTIC_GEOMETRY_VERSION,
                                           SemanticGeometryBuilder,
                                           debug_geometry_plan,
                                           geometry_input_projection,
                                           semantic_geometry_signature,
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
    assert SEMANTIC_GEOMETRY_VERSION == 3
    assert GEOMETRY_POLICY_VERSION >= 1
    assert GEOMETRY_SIGNATURE_VERSION == 3
    assert GEOMETRY_SOLVER_VERSION == 1
    assert STAGE_VERSIONS["semantic_geometry"] == 3


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


def _semantic_plan(family: str, *, dates=None, events=None, locations=None,
                   relationships=None, composition=None, recent=None):
    beat = SemanticBeat(
        beat_id="semantic_test", start_sec=1, end_sec=2,
        narration_text="Semantic geometry test", word_start=0, word_end=3,
        semantic_function={
            "chronological_timeline": SemanticFunction.CHRONOLOGY,
            "causal_network": SemanticFunction.CAUSAL_EXPLANATION,
            "geographic_map": SemanticFunction.GEOGRAPHIC_MOVEMENT,
            "document_evidence": SemanticFunction.EVIDENCE,
            "archival_subject": SemanticFunction.CHARACTER_INTRODUCTION,
        }.get(family, SemanticFunction.ATMOSPHERE),
        visual_intent="explain structure", entities=["subject"],
        dates=list(dates or []), events=list(events or []),
        locations=list(locations or []),
        relationships=list(relationships or []))
    art = EpisodeArtDirection(
        episode_id="ep", subject="subject", geometry=["asymmetric frames"])
    return SemanticGeometryBuilder().build_plan(
        beat, family, "semantic_test_strategy", [], [], art, [],
        composition, [], list(recent or []))


def test_semantic_inventory_can_exceed_bootstrap_layer_count():
    composition = VisualComposition(
        composition_id="bootstrap", beat_id="semantic_test",
        visual_family="chronological_timeline", strategy="legacy",
        layers=[CompositionLayer("only_layer", LayerType.LABEL,
                                 0.1, 0.1, 0.2, 0.1)])
    plan = _semantic_plan(
        "chronological_timeline", dates=["1989", "1990"],
        events=["opening", "reunification"], composition=composition)
    assert len(plan.nodes) == 4 > len(composition.layers)
    assert sum(node.source_layer_id is None for node in plan.nodes) == 3
    assert validate_geometry_plan(plan).ok


def test_timeline_inventory_is_generated_from_semantic_events_and_dates():
    plan = _semantic_plan("chronological_timeline", dates=["1989"],
                          events=["protests", "border opens"])
    assert len([node for node in plan.nodes
                if node.role == VisualRole.TIMELINE_NODE]) == 3
    assert [edge.relationship_type for edge in plan.edges] == [
        EdgeType.BEFORE, EdgeType.BEFORE]


def test_causal_topology_is_generated_from_semantic_relationships():
    plan = _semantic_plan("causal_network",
                          relationships=["pressure -> failure",
                                         "failure -> shutdown"])
    assert len(plan.nodes) == 3
    assert [(edge.relationship_type, edge.directed) for edge in plan.edges] == [
        (EdgeType.CAUSES, True), (EdgeType.CAUSES, True)]


def test_map_endpoints_are_generated_from_semantic_locations():
    plan = _semantic_plan("geographic_map",
                          locations=["origin", "crossing", "destination"])
    endpoints = [node for node in plan.nodes
                 if node.role == VisualRole.CONNECTOR_ENDPOINT]
    assert len(endpoints) == 3
    assert any(edge.relationship_type == EdgeType.ROUTE_TO
               for edge in plan.edges)


def test_equivalent_graph_ids_have_the_same_semantic_signature():
    original = _semantic_plan("causal_network",
                              relationships=["A -> B", "B -> C"])
    renamed = GeometryPlan.from_dict(original.to_dict())
    mapping = {node.node_id: f"generated-id-{index}"
               for index, node in enumerate(renamed.nodes)}
    for node in renamed.nodes:
        node.node_id = mapping[node.node_id]
    for edge in renamed.edges:
        edge.source_node_id = mapping[edge.source_node_id]
        edge.target_node_id = mapping[edge.target_node_id]
    for group in renamed.groups:
        group.node_ids = [mapping[item] for item in group.node_ids]
    for constraint in renamed.constraints:
        constraint.node_ids = [mapping[item] for item in constraint.node_ids]
    hierarchy = renamed.hierarchy
    hierarchy.primary_node_id = mapping[hierarchy.primary_node_id]
    hierarchy.secondary_node_ids = [mapping[item]
                                    for item in hierarchy.secondary_node_ids]
    hierarchy.tertiary_node_ids = [mapping[item]
                                   for item in hierarchy.tertiary_node_ids]
    hierarchy.reading_order = [mapping[item] for item in hierarchy.reading_order]
    assert semantic_geometry_signature(original) == \
        semantic_geometry_signature(renamed)


def test_chain_and_star_topologies_have_different_signatures():
    chain = _semantic_plan("causal_network",
                           relationships=["A -> B", "B -> C"])
    star = _semantic_plan("causal_network",
                          relationships=["A -> B", "A -> C"])
    assert chain.semantic_geometry_signature != star.semantic_geometry_signature


def test_reading_direction_is_semantic_and_style_agrees():
    plans = [
        _semantic_plan("chronological_timeline", events=["one", "two"]),
        _semantic_plan("causal_network", relationships=["A -> B"]),
        _semantic_plan("geographic_map", locations=["A", "B"]),
        _semantic_plan("full_frame_cinematic"),
    ]
    directions = {plan.hierarchy.reading_direction for plan in plans}
    assert directions == {"CHRONOLOGICAL_HORIZONTAL", "CAUSE_TO_EFFECT",
                          "ROUTE_FLOW", "OVERLAY_HIERARCHY"}
    assert all(plan.hierarchy.reading_direction
               == plan.style_hints.preferred_reading_direction
               for plan in plans)


def test_solver_generates_one_valid_placement_per_semantic_node(berlin_run):
    for plan in berlin_run["result"].geometry_plans:
        assert plan.solver_candidate_count >= 2
        assert plan.solver_explanation
        assert plan.structural_geometry_signature.startswith("solver_v")
        assert plan.solver_score["hard_constraint_score"] == 1.0
        assert "total_score" in plan.solver_score
        assert {item.node_id for item in plan.solved_placements} == {
            node.node_id for node in plan.nodes}
        assert len(plan.solved_placements) == len(plan.nodes)
        for placement in plan.solved_placements:
            rect = placement.bounds
            assert 0 <= rect.x <= 1 and 0 <= rect.y <= 1
            assert rect.x + rect.width <= 1.000001
            assert rect.y + rect.height <= 1.000001
        assert validate_geometry_plan(plan).ok


def test_solver_is_topology_aware_for_timeline_causal_map_and_document():
    timeline = _semantic_plan("chronological_timeline",
                              dates=["1988", "1989", "1990"])
    centers = [
        next(p.bounds.x + p.bounds.width / 2 for p in timeline.solved_placements
             if p.node_id == node_id)
        for node_id in timeline.hierarchy.reading_order
    ]
    assert centers == sorted(centers)

    causal = _semantic_plan("causal_network",
                            relationships=["A -> B", "A -> C"])
    by_id = {p.node_id: p.bounds for p in causal.solved_placements}
    for edge in causal.edges:
        assert by_id[edge.source_node_id].x <= by_id[edge.target_node_id].x

    mapped = _semantic_plan("geographic_map", locations=["A", "B", "C"])
    map_rect = next(p.bounds for p in mapped.solved_placements
                    if next(n for n in mapped.nodes
                            if n.node_id == p.node_id).role == VisualRole.MAP)
    for placement in mapped.solved_placements:
        node = next(n for n in mapped.nodes if n.node_id == placement.node_id)
        if node.role == VisualRole.CONNECTOR_ENDPOINT:
            assert map_rect.x <= placement.bounds.x
            assert placement.bounds.x + placement.bounds.width <= \
                map_rect.x + map_rect.width

    document = _semantic_plan("document_evidence")
    assert validate_geometry_plan(document).ok
    contained = [c for c in document.constraints
                 if c.constraint_type == ConstraintType.CONTAINED_IN]
    assert contained


def test_structural_signature_excludes_asset_ids_and_absolute_timing():
    first = _semantic_plan("full_frame_cinematic")
    second = GeometryPlan.from_dict(first.to_dict())
    second.nodes[0].asset_id = "different:file:name"
    second.nodes[0].timing_anchor_id = "later-anchor"
    assert first.structural_geometry_signature == \
        second.structural_geometry_signature


def test_history_aware_selection_penalizes_recent_exact_geometry():
    first = _semantic_plan("full_frame_cinematic")
    repeated = _semantic_plan(
        "full_frame_cinematic",
        recent=[first.structural_geometry_signature])
    assert repeated.solver_score["novelty_score"] < 1.0
    assert repeated.solver_score["hard_constraint_score"] == 1.0


def test_meta_consistent_solved_geometry_corruption_invalidates(tmp_path):
    root = tmp_path / "artifacts"
    run_berlin(root)
    store = ArtifactStore(root)
    episode_id = "berlin_wall_phase1"
    payload = store.load(episode_id, "semantic_geometry")
    payload[0]["solved_placements"][0]["bounds"]["y"] = 0.90
    store.save(episode_id, "semantic_geometry", payload)
    meta = store.load(episode_id, "stage_meta")
    meta["semantic_geometry"]["output_hash"] = stable_hash(payload)
    store.save(episode_id, "stage_meta", meta)
    result = run_berlin(root)
    assert result.ok
    assert result.manifest["stages"]["semantic_geometry"]["status"] == \
        "invalidated"


def test_solver_rejects_hard_overlap_when_overlap_is_prohibited():
    plan = _semantic_plan("chronological_timeline",
                          events=["one", "two", "three"])
    broken = GeometryPlan.from_dict(plan.to_dict())
    first = broken.solved_placements[0].bounds
    broken.solved_placements[1] = SolvedPlacement(
        broken.solved_placements[1].node_id,
        NormalizedRect(first.x, first.y, first.width, first.height),
        broken.solved_placements[1].z_index,
        broken.solved_placements[1].operator,
        broken.solved_placements[1].region)
    assert any("overlap" in error
               for error in validate_geometry_plan(broken).errors)


def test_timing_only_resume_still_keeps_semantic_geometry(tmp_path):
    root = tmp_path / "artifacts"
    run_berlin(root)
    store = ArtifactStore(root)
    episode_id = "berlin_wall_phase1"
    timing = store.load(episode_id, "narration_timing")
    timing["words"][0]["start_sec"] += 0.25
    timing["words"][0]["end_sec"] += 0.25
    store.save(episode_id, "narration_timing", timing)
    meta = store.load(episode_id, "stage_meta")
    meta["narration_timing"]["output_hash"] = stable_hash(timing)
    store.save(episode_id, "stage_meta", meta)
    result = run_berlin(root)
    assert result.manifest["stages"]["semantic_geometry"]["status"] == "resumed"


def test_bootstrap_composition_coordinates_are_not_mutated_by_solver(tmp_path):
    root = tmp_path / "artifacts"
    result = run_berlin(root)
    stored = ArtifactStore(root).load("berlin_wall_phase1",
                                      "visual_compositions")
    assert stored == [composition.to_dict()
                      for composition in result.compositions]


def test_required_constraint_abstractions_are_available():
    required = {
        "INSIDE_CANVAS", "OUTSIDE_SAFE_ZONE", "MIN_SIZE", "MAX_SIZE",
        "ASPECT_RATIO", "PREFER_REGION", "AVOID_REGION", "NEAR",
        "FAR_FROM", "ALIGN", "STACK", "ORDER_LEFT_TO_RIGHT",
        "ORDER_TOP_TO_BOTTOM", "NO_OVERLAP", "CONTAINED_IN", "CONNECT",
        "ANCHOR_TO", "GROUP", "BALANCE", "READING_ORDER",
        "SUBTITLE_EXCLUSION", "MIN_DISTANCE",
    }
    assert required <= {item.value for item in ConstraintType}
    assert {"HARD", "STRONG", "MEDIUM", "WEAK"} == {
        item.value for item in ConstraintStrength}
    assert CanvasRegion.FULL.value == "FULL"
    assert EdgeType.CAUSES.value == "CAUSES"
