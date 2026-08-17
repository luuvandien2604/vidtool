"""Deterministic semantic graph + constraint generation for geometry planning."""
from __future__ import annotations

from videotool.domain.assets import MediaAsset
from videotool.domain.composition import LayerType, VisualComposition
from videotool.domain.geometry import (CanvasSpec, ConstraintStrength,
                                       ConstraintType, EdgeType,
                                       GeometryConstraint, GeometryHistory,
                                       GeometryPlan, VisualEdge,
                                       VisualHierarchy, VisualNode, VisualRole)
from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.timing import SemanticAnchor, TimingBinding

from .families import FAMILY_GEOMETRY_BUILDERS, GeometryFamilyContext
from .policy import GeometryPolicy

SEMANTIC_GEOMETRY_VERSION = 1
GEOMETRY_POLICY_VERSION = 1
GEOMETRY_SIGNATURE_VERSION = 1


def _relationship_type(kind: str, label: str) -> EdgeType:
    corpus = f"{kind} {label}".lower()
    if "contrast" in corpus or "oppos" in corpus:
        return EdgeType.CONTRASTS_WITH
    if "route" in corpus:
        return EdgeType.ROUTE_TO
    if "then" in corpus or "next" in corpus:
        return EdgeType.BEFORE
    if "point" in corpus or "lead" in corpus:
        return EdgeType.LEADS_TO
    if "evidence" in corpus or "source" in corpus:
        return EdgeType.EVIDENCE_FOR
    return EdgeType.ASSOCIATED_WITH


def _node_role(layer, asset: MediaAsset | None,
               family: str) -> VisualRole:
    kind = asset.kind if asset else ""
    if layer.type == LayerType.TEXTURE:
        return VisualRole.BACKGROUND
    if family == "full_frame_cinematic" and layer.role == "hero" \
            and layer.type not in {LayerType.TEXT, LayerType.LABEL}:
        return VisualRole.HERO
    if layer.type == LayerType.MAP or kind == "map":
        return VisualRole.MAP
    if layer.type == LayerType.DOCUMENT or kind == "document":
        return VisualRole.DOCUMENT
    if layer.type == LayerType.IMAGE or kind in {"photo", "portrait"}:
        return (VisualRole.PORTRAIT if kind == "portrait"
                else VisualRole.ARCHIVAL_IMAGE)
    if family == "chronological_timeline" and "_ev_" in layer.id:
        return VisualRole.TIMELINE_NODE
    if family == "geographic_map" and layer.type in {
            LayerType.ICON, LayerType.SHAPE}:
        return VisualRole.CONNECTOR_ENDPOINT
    if layer.type in {LayerType.LINE, LayerType.ARROW, LayerType.STRING}:
        return VisualRole.DECORATIVE
    text = layer.text or ""
    if layer.type in {LayerType.TEXT, LayerType.LABEL}:
        if '"' in text or "“" in text or family == "document_evidence" \
                and layer.role in {"hero", "caption"}:
            return VisualRole.QUOTE
        if any(ref.isdigit() for ref in layer.semantic_refs):
            return VisualRole.DATE
        if layer.semantic_refs and family == "geographic_map":
            return VisualRole.LOCATION
        return VisualRole.HERO if layer.role == "hero" else VisualRole.LABEL
    if layer.role == "hero":
        return VisualRole.HERO
    if layer.role in {"support", "document", "map"}:
        return VisualRole.SUPPORT
    return VisualRole.DECORATIVE


def _signature(plan: GeometryPlan) -> str:
    role_counts: dict[str, int] = {}
    for node in plan.nodes:
        role_counts[node.role.value] = role_counts.get(node.role.value, 0) + 1
    roles = ",".join(f"{role}x{count}" for role, count
                     in sorted(role_counts.items()))
    groups = ",".join(sorted(f"{group.semantic_role}:{len(group.node_ids)}"
                             for group in plan.groups)) or "none"
    edges = ",".join(sorted(edge.relationship_type.value
                            for edge in plan.edges)) or "none"
    primary = next((node for node in plan.nodes
                    if node.node_id == plan.hierarchy.primary_node_id), None)
    primary_part = primary.role.value if primary else "none"
    region = (primary.preferred_regions[0].value
              if primary and primary.preferred_regions else "none")
    return (f"v{GEOMETRY_SIGNATURE_VERSION}|{plan.visual_family}|"
            f"primary={primary_part}@{region}|roles={roles}|groups={groups}|"
            f"edges={edges}|reading={plan.hierarchy.reading_direction}")


def geometry_input_projection(compositions: list[VisualComposition],
                              assets: list[MediaAsset], strategy_plan,
                              art_direction, anchors: list[SemanticAnchor],
                              bindings: list[TimingBinding]) -> dict:
    """Only WHERE/WHAT inputs; deliberately excludes every absolute time."""
    return {
        "compositions": [{
            "composition_id": comp.composition_id,
            "beat_id": comp.beat_id,
            "visual_family": comp.visual_family,
            "strategy": comp.strategy,
            "focus_target": comp.focus_target,
            "layers": [{
                "id": layer.id, "type": layer.type.value,
                "role": layer.role, "asset_id": layer.asset_id,
                "text": layer.text, "semantic_refs": layer.semantic_refs,
            } for layer in comp.layers],
            "relationships": [relationship.to_dict()
                              for relationship in comp.relationships],
        } for comp in compositions],
        "assets": sorted([{
            "asset_id": asset.asset_id,
            "requirement_id": asset.requirement_id,
            "kind": asset.kind,
            "width": asset.width,
            "height": asset.height,
            "is_placeholder": asset.is_placeholder,
        } for asset in assets], key=lambda item: item["asset_id"]),
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
            "anchor_id": anchor.anchor_id,
            "beat_id": anchor.beat_id,
            "anchor_type": anchor.anchor_type.value,
            "text": anchor.text,
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

    def build_episode(self, beats: list[SemanticBeat],
                      compositions: list[VisualComposition],
                      assets: list[MediaAsset], art_direction,
                      bindings: list[TimingBinding]) -> list[GeometryPlan]:
        beat_by_id = {beat.beat_id: beat for beat in beats}
        asset_by_id = {asset.asset_id: asset for asset in assets}
        binding_by_layer = {(binding.composition_id, binding.layer_id): binding
                            for binding in bindings}
        history = GeometryHistory(max_window=self.policy.recent_history_window)
        plans: list[GeometryPlan] = []
        for composition in compositions:
            plan = self.build_plan(
                beat_by_id[composition.beat_id], composition, asset_by_id,
                art_direction, binding_by_layer, history.recent())
            plans.append(plan)
            history.record(plan.semantic_geometry_signature)
        return plans

    def build_plan(self, beat: SemanticBeat, composition: VisualComposition,
                   asset_by_id: dict[str, MediaAsset], art_direction,
                   binding_by_layer: dict[tuple[str, str], TimingBinding],
                   recent_context: list[str]) -> GeometryPlan:
        nodes: dict[str, VisualNode] = {}
        for layer in composition.layers:
            asset = asset_by_id.get(layer.asset_id or "")
            role = _node_role(layer, asset, composition.visual_family)
            media_kind = asset.kind if asset else (
                layer.type.value.lower()
                if layer.type in {LayerType.MAP, LayerType.DOCUMENT,
                                  LayerType.IMAGE, LayerType.VIDEO} else "")
            minimum = self.policy.min_size(role)
            crop, rotate = self.policy.crop_policy(role, media_kind)
            text_role = self.policy.text_role(layer.type, role, layer.text or "")
            estimated_width = estimated_height = text_density = None
            max_lines = None
            if text_role is not None:
                (estimated_width, estimated_height, text_density,
                 max_lines) = self.policy.measure_text(layer.text or "", text_role)
            binding = binding_by_layer.get((composition.composition_id, layer.id))
            ratio = (round(asset.width / asset.height, 5)
                     if asset and asset.width > 0 and asset.height > 0 else None)
            importance = self.policy.importance(role)
            salience = self.policy.salience(role)
            if layer.id == composition.focus_target:
                importance = max(importance, 0.95)
                salience = max(salience, 0.90)
            nodes[layer.id] = VisualNode(
                node_id=layer.id, beat_id=beat.beat_id, role=role,
                semantic_refs=list(layer.semantic_refs),
                asset_id=layer.asset_id, media_kind=media_kind,
                importance=importance, salience=salience,
                preferred_regions=self.policy.regions(role),
                min_width=minimum[0], min_height=minimum[1],
                preferred_aspect_ratio=ratio, can_crop=crop,
                can_scale=True, can_rotate=rotate,
                text_density=text_density or 0.0, reading_priority=0,
                timing_anchor_id=binding.anchor_id if binding else None,
                text_role=text_role, estimated_width=estimated_width,
                estimated_height=estimated_height, max_lines=max_lines,
                source_layer_id=layer.id)

        context = GeometryFamilyContext(
            beat=beat, composition=composition, nodes=nodes,
            policy=self.policy)
        self._common_constraints(context)
        self._composition_edges(context)
        adapter = FAMILY_GEOMETRY_BUILDERS.get(composition.visual_family)
        if adapter is None:
            raise ValueError(f"no geometry adapter for {composition.visual_family}")
        reading_order = adapter.build(context)
        semantic_nodes = [node.node_id for node in nodes.values()
                          if node.role not in {VisualRole.BACKGROUND,
                                               VisualRole.DECORATIVE}]
        reading_order = list(dict.fromkeys(
            node_id for node_id in reading_order + semantic_nodes
            if node_id in nodes))
        if not reading_order:
            reading_order = list(nodes)[:1]
        for priority, node_id in enumerate(reading_order):
            nodes[node_id].reading_priority = priority
        primary = reading_order[0]
        secondary = [node_id for node_id in reading_order[1:]
                     if nodes[node_id].importance >= 0.6]
        tertiary = [node_id for node_id in reading_order[1:]
                    if node_id not in secondary]
        hierarchy = VisualHierarchy(
            primary_node_id=primary, secondary_node_ids=secondary,
            tertiary_node_ids=tertiary, reading_order=reading_order,
            reading_direction="LEFT_TO_RIGHT")
        if len(reading_order) > 1:
            context.add_constraint(
                ConstraintType.READING_ORDER, reading_order,
                ConstraintStrength.STRONG,
                "Reading order is derived from semantic hierarchy, not coordinates.",
                {"direction": hierarchy.reading_direction})
        plan = GeometryPlan(
            beat_id=beat.beat_id, visual_family=composition.visual_family,
            nodes=list(nodes.values()), groups=context.groups,
            edges=context.edges, hierarchy=hierarchy,
            constraints=context.constraints, canvas=CanvasSpec(),
            safe_zones=self.policy.safe_zones(),
            style_hints=self.policy.style_hints(
                beat.information_density, art_direction.geometry),
            semantic_geometry_signature="",
            recent_geometry_context=list(recent_context))
        plan.semantic_geometry_signature = _signature(plan)
        return plan

    def fallback_plan(self, beat: SemanticBeat, visual_family: str,
                      reason: str, recent_context: list[str] | None = None
                      ) -> GeometryPlan:
        node = VisualNode(
            node_id=f"geometry_fallback:{beat.beat_id}:hero",
            beat_id=beat.beat_id, role=VisualRole.HERO,
            semantic_refs=(beat.entities[:1] or beat.locations[:1]
                           or beat.events[:1]),
            importance=0.95, salience=0.90,
            preferred_regions=self.policy.regions(VisualRole.HERO),
            min_width=0.30, min_height=0.28, can_crop=False,
            reading_priority=0)
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
            VisualHierarchy(node.node_id, reading_order=[node.node_id]),
            constraints, CanvasSpec(), self.policy.safe_zones(),
            self.policy.style_hints(beat.information_density, []), "",
            list(recent_context or []), True, reason)
        plan.semantic_geometry_signature = _signature(plan) + "|fallback=true"
        return plan

    def _common_constraints(self, context: GeometryFamilyContext) -> None:
        for node in context.nodes.values():
            context.add_constraint(
                ConstraintType.INSIDE_CANVAS, [node.node_id],
                ConstraintStrength.HARD,
                "Every visual node must remain inside the normalized canvas.")
            context.add_constraint(
                ConstraintType.MIN_SIZE, [node.node_id],
                ConstraintStrength.HARD,
                "The node must remain large enough to preserve readability.",
                {"min_width": node.min_width,
                 "min_height": node.min_height})
            if node.importance >= 0.45 and node.role != VisualRole.BACKGROUND:
                context.add_constraint(
                    ConstraintType.OUTSIDE_SAFE_ZONE, [node.node_id],
                    ConstraintStrength.HARD,
                    "Important content cannot occupy the subtitle safe zone.",
                    {"safe_zone_id": "subtitle_safe_zone"})
            if node.preferred_regions:
                context.add_constraint(
                    ConstraintType.PREFER_REGION, [node.node_id],
                    ConstraintStrength.MEDIUM,
                    "Semantic role supplies a soft region preference.",
                    {"regions": [region.value
                                 for region in node.preferred_regions]})
            if node.preferred_aspect_ratio is not None:
                context.add_constraint(
                    ConstraintType.ASPECT_RATIO, [node.node_id],
                    ConstraintStrength.STRONG,
                    "Resolved media metadata supplies its natural aspect ratio.",
                    {"ratio": node.preferred_aspect_ratio,
                     "crop_allowed": node.can_crop})

    def _composition_edges(self, context: GeometryFamilyContext) -> None:
        for relationship in context.composition.relationships:
            context.add_edge(
                relationship.from_layer, relationship.to_layer,
                _relationship_type(relationship.kind, relationship.label),
                "Bootstrap composition records an explicit semantic relationship.",
                directed=relationship.kind not in {"contrasts", "groups"},
                style=relationship.kind)


def debug_geometry_plan(plan: GeometryPlan) -> str:
    """Human-readable graph report without renderer coordinates."""
    node_by_id = {node.node_id: node for node in plan.nodes}
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
    lines.extend(f"- {constraint.constraint_type.value} "
                 f"({', '.join(constraint.node_ids)}) "
                 f"[{constraint.strength.value}]"
                 for constraint in plan.constraints)
    readable = [node_id for node_id in plan.hierarchy.reading_order
                if node_id in node_by_id]
    lines.extend(["", "Reading:", " -> ".join(readable), "",
                  f"Signature: {plan.semantic_geometry_signature}"])
    return "\n".join(lines)
