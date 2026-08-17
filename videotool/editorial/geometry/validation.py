"""Semantic and referential validation for unresolved GeometryPlan graphs."""
from __future__ import annotations

from videotool.domain.geometry import (ConstraintType, EdgeType, GeometryPlan,
                                       VisualRole)
from videotool.editorial.validation import ValidationReport


def validate_geometry_plan(plan: GeometryPlan,
                           known_asset_ids: set[str] | None = None
                           ) -> ValidationReport:
    report = ValidationReport()
    node_ids = [node.node_id for node in plan.nodes]
    known_nodes = set(node_ids)
    if not plan.nodes:
        report.error(f"{plan.beat_id}: geometry has no nodes")
        return report
    if len(known_nodes) != len(node_ids):
        report.error(f"{plan.beat_id}: duplicate visual node id")

    for node in plan.nodes:
        if not 0.0 <= node.importance <= 1.0:
            report.error(f"{node.node_id}: importance outside [0,1]")
        if not 0.0 <= node.salience <= 1.0:
            report.error(f"{node.node_id}: salience outside [0,1]")
        if not 0.0 < node.min_width <= 1.0 \
                or not 0.0 < node.min_height <= 1.0:
            report.error(f"{node.node_id}: invalid minimum dimensions")
        if node.preferred_aspect_ratio is not None \
                and node.preferred_aspect_ratio <= 0:
            report.error(f"{node.node_id}: invalid aspect ratio")
        if known_asset_ids is not None and node.asset_id \
                and node.asset_id not in known_asset_ids:
            report.error(f"{node.node_id}: references unknown asset {node.asset_id}")
        if node.text_role is not None and (
                node.estimated_width is None or node.estimated_height is None
                or node.estimated_width <= 0 or node.estimated_height <= 0):
            report.error(f"{node.node_id}: text geometry estimate missing")

    if plan.canvas.width_norm != 1.0 or plan.canvas.height_norm != 1.0 \
            or plan.canvas.aspect_ratio <= 0:
        report.error(f"{plan.beat_id}: invalid normalized canvas")
    safe_zone_ids: set[str] = set()
    for zone in plan.safe_zones:
        if zone.zone_id in safe_zone_ids:
            report.error(f"{plan.beat_id}: duplicate safe zone {zone.zone_id}")
        safe_zone_ids.add(zone.zone_id)
        bounds = zone.bounds
        if (bounds.x < 0 or bounds.y < 0 or bounds.width <= 0
                or bounds.height <= 0
                or bounds.x + bounds.width > plan.canvas.width_norm + 1e-6
                or bounds.y + bounds.height > plan.canvas.height_norm + 1e-6):
            report.error(f"{zone.zone_id}: safe zone outside canvas")
    for required in ("subtitle_safe_zone", "edge_safe_zone", "title_safe_zone"):
        if required not in safe_zone_ids:
            report.error(f"{plan.beat_id}: missing {required}")

    group_ids: set[str] = set()
    for group in plan.groups:
        if group.group_id in group_ids:
            report.error(f"{plan.beat_id}: duplicate group {group.group_id}")
        group_ids.add(group.group_id)
        if not group.node_ids or any(node_id not in known_nodes
                                     for node_id in group.node_ids):
            report.error(f"{group.group_id}: unknown or empty group membership")
        if not 0 <= group.importance <= 1:
            report.error(f"{group.group_id}: importance outside [0,1]")
        if not group.reason:
            report.error(f"{group.group_id}: missing semantic reason")

    edge_ids: set[str] = set()
    for edge in plan.edges:
        if edge.edge_id in edge_ids:
            report.error(f"{plan.beat_id}: duplicate edge {edge.edge_id}")
        edge_ids.add(edge.edge_id)
        if edge.source_node_id not in known_nodes \
                or edge.target_node_id not in known_nodes:
            report.error(f"{edge.edge_id}: edge references unknown node")
        if edge.source_node_id == edge.target_node_id:
            report.error(f"{edge.edge_id}: impossible self-edge")
        if not 0 <= edge.importance <= 1:
            report.error(f"{edge.edge_id}: importance outside [0,1]")
        if not edge.reason:
            report.error(f"{edge.edge_id}: missing semantic reason")

    constraint_ids: set[str] = set()
    contained_pairs: set[tuple[str, str]] = set()
    connected_pairs: set[frozenset[str]] = set()
    for constraint in plan.constraints:
        if constraint.constraint_id in constraint_ids:
            report.error(f"{plan.beat_id}: duplicate constraint "
                         f"{constraint.constraint_id}")
        constraint_ids.add(constraint.constraint_id)
        if not constraint.node_ids or any(node_id not in known_nodes
                                          for node_id in constraint.node_ids):
            report.error(f"{constraint.constraint_id}: references unknown node")
        if not 0.0 <= constraint.weight <= 1.0:
            report.error(f"{constraint.constraint_id}: weight outside [0,1]")
        if not constraint.reason:
            report.error(f"{constraint.constraint_id}: missing reason")
        if constraint.constraint_type == ConstraintType.OUTSIDE_SAFE_ZONE:
            zone_id = constraint.parameters.get("safe_zone_id")
            if zone_id not in safe_zone_ids:
                report.error(f"{constraint.constraint_id}: unknown safe zone")
        if constraint.constraint_type == ConstraintType.CONTAINED_IN:
            if len(constraint.node_ids) != 2:
                report.error(f"{constraint.constraint_id}: containment needs child and parent")
            else:
                child_id, parent_id = constraint.node_ids
                contained_pairs.add((child_id, parent_id))
                child = next((node for node in plan.nodes
                              if node.node_id == child_id), None)
                parent = next((node for node in plan.nodes
                               if node.node_id == parent_id), None)
                if child and parent and child.role == VisualRole.QUOTE \
                        and parent.media_kind != "document" \
                        and parent.role != VisualRole.DOCUMENT:
                    report.error(f"{constraint.constraint_id}: quote parent is not a document")
        if constraint.constraint_type == ConstraintType.CONNECT:
            if len(constraint.node_ids) < 2:
                report.error(f"{constraint.constraint_id}: connect needs endpoints")
            else:
                connected_pairs.add(frozenset(constraint.node_ids[:2]))

    hierarchy_ids = ([plan.hierarchy.primary_node_id]
                     + plan.hierarchy.secondary_node_ids
                     + plan.hierarchy.tertiary_node_ids
                     + plan.hierarchy.reading_order)
    if any(node_id not in known_nodes for node_id in hierarchy_ids):
        report.error(f"{plan.beat_id}: hierarchy references unknown node")
    if len(plan.hierarchy.reading_order) != \
            len(set(plan.hierarchy.reading_order)):
        report.error(f"{plan.beat_id}: duplicate node in reading order")
    if not plan.hierarchy.reading_order:
        report.error(f"{plan.beat_id}: empty reading order")
    if plan.hierarchy.reading_direction != \
            plan.style_hints.preferred_reading_direction:
        report.error(f"{plan.beat_id}: hierarchy and style reading direction disagree")

    node_by_id = {node.node_id: node for node in plan.nodes}
    if plan.visual_family == "geographic_map":
        maps = [node for node in plan.nodes
                if node.role == VisualRole.MAP or node.media_kind == "map"]
        if maps:
            overlay_ids = {node.node_id for node in plan.nodes
                           if node.role == VisualRole.CONNECTOR_ENDPOINT}
            for overlay_id in overlay_ids:
                if not any(child == overlay_id and
                           node_by_id[parent].node_id in {m.node_id for m in maps}
                           for child, parent in contained_pairs):
                    report.error(f"{overlay_id}: map marker is not contained in a map")
        for edge in plan.edges:
            if edge.relationship_type == EdgeType.ROUTE_TO \
                    and frozenset((edge.source_node_id,
                                   edge.target_node_id)) not in connected_pairs:
                report.error(f"{edge.edge_id}: route has no CONNECT constraint")
    if plan.visual_family == "document_evidence":
        documents = {node.node_id for node in plan.nodes
                     if node.role == VisualRole.DOCUMENT
                     or node.media_kind == "document"}
        quotes = {node.node_id for node in plan.nodes
                  if node.role == VisualRole.QUOTE}
        if documents:
            for quote_id in quotes:
                if not any(child == quote_id and parent in documents
                           for child, parent in contained_pairs):
                    report.error(f"{quote_id}: document quote is not contained")
    if plan.visual_family == "causal_network" and len(plan.nodes) > 1 \
            and not plan.edges:
        report.error(f"{plan.beat_id}: causal graph has no semantic edge")

    if not plan.semantic_geometry_signature:
        report.error(f"{plan.beat_id}: semantic geometry signature missing")
    return report


def validate_geometry_plans(plans: list[GeometryPlan], beat_ids: set[str],
                            known_asset_ids: set[str]) -> ValidationReport:
    report = ValidationReport()
    owned: dict[str, int] = {}
    for plan in plans:
        owned[plan.beat_id] = owned.get(plan.beat_id, 0) + 1
        if plan.beat_id not in beat_ids:
            report.error(f"geometry plan for unknown beat {plan.beat_id}")
        child = validate_geometry_plan(plan, known_asset_ids)
        report.errors.extend(child.errors)
        report.warnings.extend(child.warnings)
    for beat_id in beat_ids:
        if owned.get(beat_id, 0) != 1:
            report.error(f"{beat_id}: expected exactly one geometry plan")
    return report
