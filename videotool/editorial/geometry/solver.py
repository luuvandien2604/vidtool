"""Deterministic constraint-driven geometry solving for semantic plans."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt

from videotool.domain.geometry import (CanvasRegion, ConstraintStrength,
                                       ConstraintType, GeometryConstraint,
                                       GeometryPlan, NormalizedRect,
                                       SolvedPlacement, VisualNode, VisualRole)

GEOMETRY_SOLVER_VERSION = 2
GEOMETRY_CANDIDATE_VERSION = 1
GEOMETRY_SCORE_VERSION = 2


@dataclass
class GeometryCandidate:
    candidate_id: str
    operator_chain: list[str]
    placements: list[SolvedPlacement]
    score: dict = field(default_factory=dict)
    hard_violations: list[str] = field(default_factory=list)
    structural_signature: str = ""
    explanation: str = ""


class GeometrySolver:
    """Generate, validate and score solved coordinates from semantic topology."""

    def solve(self, plan: GeometryPlan) -> GeometryPlan:
        candidates = self.generate_candidates(plan)
        scored = [self.score_candidate(plan, candidate) for candidate in candidates]
        valid = [item for item in scored if not item.hard_violations]
        selected = max(valid or scored, key=lambda item: item.score["total_score"])
        solved = GeometryPlan.from_dict(plan.to_dict())
        solved.solved_placements = selected.placements
        solved.solver_candidate_count = len(scored)
        solved.solver_score = selected.score
        solved.solver_explanation = selected.explanation
        solved.structural_geometry_signature = selected.structural_signature
        return solved

    def generate_candidates(self, plan: GeometryPlan) -> list[GeometryCandidate]:
        operators = self._operator_chains(plan)
        return [
            GeometryCandidate(
                f"candidate:{plan.beat_id}:{index:02d}", chain,
                self._place(plan, chain))
            for index, chain in enumerate(operators)
        ]

    def score_candidate(self, plan: GeometryPlan,
                        candidate: GeometryCandidate) -> GeometryCandidate:
        candidate.hard_violations = self._hard_violations(plan, candidate)
        candidate.structural_signature = structural_geometry_signature(
            plan, candidate)
        overlap_penalty = self._overlap_penalty(candidate.placements)
        safe_zone_score = 1.0 if not any("safe zone" in item
                                         for item in candidate.hard_violations) else 0.0
        hierarchy_score = self._hierarchy_score(plan, candidate)
        reading_flow_score = self._reading_flow_score(plan, candidate)
        semantic_proximity_score = self._semantic_proximity_score(plan, candidate)
        whitespace_score = max(0.0, 1.0 - sum(
            p.bounds.width * p.bounds.height for p in candidate.placements))
        balance_score = self._balance_score(candidate.placements)
        salience_score = self._salience_score(plan, candidate)
        novelty_score = self._novelty_score(plan, candidate.structural_signature)
        art_direction_score = self._art_direction_score(plan, candidate)
        hard_constraint_score = 1.0 if not candidate.hard_violations else 0.0
        total = (
            hard_constraint_score * 2.0
            - overlap_penalty * 0.9
            + safe_zone_score * 0.8
            + hierarchy_score * 0.85
            + reading_flow_score * 0.70
            + semantic_proximity_score * 0.65
            + whitespace_score * 0.30
            + balance_score * 0.45
            + salience_score * 0.65
            + novelty_score * 0.55
            + art_direction_score * 0.45
        )
        if candidate.hard_violations:
            total -= 1000.0 + len(candidate.hard_violations)
        candidate.score = {
            "hard_constraint_score": round(hard_constraint_score, 4),
            "overlap_penalty": round(overlap_penalty, 4),
            "safe_zone_score": round(safe_zone_score, 4),
            "hierarchy_score": round(hierarchy_score, 4),
            "reading_flow_score": round(reading_flow_score, 4),
            "semantic_proximity_score": round(semantic_proximity_score, 4),
            "whitespace_score": round(whitespace_score, 4),
            "balance_score": round(balance_score, 4),
            "salience_score": round(salience_score, 4),
            "novelty_score": round(novelty_score, 4),
            "art_direction_score": round(art_direction_score, 4),
            "total_score": round(total, 4),
            "hard_violations": list(candidate.hard_violations),
        }
        candidate.explanation = self._explain(plan, candidate)
        return candidate

    def _operator_chains(self, plan: GeometryPlan) -> list[list[str]]:
        family = plan.visual_family
        if family == "chronological_timeline":
            return [["row", "chronological_spacing"],
                    ["column", "compressed_spacing"],
                    ["row", "region_swap"]]
        if family == "causal_network":
            return [["graph_levels", "edge_attachment"],
                    ["radial_cluster", "edge_attachment"],
                    ["column_flow", "edge_attachment"]]
        if family == "geographic_map":
            return [["map_canvas", "route_endpoints"],
                    ["map_canvas", "clustered_endpoints"]]
        if family == "document_evidence":
            return [["document_anchor", "contained_evidence"],
                    ["document_center", "contained_evidence"]]
        if family == "archival_subject":
            return [["portrait_cluster", "stack_labels"],
                    ["portrait_cluster_mirror", "stack_labels"]]
        if family == "paper_collage_hero":
            return [["collage_hero_layout"], ["collage_hero_layout_insets"]]
        return [["hero_overlay"], ["hero_overlay_asymmetric"]]

    def _place(self, plan: GeometryPlan, chain: list[str]) -> list[SolvedPlacement]:
        nodes = list(plan.nodes)
        if "row" in chain:
            return self._row(plan, nodes, chain)
        if "column" in chain:
            return self._column(plan, nodes, chain)
        if "graph_levels" in chain:
            return self._graph(plan, chain)
        if "radial_cluster" in chain:
            return self._radial(plan, chain)
        if "column_flow" in chain:
            return self._column(plan, nodes, chain)
        if "map_canvas" in chain:
            return self._map(plan, chain)
        if "document_anchor" in chain or "document_center" in chain:
            return self._document(plan, chain)
        if "portrait_cluster" in chain:
            return self._portrait(plan, chain, mirror="mirror" in chain[0])
        if "collage_hero_layout" in chain[0]:
            return self._collage(plan, chain)
        return self._hero(plan, chain)

    def _collage(self, plan: GeometryPlan, chain: list[str]) -> list[SolvedPlacement]:
        placements = []
        for index, node in enumerate(plan.nodes):
            if node.role == VisualRole.HERO:
                placements.append(self._placement(
                    node, 0.05, 0.05, 0.90, 0.74, 0, chain, CanvasRegion.FULL))
            elif node.role in {VisualRole.MAP, VisualRole.DOCUMENT, VisualRole.SUPPORT}:
                placements.append(self._placement(
                    node, 0.60, 0.08, 0.34, 0.36, 1, chain, CanvasRegion.TOP_RIGHT))
            elif node.role in {VisualRole.DATE, VisualRole.DATA}:
                placements.append(self._placement(
                    node, 0.04, 0.68, 0.32, 0.10, 2, chain, CanvasRegion.BOTTOM_LEFT))
            elif node.role == VisualRole.QUOTE:
                placements.append(self._placement(
                    node, 0.22, 0.72, 0.58, 0.09, 3, chain, CanvasRegion.BOTTOM))
            else:
                placements.append(self._placement(
                    node, 0.04, 0.12 + 0.10 * index, 0.30, 0.10, index + 2, chain, CanvasRegion.LEFT))
        return self._ensure_all(plan, placements, chain)

    def _row(self, plan, nodes, chain) -> list[SolvedPlacement]:
        count = max(1, len(nodes))
        y = 0.38
        gap = 0.04
        width = min(0.22, max(0.08, (0.88 - gap * (count - 1)) / count))
        start = (1.0 - (width * count + gap * (count - 1))) / 2
        placements = []
        for index, node in enumerate(nodes):
            placements.append(self._placement(
                node, start + index * (width + gap), y,
                max(width, node.min_width), max(0.11, node.min_height),
                index, chain, CanvasRegion.CENTER))
        return placements

    def _column(self, plan, nodes, chain) -> list[SolvedPlacement]:
        count = max(1, len(nodes))
        height = min(0.14, max(0.07, 0.68 / count))
        start = 0.10
        placements = []
        for index, node in enumerate(nodes):
            placements.append(self._placement(
                node, 0.34, start + index * (height + 0.035),
                max(0.28, node.min_width), max(height, node.min_height),
                index, chain, CanvasRegion.CENTER))
        return placements

    def _graph(self, plan, chain) -> list[SolvedPlacement]:
        order = plan.hierarchy.reading_order
        incoming = {node.node_id: 0 for node in plan.nodes}
        outgoing = {node.node_id: 0 for node in plan.nodes}
        for edge in plan.edges:
            outgoing[edge.source_node_id] += 1
            incoming[edge.target_node_id] += 1
        sources = [node_id for node_id in order if incoming.get(node_id, 0) == 0]
        sinks = [node_id for node_id in order if outgoing.get(node_id, 0) == 0]
        middle = [node_id for node_id in order if node_id not in sources + sinks]
        columns = [sources or order[:1], middle, sinks or order[-1:]]
        by_id = {node.node_id: node for node in plan.nodes}
        placements = []
        for col_index, column in enumerate([c for c in columns if c]):
            x = [0.10, 0.38, 0.66][min(col_index, 2)]
            for row_index, node_id in enumerate(column):
                y = 0.24 + row_index * 0.20
                node = by_id[node_id]
                placements.append(self._placement(
                    node, x, y, max(0.20, node.min_width),
                    max(0.10, node.min_height), len(placements), chain,
                    CanvasRegion.LEFT if col_index == 0 else CanvasRegion.RIGHT))
        return placements

    def _radial(self, plan, chain) -> list[SolvedPlacement]:
        order = plan.hierarchy.reading_order
        by_id = {node.node_id: node for node in plan.nodes}
        points = [(0.40, 0.30), (0.18, 0.50), (0.62, 0.50),
                  (0.40, 0.66), (0.12, 0.22), (0.68, 0.22)]
        return [self._placement(
            by_id[node_id], points[index % len(points)][0],
            points[index % len(points)][1], max(0.18, by_id[node_id].min_width),
            max(0.09, by_id[node_id].min_height), index, chain,
            CanvasRegion.CENTER) for index, node_id in enumerate(order)]

    def _map(self, plan, chain) -> list[SolvedPlacement]:
        placements = []
        endpoints = [n for n in plan.nodes if n.role == VisualRole.CONNECTOR_ENDPOINT]
        for index, node in enumerate(plan.nodes):
            if node.role == VisualRole.MAP:
                placements.append(self._placement(
                    node, 0.08, 0.08, 0.84, 0.66, 0, chain, CanvasRegion.CENTER))
        count = max(1, len(endpoints))
        for index, node in enumerate(endpoints):
            x = 0.18 + (0.62 * index / max(1, count - 1))
            y = 0.34 + (0.10 if index % 2 else -0.04)
            if "clustered" in chain:
                x = 0.40 + index * 0.06
                y = 0.34 + index * 0.04
            placements.append(self._placement(
                node, x, y, max(0.05, node.min_width),
                max(0.05, node.min_height), index + 1, chain,
                CanvasRegion.CENTER))
        return self._ensure_all(plan, placements, chain)

    def _document(self, plan, chain) -> list[SolvedPlacement]:
        placements = []
        centered = "center" in chain[0]
        doc_rect = (0.27, 0.10, 0.46, 0.64) if centered else (0.50, 0.08, 0.38, 0.66)
        for index, node in enumerate(plan.nodes):
            if node.role == VisualRole.DOCUMENT:
                placements.append(self._placement(node, *doc_rect, index, chain,
                                                  CanvasRegion.RIGHT))
            elif node.role == VisualRole.QUOTE:
                x = doc_rect[0] + 0.05
                y = doc_rect[1] + 0.36
                placements.append(self._placement(
                    node, x, y, min(0.34, doc_rect[2] - 0.10),
                    max(0.12, node.min_height), index, chain,
                    CanvasRegion.RIGHT))
        return self._ensure_all(plan, placements, chain)

    def _portrait(self, plan, chain, mirror: bool) -> list[SolvedPlacement]:
        hero_x = 0.58 if mirror else 0.10
        label_x = 0.12 if mirror else 0.44
        hero_region = CanvasRegion.RIGHT if mirror else CanvasRegion.LEFT
        placements = []
        for index, node in enumerate(plan.nodes):
            if node.role in {VisualRole.PORTRAIT, VisualRole.ARCHIVAL_IMAGE,
                             VisualRole.HERO}:
                placements.append(self._placement(
                    node, hero_x, 0.16, max(0.30, node.min_width),
                    max(0.44, node.min_height), index, chain, hero_region))
            else:
                placements.append(self._placement(
                    node, label_x, 0.26 + 0.10 * index,
                    max(0.28, node.min_width), max(0.08, node.min_height),
                    index, chain, CanvasRegion.CENTER))
        return placements

    def _hero(self, plan, chain) -> list[SolvedPlacement]:
        placements = []
        for index, node in enumerate(plan.nodes):
            if index == 0:
                placements.append(self._placement(
                    node, 0.06, 0.06, 0.88, 0.70, index, chain,
                    CanvasRegion.FULL))
            else:
                placements.append(self._placement(
                    node, 0.52 if "asymmetric" in chain[0] else 0.32,
                    0.58, max(0.34, node.min_width),
                    max(0.13, node.min_height), index, chain,
                    CanvasRegion.CENTER))
        return placements

    def _ensure_all(self, plan, placements, chain) -> list[SolvedPlacement]:
        placed = {item.node_id for item in placements}
        for node in plan.nodes:
            if node.node_id not in placed:
                placements.append(self._placement(
                    node, 0.08, 0.12 + 0.10 * len(placements),
                    max(0.18, node.min_width), max(0.08, node.min_height),
                    len(placements), chain, CanvasRegion.LEFT))
        return placements

    def _placement(self, node: VisualNode, x: float, y: float, width: float,
                   height: float, z: int, chain: list[str],
                   region: CanvasRegion) -> SolvedPlacement:
        return SolvedPlacement(
            node.node_id, NormalizedRect(round(x, 4), round(y, 4),
                                         round(width, 4), round(height, 4)),
            z, "+".join(chain), region,
            crop_loss=0.0 if not node.can_crop else round(max(0.0, min(0.18,
                abs((node.preferred_aspect_ratio or width / height)
                    - (width / height)) / 10)), 4),
            alignment=("center" if region in {CanvasRegion.CENTER,
                                              CanvasRegion.FULL} else "edge"))

    def _hard_violations(self, plan: GeometryPlan,
                         candidate: GeometryCandidate) -> list[str]:
        placements = {item.node_id: item for item in candidate.placements}
        violations: list[str] = []
        node_by_id = {node.node_id: node for node in plan.nodes}
        if set(placements) != {node.node_id for node in plan.nodes}:
            violations.append("missing solved placement")
        for node in plan.nodes:
            placement = placements.get(node.node_id)
            if not placement:
                continue
            rect = placement.bounds
            if rect.x < 0 or rect.y < 0 or rect.x + rect.width > 1 \
                    or rect.y + rect.height > 1:
                violations.append(f"{node.node_id}: outside canvas")
            if rect.width + 1e-6 < node.min_width \
                    or rect.height + 1e-6 < node.min_height:
                violations.append(f"{node.node_id}: below minimum size")
        for constraint in plan.constraints:
            if constraint.strength != ConstraintStrength.HARD:
                continue
            if constraint.constraint_type in {ConstraintType.OUTSIDE_SAFE_ZONE,
                                              ConstraintType.SUBTITLE_EXCLUSION}:
                zone = self._safe_zone(plan, constraint.parameters.get("safe_zone_id",
                                                                        "subtitle_safe_zone"))
                for node_id in constraint.node_ids:
                    if node_id in placements and zone and self._intersects(
                                                 placements[node_id].bounds,
                                                 zone.bounds):
                        violations.append(f"{node_id}: intersects safe zone")
            if constraint.constraint_type == ConstraintType.NO_OVERLAP:
                for left_id, right_id in _pairs(constraint.node_ids):
                    if left_id in placements and right_id in placements \
                            and self._intersects(placements[left_id].bounds,
                                                 placements[right_id].bounds):
                        violations.append(f"{left_id}/{right_id}: overlap")
            if constraint.constraint_type == ConstraintType.CONTAINED_IN \
                    and len(constraint.node_ids) == 2:
                child, parent = constraint.node_ids
                if child in placements and parent in placements \
                        and not self._contains(placements[parent].bounds,
                                               placements[child].bounds):
                    violations.append(f"{child}: not contained in {parent}")
            # -- ASPECT_RATIO ------------------------------------------------
            if constraint.constraint_type == ConstraintType.ASPECT_RATIO:
                ratio = constraint.parameters.get("ratio")
                crop_allowed = constraint.parameters.get("crop_allowed", True)
                tolerance = 0.15 if crop_allowed else 0.05
                for node_id in constraint.node_ids:
                    if node_id not in placements or ratio is None:
                        continue
                    rect = placements[node_id].bounds
                    if rect.height < 1e-9:
                        violations.append(f"{node_id}: degenerate height")
                        continue
                    actual = rect.width / rect.height
                    if abs(actual - ratio) / max(ratio, 1e-9) > tolerance:
                        violations.append(
                            f"{node_id}: aspect ratio {actual:.3f} "
                            f"violates {ratio:.3f} (tol={tolerance})")
            # -- CONNECT (graph-level + basic geometry) ----------------------
            if constraint.constraint_type == ConstraintType.CONNECT \
                    and len(constraint.node_ids) >= 2:
                src_id, tgt_id = constraint.node_ids[0], constraint.node_ids[1]
                if src_id not in placements:
                    violations.append(f"{src_id}: CONNECT source missing")
                elif tgt_id not in placements:
                    violations.append(f"{tgt_id}: CONNECT target missing")
                else:
                    sr = placements[src_id].bounds
                    tr = placements[tgt_id].bounds
                    # both placements must be finite
                    if not all(_is_finite(v) for v in
                               (sr.x, sr.y, sr.width, sr.height,
                                tr.x, tr.y, tr.width, tr.height)):
                        violations.append(
                            f"{src_id}/{tgt_id}: CONNECT non-finite placement")
                    elif self._distance(sr, tr) < 1e-9:
                        violations.append(
                            f"{src_id}/{tgt_id}: CONNECT zero distance")
            # -- READING_ORDER (declared semantic order) ---------------------
            if constraint.constraint_type == ConstraintType.READING_ORDER:
                direction = constraint.parameters.get("direction", "")
                # Use the declared order from the constraint node_ids list.
                # Never derive order from positions then validate that.
                ordered = [nid for nid in constraint.node_ids
                           if nid in placements]
                if len(ordered) >= 2:
                    violations.extend(
                        _reading_order_violations(ordered, direction,
                                                  placements))
            # -- ORDER_LEFT_TO_RIGHT ----------------------------------------
            if constraint.constraint_type == ConstraintType.ORDER_LEFT_TO_RIGHT:
                ordered = [nid for nid in constraint.node_ids
                           if nid in placements]
                for i in range(len(ordered) - 1):
                    ax = self._center(placements[ordered[i]].bounds)[0]
                    bx = self._center(placements[ordered[i + 1]].bounds)[0]
                    if ax > bx + 0.01:
                        violations.append(
                            f"{ordered[i]}/{ordered[i+1]}: "
                            f"ORDER_LEFT_TO_RIGHT violated")
            # -- ORDER_TOP_TO_BOTTOM ----------------------------------------
            if constraint.constraint_type == ConstraintType.ORDER_TOP_TO_BOTTOM:
                ordered = [nid for nid in constraint.node_ids
                           if nid in placements]
                for i in range(len(ordered) - 1):
                    ay = self._center(placements[ordered[i]].bounds)[1]
                    by = self._center(placements[ordered[i + 1]].bounds)[1]
                    if ay > by + 0.01:
                        violations.append(
                            f"{ordered[i]}/{ordered[i+1]}: "
                            f"ORDER_TOP_TO_BOTTOM violated")
            # -- ALIGN -------------------------------------------------------
            if constraint.constraint_type == ConstraintType.ALIGN \
                    and len(constraint.node_ids) >= 2:
                axis = constraint.parameters.get("axis", "horizontal")
                anchor = constraint.parameters.get("anchor", "center")
                tol = constraint.parameters.get("tolerance", 0.03)
                vals = []
                for nid in constraint.node_ids:
                    if nid not in placements:
                        continue
                    r = placements[nid].bounds
                    if axis == "horizontal":
                        if anchor == "top":
                            vals.append((nid, r.y))
                        elif anchor == "bottom":
                            vals.append((nid, r.y + r.height))
                        else:
                            vals.append((nid, r.y + r.height / 2))
                    else:
                        if anchor == "left":
                            vals.append((nid, r.x))
                        elif anchor == "right":
                            vals.append((nid, r.x + r.width))
                        else:
                            vals.append((nid, r.x + r.width / 2))
                if len(vals) >= 2:
                    ref = vals[0][1]
                    for nid, v in vals[1:]:
                        if abs(v - ref) > tol:
                            violations.append(
                                f"{nid}: ALIGN {axis}/{anchor} "
                                f"off by {abs(v - ref):.4f}")
            # -- STACK -------------------------------------------------------
            if constraint.constraint_type == ConstraintType.STACK \
                    and len(constraint.node_ids) >= 2:
                axis = constraint.parameters.get("axis", "vertical")
                gap_tol = constraint.parameters.get("gap_tolerance", 0.06)
                ordered = [nid for nid in constraint.node_ids
                           if nid in placements]
                for i in range(len(ordered) - 1):
                    a = placements[ordered[i]].bounds
                    b = placements[ordered[i + 1]].bounds
                    if axis == "vertical":
                        gap = b.y - (a.y + a.height)
                    else:
                        gap = b.x - (a.x + a.width)
                    if gap < -1e-6 or gap > gap_tol:
                        violations.append(
                            f"{ordered[i]}/{ordered[i+1]}: "
                            f"STACK {axis} gap={gap:.4f}")
            # -- MIN_DISTANCE ------------------------------------------------
            if constraint.constraint_type == ConstraintType.MIN_DISTANCE \
                    and len(constraint.node_ids) >= 2:
                min_dist = constraint.parameters.get("min_distance", 0.0)
                for lid, rid in _pairs(constraint.node_ids):
                    if lid in placements and rid in placements:
                        dist = self._distance(placements[lid].bounds,
                                              placements[rid].bounds)
                        if dist + 1e-6 < min_dist:
                            violations.append(
                                f"{lid}/{rid}: MIN_DISTANCE "
                                f"{dist:.4f} < {min_dist:.4f}")
            # -- MAX_SIZE ----------------------------------------------------
            if constraint.constraint_type == ConstraintType.MAX_SIZE:
                max_w = constraint.parameters.get("max_width", 1.0)
                max_h = constraint.parameters.get("max_height", 1.0)
                for nid in constraint.node_ids:
                    if nid not in placements:
                        continue
                    r = placements[nid].bounds
                    if r.width > max_w + 1e-6 or r.height > max_h + 1e-6:
                        violations.append(
                            f"{nid}: MAX_SIZE {r.width:.4f}x"
                            f"{r.height:.4f} exceeds "
                            f"{max_w:.4f}x{max_h:.4f}")
        return violations

    def _hierarchy_score(self, plan, candidate) -> float:
        by_id = {item.node_id: item for item in candidate.placements}
        primary_placement = by_id.get(plan.hierarchy.primary_node_id)
        if not primary_placement:
            return 0.0
        primary = primary_placement.bounds
        primary_area = primary.width * primary.height
        others = [p.bounds.width * p.bounds.height for p in candidate.placements
                  if p.node_id != plan.hierarchy.primary_node_id]
        return 1.0 if not others or primary_area >= max(others) else 0.35

    def _reading_flow_score(self, plan, candidate) -> float:
        by_id = {item.node_id: item for item in candidate.placements}
        placed_order = [node_id for node_id in plan.hierarchy.reading_order
                        if node_id in by_id]
        if len(placed_order) < 2:
            return 1.0
        centers = [self._center(by_id[node_id].bounds) for node_id in placed_order]
        direction = plan.hierarchy.reading_direction
        if direction in {"LEFT_TO_RIGHT", "CHRONOLOGICAL_HORIZONTAL",
                         "CAUSE_TO_EFFECT", "ROUTE_FLOW"}:
            return sum(centers[i][0] <= centers[i + 1][0] + 0.02
                       for i in range(len(centers) - 1)) / (len(centers) - 1)
        if direction == "RIGHT_TO_LEFT":
            return sum(centers[i][0] >= centers[i + 1][0] - 0.02
                       for i in range(len(centers) - 1)) / (len(centers) - 1)
        return 1.0

    def _semantic_proximity_score(self, plan, candidate) -> float:
        by_id = {item.node_id: item for item in candidate.placements}
        if not plan.edges and not plan.groups:
            return 1.0
        scores = []
        for edge in plan.edges:
            if edge.source_node_id in by_id and edge.target_node_id in by_id:
                scores.append(1.0 - min(1.0, self._distance(
                    by_id[edge.source_node_id].bounds,
                    by_id[edge.target_node_id].bounds)))
        for group in plan.groups:
            group_rects = [by_id[node_id].bounds for node_id in group.node_ids
                           if node_id in by_id]
            if len(group_rects) >= 2:
                scores.append(1.0 - min(1.0, self._spread(group_rects)))
        return sum(scores) / len(scores) if scores else 1.0

    def _balance_score(self, placements) -> float:
        if not placements:
            return 0.0
        weighted_x = sum(self._center(p.bounds)[0] * p.bounds.width * p.bounds.height
                         for p in placements)
        area = sum(p.bounds.width * p.bounds.height for p in placements)
        return max(0.0, 1.0 - abs((weighted_x / area) - 0.5) * 2)

    def _salience_score(self, plan, candidate) -> float:
        by_id = {item.node_id: item for item in candidate.placements}
        total = sum(node.salience for node in plan.nodes) or 1.0
        return sum(node.salience * by_id[node.node_id].bounds.width
                   * by_id[node.node_id].bounds.height
                   for node in plan.nodes
                   if node.node_id in by_id) / total * 4

    def _novelty_score(self, plan, signature: str) -> float:
        if signature in plan.recent_geometry_context:
            return 0.0
        reading = f"reading={plan.hierarchy.reading_direction}"
        recent_reading = sum(reading in item for item in plan.recent_geometry_context)
        return max(0.35, 1.0 - recent_reading * 0.18)

    def _art_direction_score(self, plan, candidate) -> float:
        if plan.style_hints.asymmetry >= 0.7:
            return 1.0 if "asymmetric" in "+".join(candidate.operator_chain) \
                or "portrait_cluster" in "+".join(candidate.operator_chain) else 0.65
        return 1.0

    def _overlap_penalty(self, placements) -> float:
        return sum(self._intersection_area(a.bounds, b.bounds)
                   for a, b in _placement_pairs(placements))

    def _explain(self, plan, candidate) -> str:
        if candidate.hard_violations:
            return "Rejected because hard constraints failed: " + \
                "; ".join(candidate.hard_violations[:3])
        return (
            f"Selected { '+'.join(candidate.operator_chain) } because "
            f"{plan.hierarchy.reading_direction} flow is preserved, "
            "hard bounds and subtitle-safe constraints pass, related nodes stay "
            f"near their semantic group, and novelty score is "
            f"{candidate.score['novelty_score']:.2f}."
        )

    def _safe_zone(self, plan, zone_id):
        return next((zone for zone in plan.safe_zones
                     if zone.zone_id == zone_id), None)

    @staticmethod
    def _intersects(a: NormalizedRect, b: NormalizedRect) -> bool:
        return not (a.x + a.width <= b.x or b.x + b.width <= a.x
                    or a.y + a.height <= b.y or b.y + b.height <= a.y)

    @staticmethod
    def _contains(parent: NormalizedRect, child: NormalizedRect) -> bool:
        return (child.x >= parent.x and child.y >= parent.y
                and child.x + child.width <= parent.x + parent.width + 1e-6
                and child.y + child.height <= parent.y + parent.height + 1e-6)

    @staticmethod
    def _intersection_area(a: NormalizedRect, b: NormalizedRect) -> float:
        width = max(0.0, min(a.x + a.width, b.x + b.width) - max(a.x, b.x))
        height = max(0.0, min(a.y + a.height, b.y + b.height) - max(a.y, b.y))
        return width * height

    @staticmethod
    def _center(rect: NormalizedRect) -> tuple[float, float]:
        return rect.x + rect.width / 2, rect.y + rect.height / 2

    def _distance(self, a: NormalizedRect, b: NormalizedRect) -> float:
        ax, ay = self._center(a)
        bx, by = self._center(b)
        return sqrt((ax - bx) ** 2 + (ay - by) ** 2)

    def _spread(self, rects: list[NormalizedRect]) -> float:
        centers = [self._center(rect) for rect in rects]
        if len(centers) < 2:
            return 0.0
        return max(sqrt((ax - bx) ** 2 + (ay - by) ** 2)
                   for ax, ay in centers for bx, by in centers)


def structural_geometry_signature(plan: GeometryPlan,
                                  candidate: GeometryCandidate) -> str:
    placements = {item.node_id: item for item in candidate.placements}
    node_by_id = {node.node_id: node for node in plan.nodes}
    order = plan.hierarchy.reading_order or [node.node_id for node in plan.nodes]
    regions = []
    scales = []
    for node_id in order:
        placement = placements.get(node_id)
        node = node_by_id.get(node_id)
        if not placement or not node:
            continue
        area = placement.bounds.width * placement.bounds.height
        scale = "large" if area >= 0.18 else ("medium" if area >= 0.06 else "small")
        regions.append(f"{node.role.value}@{placement.region.value}:{scale}")
        scales.append(scale)
    edge_shape = sorted(
        f"{node_by_id[e.source_node_id].role.value}->{e.relationship_type.value}->"
        f"{node_by_id[e.target_node_id].role.value}" for e in plan.edges
        if e.source_node_id in node_by_id and e.target_node_id in node_by_id)
    hero = placements.get(plan.hierarchy.primary_node_id)
    if hero:
        hero_center = GeometrySolver._center(hero.bounds)
        hero_pos = ("left" if hero_center[0] < 0.4 else
                    "right" if hero_center[0] > 0.6 else "center")
    else:
        hero_pos = "none"
    axis = dominant_axis(candidate.placements)
    alignment = "+".join(sorted({p.alignment or "none"
                                 for p in candidate.placements}))
    return (
        f"solver_v{GEOMETRY_CANDIDATE_VERSION}|family={plan.visual_family}|"
        f"reading={plan.hierarchy.reading_direction}|axis={axis}|"
        f"hero={hero_pos}|alignment={alignment}|"
        f"regions=[{','.join(regions)}]|"
        f"groups={len(plan.groups)}:{','.join(sorted(g.semantic_role for g in plan.groups))}|"
        f"edges=[{';'.join(edge_shape) or 'none'}]"
    )


def dominant_axis(placements: list[SolvedPlacement]) -> str:
    if len(placements) < 2:
        return "single"
    xs = [GeometrySolver._center(p.bounds)[0] for p in placements]
    ys = [GeometrySolver._center(p.bounds)[1] for p in placements]
    return "horizontal" if max(xs) - min(xs) >= max(ys) - min(ys) else "vertical"


def _pairs(items: list[str]):
    for index, left in enumerate(items):
        for right in items[index + 1:]:
            yield left, right


def _placement_pairs(items: list[SolvedPlacement]):
    for index, left in enumerate(items):
        for right in items[index + 1:]:
            yield left, right


def _is_finite(value: float) -> bool:
    import math
    return math.isfinite(value)


def _reading_order_violations(ordered: list[str], direction: str,
                              placements: dict) -> list[str]:
    """Validate declared reading order against final solved positions.

    The ``ordered`` list is the *declared semantic order* from the constraint,
    not an order derived from positions.  This prevents the tautology of
    deriving then validating against the same positions.
    """
    violations: list[str] = []
    horizontal = direction in {
        "LEFT_TO_RIGHT", "CHRONOLOGICAL_HORIZONTAL",
        "CAUSE_TO_EFFECT", "ROUTE_FLOW",
    }
    vertical = direction in {"TOP_TO_BOTTOM"}
    if not horizontal and not vertical:
        return violations
    for i in range(len(ordered) - 1):
        a = placements[ordered[i]].bounds
        b = placements[ordered[i + 1]].bounds
        ax = a.x + a.width / 2
        bx = b.x + b.width / 2
        ay = a.y + a.height / 2
        by = b.y + b.height / 2
        if horizontal and ax > bx + 0.01:
            violations.append(
                f"{ordered[i]}/{ordered[i+1]}: "
                f"READING_ORDER {direction} x-violated")
        if vertical and ay > by + 0.01:
            violations.append(
                f"{ordered[i]}/{ordered[i+1]}: "
                f"READING_ORDER {direction} y-violated")
    return violations
