"""Phase 2C.2 Hardening — constraint completeness and structural novelty tests.

Covers:
  - HARD constraint enforcement for all declared constraint types
  - Structural vs semantic geometry signature domain separation
  - Real runner history integration (no manual mock of recent_geometry_context)
  - HARD validity > novelty invariant
  - Fallback lifecycle (constraints, signature, history)
  - Version bump regression (old artifacts invalidated)
  - Debug report acceptance
"""
from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from videotool.artifacts import ArtifactStore
from videotool.domain.art_direction import EpisodeArtDirection
from videotool.domain.composition import (CompositionLayer, LayerType,
                                          VisualComposition)
from videotool.domain.geometry import (CanvasRegion, CanvasSpec,
                                       ConstraintStrength, ConstraintType,
                                       EdgeType, GeometryConstraint,
                                       GeometryHistory, GeometryPlan,
                                       GeometryStyleHints, NormalizedRect,
                                       SafeZone, SolvedPlacement,
                                       VisualEdge, VisualGroup,
                                       VisualHierarchy, VisualNode,
                                       VisualRole)
from videotool.domain.narration import Narration, synthetic_word_timings
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.editorial.geometry import (GEOMETRY_SCORE_VERSION,
                                           GEOMETRY_SOLVER_VERSION,
                                           GeometrySolver,
                                           SemanticGeometryBuilder,
                                           debug_geometry_plan,
                                           semantic_geometry_signature,
                                           structural_geometry_signature,
                                           validate_geometry_plan)
from videotool.editorial.geometry.solver import GeometryCandidate
from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.fingerprints import STAGE_VERSIONS, stable_hash
from videotool.pipeline.runner import EpisodeInput, PipelineRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(node_id: str, role=VisualRole.EVIDENCE, **kw) -> VisualNode:
    return VisualNode(node_id=node_id, beat_id="test_beat", role=role,
                      min_width=kw.get("min_width", 0.08),
                      min_height=kw.get("min_height", 0.05),
                      importance=kw.get("importance", 0.8),
                      salience=kw.get("salience", 0.7),
                      preferred_regions=[CanvasRegion.CENTER],
                      can_crop=kw.get("can_crop", True),
                      **{k: v for k, v in kw.items()
                         if k not in ("min_width", "min_height", "importance",
                                      "salience", "can_crop")})


def _make_placement(node_id: str, x: float, y: float, w: float,
                    h: float, z: int = 0) -> SolvedPlacement:
    return SolvedPlacement(node_id, NormalizedRect(x, y, w, h), z,
                           "test_op", CanvasRegion.CENTER,
                           alignment="center")


def _base_plan(*nodes, constraints=None, edges=None, groups=None,
               recent=None, family="full_frame_cinematic"):
    """Minimal plan that passes validation, for injecting synthetic constraints."""
    node_list = list(nodes)
    ids = [n.node_id for n in node_list]
    return GeometryPlan(
        beat_id="test_beat", visual_family=family,
        nodes=node_list,
        groups=list(groups or []),
        edges=list(edges or []),
        hierarchy=VisualHierarchy(ids[0], reading_order=ids,
                                  reading_direction="LEFT_TO_RIGHT"),
        constraints=list(constraints or []),
        canvas=CanvasSpec(),
        safe_zones=[
            SafeZone("subtitle_safe_zone", "subtitles",
                     NormalizedRect(0.05, 0.84, 0.90, 0.15)),
            SafeZone("edge_safe_zone", "edge",
                     NormalizedRect(0.04, 0.04, 0.92, 0.92), True),
            SafeZone("title_safe_zone", "title",
                     NormalizedRect(0.05, 0.04, 0.90, 0.12)),
        ],
        style_hints=GeometryStyleHints(
            preferred_reading_direction="LEFT_TO_RIGHT"),
        semantic_geometry_signature="test_semantic_sig",
        recent_geometry_context=list(recent or []),
    )


def _semantic_plan(family: str, **kw):
    """Build a full plan through the builder + solver, same as Phase 2C.1 tests."""
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
        dates=list(kw.get("dates", [])),
        events=list(kw.get("events", [])),
        locations=list(kw.get("locations", [])),
        relationships=list(kw.get("relationships", [])))
    art = EpisodeArtDirection(
        episode_id="ep", subject="subject", geometry=["asymmetric frames"])
    return SemanticGeometryBuilder().build_plan(
        beat, family, "test_strategy", [], [], art, [],
        kw.get("composition"), [], list(kw.get("recent", [])))


def run_berlin(root, data=None, runner_cls=PipelineRunner):
    data = data or load_episode()
    return runner_cls(ArtifactStore(root), mode="final").run(
        EpisodeInput(**data))


# ===========================================================================
# HARD CONSTRAINT ENFORCEMENT
# ===========================================================================

class TestAspectRatioHardConstraint:
    def test_aspect_ratio_violation_is_hard_rejected(self):
        """A HARD ASPECT_RATIO constraint rejects a candidate whose solved
        width/height deviates beyond the tolerance."""
        node = _make_node("n1", can_crop=False)
        constraint = GeometryConstraint(
            "gc:ar", ConstraintType.ASPECT_RATIO, ["n1"],
            ConstraintStrength.HARD, 1.0,
            {"ratio": 2.0, "crop_allowed": False},
            "Must be 2:1")
        plan = _base_plan(node, constraints=[constraint])
        # Candidate has ratio 1.0 (0.20/0.20), violates 2.0 by >5%
        candidate = GeometryCandidate("c1", ["test"],
                                       [_make_placement("n1", 0.1, 0.1, 0.20, 0.20)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert scored.hard_violations
        assert any("aspect ratio" in v for v in scored.hard_violations)

    def test_aspect_ratio_within_crop_tolerance_passes(self):
        node = _make_node("n1", can_crop=True)
        constraint = GeometryConstraint(
            "gc:ar", ConstraintType.ASPECT_RATIO, ["n1"],
            ConstraintStrength.HARD, 1.0,
            {"ratio": 1.5, "crop_allowed": True},
            "Should be ~1.5")
        plan = _base_plan(node, constraints=[constraint])
        # Candidate has ratio 1.6 (0.32/0.20), within 15% of 1.5
        candidate = GeometryCandidate("c1", ["test"],
                                       [_make_placement("n1", 0.1, 0.1, 0.32, 0.20)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert not any("aspect ratio" in v for v in scored.hard_violations)

    def test_aspect_ratio_strong_is_not_hard_enforced(self):
        """STRONG constraints must NOT cause hard rejection."""
        node = _make_node("n1")
        constraint = GeometryConstraint(
            "gc:ar", ConstraintType.ASPECT_RATIO, ["n1"],
            ConstraintStrength.STRONG, 0.85,
            {"ratio": 2.0, "crop_allowed": False},
            "Prefer 2:1")
        plan = _base_plan(node, constraints=[constraint])
        candidate = GeometryCandidate("c1", ["test"],
                                       [_make_placement("n1", 0.1, 0.1, 0.20, 0.20)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert not any("aspect ratio" in v for v in scored.hard_violations)


class TestConnectHardConstraint:
    def test_connect_missing_endpoint_is_rejected(self):
        n1 = _make_node("n1")
        n2 = _make_node("n2")
        constraint = GeometryConstraint(
            "gc:conn", ConstraintType.CONNECT, ["n1", "n2"],
            ConstraintStrength.HARD, 1.0, {}, "Must connect")
        plan = _base_plan(n1, n2, constraints=[constraint])
        # Only n1 placed, n2 missing
        candidate = GeometryCandidate("c1", ["test"],
                                       [_make_placement("n1", 0.1, 0.1, 0.2, 0.2)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert any("CONNECT" in v for v in scored.hard_violations)

    def test_connect_zero_distance_is_rejected(self):
        n1 = _make_node("n1")
        n2 = _make_node("n2")
        constraint = GeometryConstraint(
            "gc:conn", ConstraintType.CONNECT, ["n1", "n2"],
            ConstraintStrength.HARD, 1.0, {}, "Must connect")
        plan = _base_plan(n1, n2, constraints=[constraint])
        # Both at exactly the same position
        candidate = GeometryCandidate("c1", ["test"], [
            _make_placement("n1", 0.4, 0.4, 0.2, 0.2),
            _make_placement("n2", 0.4, 0.4, 0.2, 0.2)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert any("CONNECT zero distance" in v for v in scored.hard_violations)

    def test_connect_valid_endpoints_passes(self):
        n1 = _make_node("n1")
        n2 = _make_node("n2")
        constraint = GeometryConstraint(
            "gc:conn", ConstraintType.CONNECT, ["n1", "n2"],
            ConstraintStrength.HARD, 1.0, {}, "Must connect")
        plan = _base_plan(n1, n2, constraints=[constraint])
        candidate = GeometryCandidate("c1", ["test"], [
            _make_placement("n1", 0.1, 0.3, 0.2, 0.2),
            _make_placement("n2", 0.6, 0.3, 0.2, 0.2)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert not any("CONNECT" in v for v in scored.hard_violations)


class TestReadingOrderHardConstraint:
    def test_reading_order_violation_is_rejected(self):
        """HARD READING_ORDER uses declared order from constraint node_ids,
        not derived from positions."""
        n1 = _make_node("n1")
        n2 = _make_node("n2")
        n3 = _make_node("n3")
        constraint = GeometryConstraint(
            "gc:ro", ConstraintType.READING_ORDER, ["n1", "n2", "n3"],
            ConstraintStrength.HARD, 1.0,
            {"direction": "LEFT_TO_RIGHT"},
            "Declared order")
        plan = _base_plan(n1, n2, n3, constraints=[constraint])
        # n2 is to the LEFT of n1, violating declared L-to-R order
        candidate = GeometryCandidate("c1", ["test"], [
            _make_placement("n1", 0.5, 0.3, 0.15, 0.15),
            _make_placement("n2", 0.1, 0.3, 0.15, 0.15),
            _make_placement("n3", 0.7, 0.3, 0.15, 0.15)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert any("READING_ORDER" in v for v in scored.hard_violations)

    def test_reading_order_correct_passes(self):
        n1 = _make_node("n1")
        n2 = _make_node("n2")
        constraint = GeometryConstraint(
            "gc:ro", ConstraintType.READING_ORDER, ["n1", "n2"],
            ConstraintStrength.HARD, 1.0,
            {"direction": "CHRONOLOGICAL_HORIZONTAL"},
            "Declared chronological order")
        plan = _base_plan(n1, n2, constraints=[constraint])
        candidate = GeometryCandidate("c1", ["test"], [
            _make_placement("n1", 0.1, 0.3, 0.15, 0.15),
            _make_placement("n2", 0.5, 0.3, 0.15, 0.15)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert not any("READING_ORDER" in v for v in scored.hard_violations)


class TestOrderLeftToRightHardConstraint:
    def test_order_ltr_violation_is_rejected(self):
        n1 = _make_node("n1")
        n2 = _make_node("n2")
        constraint = GeometryConstraint(
            "gc:ltr", ConstraintType.ORDER_LEFT_TO_RIGHT, ["n1", "n2"],
            ConstraintStrength.HARD, 1.0, {}, "n1 left of n2")
        plan = _base_plan(n1, n2, constraints=[constraint])
        # n1 at x=0.6, n2 at x=0.1 → violation
        candidate = GeometryCandidate("c1", ["test"], [
            _make_placement("n1", 0.6, 0.3, 0.15, 0.15),
            _make_placement("n2", 0.1, 0.3, 0.15, 0.15)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert any("ORDER_LEFT_TO_RIGHT" in v for v in scored.hard_violations)


class TestOrderTopToBottomHardConstraint:
    def test_order_ttb_violation_is_rejected(self):
        n1 = _make_node("n1")
        n2 = _make_node("n2")
        constraint = GeometryConstraint(
            "gc:ttb", ConstraintType.ORDER_TOP_TO_BOTTOM, ["n1", "n2"],
            ConstraintStrength.HARD, 1.0, {}, "n1 above n2")
        plan = _base_plan(n1, n2, constraints=[constraint])
        # n1 at y=0.7, n2 at y=0.1 → violation
        candidate = GeometryCandidate("c1", ["test"], [
            _make_placement("n1", 0.3, 0.7, 0.15, 0.15),
            _make_placement("n2", 0.3, 0.1, 0.15, 0.15)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert any("ORDER_TOP_TO_BOTTOM" in v for v in scored.hard_violations)


class TestAlignHardConstraint:
    def test_align_horizontal_center_violation(self):
        n1 = _make_node("n1")
        n2 = _make_node("n2")
        constraint = GeometryConstraint(
            "gc:align", ConstraintType.ALIGN, ["n1", "n2"],
            ConstraintStrength.HARD, 1.0,
            {"axis": "horizontal", "anchor": "center", "tolerance": 0.02},
            "Must be horizontally centered")
        plan = _base_plan(n1, n2, constraints=[constraint])
        # n1 center-y = 0.1 + 0.15/2 = 0.175
        # n2 center-y = 0.5 + 0.15/2 = 0.575  → off by 0.4, violates tol=0.02
        candidate = GeometryCandidate("c1", ["test"], [
            _make_placement("n1", 0.1, 0.1, 0.15, 0.15),
            _make_placement("n2", 0.5, 0.5, 0.15, 0.15)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert any("ALIGN" in v for v in scored.hard_violations)

    def test_align_within_tolerance_passes(self):
        n1 = _make_node("n1")
        n2 = _make_node("n2")
        constraint = GeometryConstraint(
            "gc:align", ConstraintType.ALIGN, ["n1", "n2"],
            ConstraintStrength.HARD, 1.0,
            {"axis": "horizontal", "anchor": "center", "tolerance": 0.03},
            "Must be horizontally centered")
        plan = _base_plan(n1, n2, constraints=[constraint])
        # Both at y=0.3, same center-y → within tolerance
        candidate = GeometryCandidate("c1", ["test"], [
            _make_placement("n1", 0.1, 0.30, 0.15, 0.15),
            _make_placement("n2", 0.5, 0.31, 0.15, 0.15)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert not any("ALIGN" in v for v in scored.hard_violations)


class TestStackHardConstraint:
    def test_stack_vertical_gap_violation(self):
        n1 = _make_node("n1")
        n2 = _make_node("n2")
        constraint = GeometryConstraint(
            "gc:stack", ConstraintType.STACK, ["n1", "n2"],
            ConstraintStrength.HARD, 1.0,
            {"axis": "vertical", "gap_tolerance": 0.04},
            "Must stack vertically")
        plan = _base_plan(n1, n2, constraints=[constraint])
        # n1 bottom = 0.1 + 0.15 = 0.25.  n2 top = 0.6. Gap = 0.35 > 0.04
        candidate = GeometryCandidate("c1", ["test"], [
            _make_placement("n1", 0.3, 0.10, 0.15, 0.15),
            _make_placement("n2", 0.3, 0.60, 0.15, 0.15)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert any("STACK" in v for v in scored.hard_violations)


class TestMinDistanceHardConstraint:
    def test_min_distance_too_close_is_rejected(self):
        n1 = _make_node("n1")
        n2 = _make_node("n2")
        constraint = GeometryConstraint(
            "gc:md", ConstraintType.MIN_DISTANCE, ["n1", "n2"],
            ConstraintStrength.HARD, 1.0,
            {"min_distance": 0.5},
            "Must be far apart")
        plan = _base_plan(n1, n2, constraints=[constraint])
        # Centers at (0.175, 0.175) and (0.275, 0.175) → distance ~0.1
        candidate = GeometryCandidate("c1", ["test"], [
            _make_placement("n1", 0.1, 0.1, 0.15, 0.15),
            _make_placement("n2", 0.2, 0.1, 0.15, 0.15)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert any("MIN_DISTANCE" in v for v in scored.hard_violations)

    def test_min_distance_far_enough_passes(self):
        n1 = _make_node("n1")
        n2 = _make_node("n2")
        constraint = GeometryConstraint(
            "gc:md", ConstraintType.MIN_DISTANCE, ["n1", "n2"],
            ConstraintStrength.HARD, 1.0,
            {"min_distance": 0.1},
            "Must be at least 0.1 apart")
        plan = _base_plan(n1, n2, constraints=[constraint])
        candidate = GeometryCandidate("c1", ["test"], [
            _make_placement("n1", 0.1, 0.3, 0.15, 0.15),
            _make_placement("n2", 0.6, 0.3, 0.15, 0.15)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert not any("MIN_DISTANCE" in v for v in scored.hard_violations)


class TestMaxSizeHardConstraint:
    def test_max_size_exceeded_is_rejected(self):
        node = _make_node("n1")
        constraint = GeometryConstraint(
            "gc:max", ConstraintType.MAX_SIZE, ["n1"],
            ConstraintStrength.HARD, 1.0,
            {"max_width": 0.30, "max_height": 0.30},
            "Must not exceed 30%")
        plan = _base_plan(node, constraints=[constraint])
        # Placement is 0.5x0.5 which exceeds 0.30x0.30
        candidate = GeometryCandidate("c1", ["test"],
                                       [_make_placement("n1", 0.1, 0.1, 0.50, 0.50)])
        solver = GeometrySolver()
        scored = solver.score_candidate(plan, candidate)
        assert any("MAX_SIZE" in v for v in scored.hard_violations)


class TestSafeZoneAndContainmentExisting:
    def test_safe_zone_hard_constraint(self, berlin_run):
        """Existing safe-zone enforcement still works."""
        for plan in berlin_run["result"].geometry_plans:
            assert plan.solver_score["safe_zone_score"] == 1.0

    def test_containment_enforced_in_document_evidence(self, berlin_run):
        docs = [p for p in berlin_run["result"].geometry_plans
                if p.visual_family == "document_evidence"]
        assert docs
        for plan in docs:
            contained = [c for c in plan.constraints
                         if c.constraint_type == ConstraintType.CONTAINED_IN]
            assert contained


# ===========================================================================
# KEY TEST 1 — solver selects valid candidate over invalid
# ===========================================================================

class TestSolverSelectsValidOverInvalid:
    def test_hard_violation_candidate_is_never_selected_over_valid(self):
        """Even if a bad candidate has better novelty/scores, a valid
        candidate with no hard violations must win."""
        plan = _semantic_plan("chronological_timeline",
                              events=["one", "two", "three"])
        solver = GeometrySolver()
        candidates = solver.generate_candidates(plan)
        scored = [solver.score_candidate(plan, c) for c in candidates]
        valid = [c for c in scored if not c.hard_violations]
        invalid = [c for c in scored if c.hard_violations]
        if valid and invalid:
            # A valid candidate must always outscore any invalid candidate
            best_valid = max(c.score["total_score"] for c in valid)
            worst_invalid = max(c.score["total_score"] for c in invalid)
            assert best_valid > worst_invalid

    def test_hard_validity_beats_novelty(self):
        """A candidate with novelty=0.2 but valid must beat a candidate
        with novelty=0.9 but a hard violation."""
        node = _make_node("n1")
        constraint = GeometryConstraint(
            "gc:max", ConstraintType.MAX_SIZE, ["n1"],
            ConstraintStrength.HARD, 1.0,
            {"max_width": 0.25, "max_height": 0.25},
            "Must be small")
        plan = _base_plan(node, constraints=[constraint])
        solver = GeometrySolver()
        # Good candidate: small, within MAX_SIZE
        good = GeometryCandidate("good", ["test"],
                                  [_make_placement("n1", 0.3, 0.3, 0.20, 0.20)])
        # Bad candidate: large, violates MAX_SIZE
        bad = GeometryCandidate("bad", ["test"],
                                 [_make_placement("n1", 0.1, 0.1, 0.50, 0.50)])
        good_scored = solver.score_candidate(plan, good)
        bad_scored = solver.score_candidate(plan, bad)
        assert not good_scored.hard_violations
        assert bad_scored.hard_violations
        assert good_scored.score["total_score"] > bad_scored.score["total_score"]


# ===========================================================================
# KEY TEST 2 — semantic vs structural signature domain separation
# ===========================================================================

class TestSignatureDomainSeparation:
    def test_same_semantics_different_geometry_different_structural_sig(self):
        """Same semantic graph, different spatial arrangements must produce
        same semantic signature but different structural signatures."""
        plan_a = _semantic_plan("full_frame_cinematic")
        plan_b = _semantic_plan("full_frame_cinematic")
        # Semantic signatures are the same (same topology)
        assert plan_a.semantic_geometry_signature == \
            plan_b.semantic_geometry_signature
        # Now mutate the solved placements of B to produce different geometry
        modified = GeometryPlan.from_dict(plan_b.to_dict())
        if modified.solved_placements:
            orig = modified.solved_placements[0].bounds
            modified.solved_placements[0] = SolvedPlacement(
                modified.solved_placements[0].node_id,
                NormalizedRect(0.50, orig.y, orig.width, orig.height),
                modified.solved_placements[0].z_index,
                modified.solved_placements[0].operator,
                CanvasRegion.RIGHT, alignment="edge")
        # Now compute structural signature of modified
        candidate_b = GeometryCandidate(
            "mod", ["test"], modified.solved_placements)
        sig_a = plan_a.structural_geometry_signature
        sig_b = structural_geometry_signature(modified, candidate_b)
        # Structural signatures must differ
        assert sig_a != sig_b
        # Semantic signatures must remain same
        assert plan_a.semantic_geometry_signature == \
            modified.semantic_geometry_signature

    def test_structural_signature_independent_of_asset_id_and_timing(self):
        first = _semantic_plan("full_frame_cinematic")
        second = GeometryPlan.from_dict(first.to_dict())
        second.nodes[0].asset_id = "completely:different:file"
        second.nodes[0].timing_anchor_id = "later-anchor-999"
        assert first.structural_geometry_signature == \
            second.structural_geometry_signature


# ===========================================================================
# KEY TEST 3 — real history integration through the runner
# ===========================================================================

class TestRealHistoryIntegration:
    def test_runner_records_structural_not_semantic_signature(self, tmp_path):
        """The runner must record structural_geometry_signature into history,
        not semantic_geometry_signature. This is the BLOCKER B fix."""
        result = run_berlin(tmp_path / "artifacts")
        assert result.ok
        # Verify that recent_geometry_context contains structural signatures
        for plan in result.geometry_plans:
            for ctx_entry in plan.recent_geometry_context:
                assert ctx_entry.startswith("solver_v"), \
                    f"History entry is not a structural signature: {ctx_entry}"
                assert "|family=" in ctx_entry
            # Verify it does NOT contain semantic signatures
            for ctx_entry in plan.recent_geometry_context:
                assert not ctx_entry.startswith("v3|"), \
                    f"History contains semantic signature: {ctx_entry}"

    def test_repeated_structural_geometry_gets_novelty_penalty(self, tmp_path):
        """When beat B has the same solved structure as beat A, the novelty
        score for beat B must be lower. Exercises real runner path."""
        result = run_berlin(tmp_path / "artifacts")
        # Find plans that have the same structural signature
        sig_count: dict[str, int] = {}
        for plan in result.geometry_plans:
            sig = plan.structural_geometry_signature
            sig_count[sig] = sig_count.get(sig, 0) + 1
        # Plans that appear after a repeated structure should show penalty
        history = GeometryHistory(max_window=5)
        for plan in result.geometry_plans:
            if plan.structural_geometry_signature in history.recent():
                # This plan's novelty should be penalized
                assert plan.solver_score["novelty_score"] < 1.0
            history.record(plan.structural_geometry_signature)


# ===========================================================================
# KEY TEST 4 — HARD validity > novelty invariant
# ===========================================================================

class TestHardValidityBeatsNoveltyInSolver:
    def test_solver_never_selects_hard_violating_candidate(self, berlin_run):
        """Across all berlin beats, the selected candidate must have no
        hard violations."""
        for plan in berlin_run["result"].geometry_plans:
            assert plan.solver_score["hard_constraint_score"] == 1.0
            assert not plan.solver_score.get("hard_violations", [])


# ===========================================================================
# LIFECYCLE TESTS
# ===========================================================================

class TestFallbackLifecycle:
    def test_fallback_has_structural_signature(self, tmp_path):
        class FailOneBuilder(SemanticGeometryBuilder):
            def build_plan(self, beat, *args, **kwargs):
                if beat.beat_id == "beat_0004":
                    raise RuntimeError("injected geometry failure")
                return super().build_plan(beat, *args, **kwargs)

        data = load_episode()
        runner = PipelineRunner(
            ArtifactStore(tmp_path / "artifacts"), mode="final")
        runner.geometry_builder = FailOneBuilder()
        result = runner.run(EpisodeInput(**data))
        fallbacks = [p for p in result.geometry_plans if p.is_fallback]
        assert len(fallbacks) == 1
        fb = fallbacks[0]
        assert fb.structural_geometry_signature
        assert fb.structural_geometry_signature.startswith("solver_v")
        assert validate_geometry_plan(fb).ok

    def test_fallback_respects_hard_constraints(self, tmp_path):
        class FailOneBuilder(SemanticGeometryBuilder):
            def build_plan(self, beat, *args, **kwargs):
                if beat.beat_id == "beat_0004":
                    raise RuntimeError("injected geometry failure")
                return super().build_plan(beat, *args, **kwargs)

        data = load_episode()
        runner = PipelineRunner(
            ArtifactStore(tmp_path / "artifacts"), mode="final")
        runner.geometry_builder = FailOneBuilder()
        result = runner.run(EpisodeInput(**data))
        fb = next(p for p in result.geometry_plans if p.is_fallback)
        assert fb.solver_score["hard_constraint_score"] == 1.0

    def test_fallback_recorded_in_structural_history(self, tmp_path):
        class FailOneBuilder(SemanticGeometryBuilder):
            def build_plan(self, beat, *args, **kwargs):
                if beat.beat_id == "beat_0004":
                    raise RuntimeError("injected geometry failure")
                return super().build_plan(beat, *args, **kwargs)

        data = load_episode()
        runner = PipelineRunner(
            ArtifactStore(tmp_path / "artifacts"), mode="final")
        runner.geometry_builder = FailOneBuilder()
        result = runner.run(EpisodeInput(**data))
        fb = next(p for p in result.geometry_plans if p.is_fallback)
        # The fallback's structural signature should appear in subsequent
        # plans' recent_geometry_context
        fb_index = next(i for i, p in enumerate(result.geometry_plans)
                        if p.is_fallback)
        if fb_index < len(result.geometry_plans) - 1:
            next_plan = result.geometry_plans[fb_index + 1]
            assert fb.structural_geometry_signature in \
                next_plan.recent_geometry_context


class TestSignatureLifecycleOrder:
    def test_structural_signature_computed_after_solve(self, berlin_run):
        """Structural signature must describe final solved geometry,
        not pre-solve semantic topology."""
        for plan in berlin_run["result"].geometry_plans:
            sig = plan.structural_geometry_signature
            assert "solver_v" in sig
            assert "axis=" in sig
            assert "hero=" in sig
            # Must not look like a semantic signature
            assert not sig.startswith("v3|")


# ===========================================================================
# RESUME / VERSIONING
# ===========================================================================

class TestVersionBumpRegression:
    def test_old_solver_version_invalidates_geometry(self, tmp_path):
        root = tmp_path / "artifacts"
        run_berlin(root)
        store = ArtifactStore(root)
        meta = store.load("berlin_wall_phase1", "stage_meta")
        # Simulate old stage version
        meta["semantic_geometry"]["stage_version"] = \
            STAGE_VERSIONS["semantic_geometry"] - 1
        store.save("berlin_wall_phase1", "stage_meta", meta)
        result = run_berlin(root)
        assert result.manifest["stages"]["semantic_geometry"]["status"] == \
            "invalidated"

    def test_timing_only_change_does_not_invalidate_geometry(self, tmp_path):
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
        assert result.manifest["stages"]["semantic_geometry"]["status"] == \
            "resumed"

    def test_versions_bumped_correctly(self):
        assert GEOMETRY_SOLVER_VERSION == 2
        assert GEOMETRY_SCORE_VERSION == 2
        assert STAGE_VERSIONS["semantic_geometry"] == 4


# ===========================================================================
# GENERALIZATION
# ===========================================================================

class TestNoFixtureVocabularyInProduction:
    def test_production_geometry_has_no_fixture_vocabulary(self):
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


# ===========================================================================
# DEBUG REPORT ACCEPTANCE
# ===========================================================================

class TestDebugReportAcceptance:
    def test_debug_report_shows_constraint_and_score_info(self, berlin_run):
        result = berlin_run["result"]
        for plan in result.geometry_plans[:2]:
            text = debug_geometry_plan(plan)
            assert "Nodes:" in text
            assert "Constraints:" in text
            assert "Reading:" in text
            assert "Solved signature:" in text
            assert plan.structural_geometry_signature in text

    def test_constraint_enforcement_audit(self, berlin_run):
        """Verify the audit table: all HARD constraints in production
        plans have been validated."""
        result = berlin_run["result"]
        for plan in result.geometry_plans:
            assert plan.solver_score["hard_constraint_score"] == 1.0
            hard_constraints = [c for c in plan.constraints
                                if c.strength == ConstraintStrength.HARD]
            assert hard_constraints, \
                f"{plan.beat_id}: no HARD constraints found"


# ===========================================================================
# END-TO-END NOVELTY (TASK 2B)
# ===========================================================================

class TestEndToEndNovelty:
    def test_e2e_novelty_through_runner(self, tmp_path):
        """Exercise the real integration path:
        solver → runner → geometry history → next solver"""
        result = run_berlin(tmp_path / "artifacts")
        assert result.ok
        # Build history from structural signatures as the runner does
        structural_sigs = [p.structural_geometry_signature
                           for p in result.geometry_plans]
        # Verify that later plans carry earlier structural sigs in context
        for i, plan in enumerate(result.geometry_plans):
            if i == 0:
                assert plan.recent_geometry_context == []
            else:
                # Context should contain structural sigs from prior beats
                assert len(plan.recent_geometry_context) == min(i, 5)
                assert plan.recent_geometry_context == \
                    structural_sigs[max(0, i - 5):i]


# ===========================================================================
# DETERMINISM
# ===========================================================================

class TestDeterminism:
    def test_identical_runs_produce_same_geometry(self, tmp_path):
        first = run_berlin(tmp_path / "artifacts")
        second = run_berlin(tmp_path / "artifacts")
        assert first.geometry_plans[0].to_dict() == \
            second.geometry_plans[0].to_dict()
        assert first.geometry_plans[0].structural_geometry_signature == \
            second.geometry_plans[0].structural_geometry_signature

