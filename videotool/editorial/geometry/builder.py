"""Deterministic semantic graph and unresolved geometry plan generation."""
from __future__ import annotations

from collections import defaultdict

from videotool.domain.assets import AssetRequirement, MediaAsset
from videotool.domain.composition import LayerType, VisualComposition
from videotool.domain.geometry import (CanvasSpec, ConstraintStrength,
                                       ConstraintType, GeometryConstraint,
                                       GeometryHistory, GeometryPlan,
                                       VisualHierarchy, VisualNode, VisualRole)
from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.timing import SemanticAnchor, TimingBinding

from .planner import SemanticNodePlanner
from .policy import GeometryPolicy

SEMANTIC_GEOMETRY_VERSION = 2
GEOMETRY_POLICY_VERSION = 1
GEOMETRY_SIGNATURE_VERSION = 2


def semantic_geometry_signature(plan: GeometryPlan) -> str:
    """Canonical topology signature; intentionally excludes IDs and topic text."""
    node_by_id = {node.node_id: node for node in plan.nodes}
    ordered_ids = list(plan.hierarchy.reading_order)
    ordered_ids.extend(node.node_id for node in plan.nodes
                       if node.node_id not in ordered_ids)
    role_ordinals: dict[str, int] = defaultdict(int)
    labels: dict[str, str] = {}
    ordered_roles: list[str] = []
    for node_id in ordered_ids:
        role = node_by_id[node_id].role.value
        labels[node_id] = f"{role}#{role_ordinals[role]}"
        role_ordinals[role] += 1
        ordered_roles.append(role)
    primary = node_by_id.get(plan.hierarchy.primary_node_id)
    primary_role = primary.role.value if primary else "none"
    region = (primary.preferred_regions[0].value
              if primary and primary.preferred_regions else "none")
    groups = sorted(
        f"{group.semantic_role}:[{','.join(labels[node_id] for node_id in group.node_ids)}]"
        for group in plan.groups)
    edges = sorted(
        f"{labels[edge.source_node_id]}->{edge.relationship_type.value}->"
        f"{labels[edge.target_node_id]}:directed={str(edge.directed).lower()}"
        for edge in plan.edges)
    regions = [
        f"{labels[node_id]}@"
        f"{'+'.join(region.value for region in node_by_id[node_id].preferred_regions) or 'none'}"
        for node_id in ordered_ids]
    return (f"v{GEOMETRY_SIGNATURE_VERSION}|{plan.visual_family}|"
            f"primary={primary_role}@{region}|"
            f"hierarchy=[{','.join(ordered_roles)}]|"
            f"regions=[{','.join(regions)}]|"
            f"groups=[{';'.join(groups) or 'none'}]|"
            f"edges=[{';'.join(edges) or 'none'}]|"
            f"reading={plan.hierarchy.reading_direction}")


def geometry_input_projection(compositions: list[VisualComposition],
                              assets: list[MediaAsset], strategy_plan,
                              art_direction, anchors: list[SemanticAnchor],
                              bindings: list[TimingBinding],
                              requirements: list[AssetRequirement] | None = None
                              ) -> dict:
    """Timing-independent semantic inputs plus optional compatibility metadata."""
    return {
        "compatibility_compositions": [{
            "composition_id": comp.composition_id,
            "beat_id": comp.beat_id,
            "visual_family": comp.visual_family,
            "layers": [{
                "id": layer.id, "type": layer.type.value,
                "role": layer.role, "asset_id": layer.asset_id,
                "semantic_refs": layer.semantic_refs,
            } for layer in comp.layers],
        } for comp in compositions],
        "assets": sorted([{
            "asset_id": asset.asset_id,
            "requirement_id": asset.requirement_id,
            "kind": asset.kind, "width": asset.width, "height": asset.height,
            "is_placeholder": asset.is_placeholder,
        } for asset in assets], key=lambda item: item["asset_id"]),
        "requirements": sorted([{
            "requirement_id": item.requirement_id, "beat_id": item.beat_id,
            "kind": item.kind, "strength": item.strength,
            "entities": item.entities, "description": item.description,
        } for item in (requirements or [])], key=lambda item: item["requirement_id"]),
        "strategy": [{
            "beat_id": record.beat_id,
            "selected_strategy": record.selected_strategy,
            "visual_family": record.visual_family,
        } for record in strategy_plan],
        "art_geometry": {
            "geometry": list(art_direction.geometry),
            "typography_character": list(art_direction.typography_character),
        },
        "anchors": [{
            "anchor_id": anchor.anchor_id, "beat_id": anchor.beat_id,
            "anchor_type": anchor.anchor_type.value, "text": anchor.text,
            "normalized_terms": anchor.normalized_terms,
            "entity_ids": anchor.entity_ids,
            "location_ids": anchor.location_ids,
            "event_ids": anchor.event_ids,
            "relationship_ids": anchor.relationship_ids,
        } for anchor in anchors],
        "bindings": [{
            "composition_id": binding.composition_id,
            "layer_id": binding.layer_id,
            "semantic_refs": binding.semantic_refs,
            "anchor_id": binding.anchor_id,
        } for binding in bindings],
    }


class SemanticGeometryBuilder:
    def __init__(self, policy: GeometryPolicy | None = None):
        self.policy = policy or GeometryPolicy()
        self.node_planner = SemanticNodePlanner(self.policy)

    def build_plan(self, beat: SemanticBeat, visual_family: str,
                   selected_strategy: str, assets: list[MediaAsset],
                   requirements: list[AssetRequirement], art_direction,
                   anchors: list[SemanticAnchor],
                   composition: VisualComposition | None = None,
                   bindings: list[TimingBinding] | None = None,
                   recent_context: list[str] | None = None) -> GeometryPlan:
        semantic = self.node_planner.plan(
            beat, visual_family, selected_strategy, assets, requirements,
            art_direction, anchors)
        nodes = {node.node_id: node for node in semantic.nodes}
        self._map_bootstrap_metadata(nodes, composition, bindings or [], anchors)
        context_constraints = list(semantic.constraints)
        self._common_constraints(beat.beat_id, nodes.values(),
                                 context_constraints)
        reading_order = list(dict.fromkeys(
            node_id for node_id in semantic.reading_order if node_id in nodes))
        if not reading_order:
            reading_order = list(nodes)[:1]
        for priority, node_id in enumerate(reading_order):
            nodes[node_id].reading_priority = priority
        primary = reading_order[0]
        secondary = [node_id for node_id in reading_order[1:]
                     if nodes[node_id].importance >= 0.6]
        tertiary = [node_id for node_id in reading_order[1:]
                    if node_id not in secondary]
        direction = self.policy.reading_direction(
            beat, visual_family, art_direction.geometry, reading_order,
            list(recent_context or []))
        hierarchy = VisualHierarchy(
            primary_node_id=primary, secondary_node_ids=secondary,
            tertiary_node_ids=tertiary, reading_order=reading_order,
            reading_direction=direction)
        if len(reading_order) > 1:
            context_constraints.append(GeometryConstraint(
                constraint_id=f"gc:{beat.beat_id}:hierarchy",
                constraint_type=ConstraintType.READING_ORDER,
                node_ids=reading_order, strength=ConstraintStrength.STRONG,
                weight=self.policy.strong_weight,
                parameters={"direction": direction},
                reason="Reading order follows semantic hierarchy."))
        plan = GeometryPlan(
            beat_id=beat.beat_id, visual_family=visual_family,
            nodes=list(nodes.values()), groups=semantic.groups,
            edges=semantic.edges, hierarchy=hierarchy,
            constraints=context_constraints, canvas=CanvasSpec(),
            safe_zones=self.policy.safe_zones(),
            style_hints=self.policy.style_hints(
                beat.information_density, art_direction.geometry, direction),
            semantic_geometry_signature="",
            recent_geometry_context=list(recent_context or []))
        plan.semantic_geometry_signature = semantic_geometry_signature(plan)
        return plan

    def fallback_plan(self, beat: SemanticBeat, visual_family: str,
                      reason: str, recent_context: list[str] | None = None
                      ) -> GeometryPlan:
        node = VisualNode(
            node_id=f"geometry_fallback:{beat.beat_id}:hero",
            beat_id=beat.beat_id, role=VisualRole.HERO,
            semantic_refs=(beat.entities[:1] or beat.locations[:1]
                           or beat.events[:1]), importance=0.95, salience=0.90,
            preferred_regions=self.policy.regions(VisualRole.HERO),
            min_width=0.30, min_height=0.28, can_crop=False,
            reading_priority=0, source_layer_id=None)
        direction = "OVERLAY_HIERARCHY"
        constraints = [
            GeometryConstraint(
                f"gc:{beat.beat_id}:fallback:inside",
                ConstraintType.INSIDE_CANVAS, [node.node_id],
                ConstraintStrength.HARD, self.policy.hard_weight, {},
                "Fallback hero must remain inside the normalized canvas."),
            GeometryConstraint(
                f"gc:{beat.beat_id}:fallback:safe",
                ConstraintType.OUTSIDE_SAFE_ZONE, [node.node_id],
                ConstraintStrength.HARD, self.policy.hard_weight,
                {"safe_zone_id": "subtitle_safe_zone"},
                "Fallback critical content must not occupy subtitle space."),
        ]
        plan = GeometryPlan(
            beat.beat_id, visual_family, [node], [], [],
            VisualHierarchy(node.node_id, reading_order=[node.node_id],
                            reading_direction=direction),
            constraints, CanvasSpec(), self.policy.safe_zones(),
            self.policy.style_hints(beat.information_density, [], direction), "",
            list(recent_context or []), True, reason)
        plan.semantic_geometry_signature = (semantic_geometry_signature(plan)
                                            + "|fallback=true")
        return plan

    def _map_bootstrap_metadata(self, nodes: dict[str, VisualNode],
                                composition: VisualComposition | None,
                                bindings: list[TimingBinding],
                                anchors: list[SemanticAnchor]) -> None:
        if composition is None:
            return
        binding_by_layer = {item.layer_id: item for item in bindings
                            if item.composition_id == composition.composition_id}
        anchor_by_id = {anchor.anchor_id: anchor for anchor in anchors}
        unused = list(composition.layers)
        for node in nodes.values():
            candidates = [layer for layer in unused
                          if node.asset_id and layer.asset_id == node.asset_id]
            if not candidates:
                candidates = [layer for layer in unused
                              if set(node.semantic_refs) & set(layer.semantic_refs)]
            if not candidates:
                candidates = [layer for layer in unused
                              if self._compatible_layer(node, layer.type)]
            if not candidates:
                continue
            layer = candidates[0]
            unused.remove(layer)
            node.source_layer_id = layer.id
            binding = binding_by_layer.get(layer.id)
            if binding and binding.anchor_id in anchor_by_id:
                node.timing_anchor_id = binding.anchor_id

    @staticmethod
    def _compatible_layer(node: VisualNode, layer_type: LayerType) -> bool:
        if node.role == VisualRole.MAP:
            return layer_type == LayerType.MAP
        if node.role == VisualRole.DOCUMENT:
            return layer_type == LayerType.DOCUMENT
        if node.role in {VisualRole.PORTRAIT, VisualRole.ARCHIVAL_IMAGE,
                         VisualRole.HERO} and node.text_role is None:
            return layer_type in {LayerType.IMAGE, LayerType.VIDEO}
        if node.text_role is not None:
            return layer_type in {LayerType.TEXT, LayerType.LABEL}
        if node.role == VisualRole.CONNECTOR_ENDPOINT:
            return layer_type in {LayerType.ICON, LayerType.SHAPE}
        return False

    def _common_constraints(self, beat_id: str, nodes,
                            constraints: list[GeometryConstraint]) -> None:
        def add(kind, node_ids, strength, reason, parameters=None):
            constraints.append(GeometryConstraint(
                constraint_id=f"gc:{beat_id}:common:{len(constraints):03d}",
                constraint_type=kind, node_ids=node_ids, strength=strength,
                weight=self.policy.strength_weight(strength),
                parameters=parameters or {}, reason=reason))
        for node in nodes:
            add(ConstraintType.INSIDE_CANVAS, [node.node_id],
                ConstraintStrength.HARD,
                "Every semantic node remains inside the normalized canvas.")
            add(ConstraintType.MIN_SIZE, [node.node_id], ConstraintStrength.HARD,
                "Semantic role supplies a minimum readable size.",
                {"min_width": node.min_width, "min_height": node.min_height})
            if node.importance >= 0.45:
                add(ConstraintType.OUTSIDE_SAFE_ZONE, [node.node_id],
                    ConstraintStrength.HARD,
                    "Important content cannot occupy the subtitle safe zone.",
                    {"safe_zone_id": "subtitle_safe_zone"})
            if node.preferred_regions:
                add(ConstraintType.PREFER_REGION, [node.node_id],
                    ConstraintStrength.MEDIUM,
                    "Semantic role supplies a soft region preference.",
                    {"regions": [region.value
                                 for region in node.preferred_regions]})
            if node.preferred_aspect_ratio is not None:
                add(ConstraintType.ASPECT_RATIO, [node.node_id],
                    ConstraintStrength.STRONG,
                    "Resolved media supplies its natural aspect ratio.",
                    {"ratio": node.preferred_aspect_ratio,
                     "crop_allowed": node.can_crop})


def debug_geometry_plan(plan: GeometryPlan) -> str:
    lines = [f"Beat {plan.beat_id} — {plan.visual_family}", "", "Nodes:"]
    for node in plan.nodes:
        lines.append(f"- {node.node_id} [{node.role.value}] "
                     f"importance={node.importance:.2f} salience={node.salience:.2f}")
    lines.extend(["", "Groups:"])
    lines.extend(f"- {group.group_id} ({', '.join(group.node_ids)})"
                 for group in plan.groups)
    lines.extend(["", "Edges:"])
    lines.extend(f"- {edge.source_node_id} -> {edge.target_node_id} "
                 f"[{edge.relationship_type.value}]" for edge in plan.edges)
    lines.extend(["", "Constraints:"])
    lines.extend(f"- {item.constraint_type.value} ({', '.join(item.node_ids)}) "
                 f"[{item.strength.value}]" for item in plan.constraints)
    lines.extend(["", f"Reading: {' -> '.join(plan.hierarchy.reading_order)} "
                  f"({plan.hierarchy.reading_direction})", "",
                  f"Signature: {plan.semantic_geometry_signature}"])
    return "\n".join(lines)
