"""Family-specific semantic geometry adapters; no coordinates are solved here."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from videotool.domain.composition import LayerType, VisualComposition
from videotool.domain.geometry import (CanvasRegion, ConstraintStrength,
                                       ConstraintType, EdgeType,
                                       GeometryConstraint, VisualEdge,
                                       VisualGroup, VisualNode, VisualRole)
from videotool.domain.semantic_beat import SemanticBeat
from videotool.editorial.geometry.policy import GeometryPolicy


@dataclass
class GeometryFamilyContext:
    beat: SemanticBeat
    composition: VisualComposition
    nodes: dict[str, VisualNode]
    policy: GeometryPolicy
    groups: list[VisualGroup] = field(default_factory=list)
    edges: list[VisualEdge] = field(default_factory=list)
    constraints: list[GeometryConstraint] = field(default_factory=list)

    def add_constraint(self, kind: ConstraintType, node_ids: list[str],
                       strength: ConstraintStrength, reason: str,
                       parameters: dict | None = None) -> None:
        ordinal = len(self.constraints)
        self.constraints.append(GeometryConstraint(
            constraint_id=f"gc:{self.beat.beat_id}:{ordinal:03d}",
            constraint_type=kind, node_ids=node_ids, strength=strength,
            weight=self.policy.strength_weight(strength),
            parameters=parameters or {}, reason=reason))

    def add_edge(self, source: str, target: str, kind: EdgeType,
                 reason: str, directed: bool = True,
                 importance: float = 0.75,
                 style: str = "") -> None:
        if source == target or source not in self.nodes or target not in self.nodes:
            return
        key = (source, target, kind)
        if any((edge.source_node_id, edge.target_node_id,
                edge.relationship_type) == key for edge in self.edges):
            return
        self.edges.append(VisualEdge(
            edge_id=f"ge:{self.beat.beat_id}:{len(self.edges):03d}",
            source_node_id=source, target_node_id=target,
            relationship_type=kind, importance=importance,
            directed=directed, connector_style_hint=style, reason=reason))

    def add_group(self, semantic_role: str, node_ids: list[str],
                  importance: float, reason: str,
                  region: CanvasRegion | None = None,
                  hint: str = "") -> None:
        members = list(dict.fromkeys(node_id for node_id in node_ids
                                    if node_id in self.nodes))
        if not members:
            return
        group = VisualGroup(
            group_id=f"group:{self.beat.beat_id}:{len(self.groups):02d}",
            node_ids=members, semantic_role=semantic_role,
            importance=importance, preferred_region=region,
            internal_layout_hint=hint, reason=reason)
        self.groups.append(group)
        self.add_constraint(
            ConstraintType.GROUP, members, ConstraintStrength.STRONG,
            reason, {"group_id": group.group_id,
                     "internal_layout_hint": hint})

    def layers_of_type(self, *types: LayerType) -> list[str]:
        return [layer.id for layer in self.composition.layers
                if layer.id in self.nodes and layer.type in types]


class GeometryFamilyBuilder(Protocol):
    family_id: str

    def build(self, context: GeometryFamilyContext) -> list[str]: ...


def _semantic_nodes(ctx: GeometryFamilyContext) -> list[str]:
    return [node.node_id for node in ctx.nodes.values()
            if node.role not in {VisualRole.BACKGROUND, VisualRole.DECORATIVE}]


class ArchivalSubjectGeometry:
    family_id = "archival_subject"

    def build(self, ctx: GeometryFamilyContext) -> list[str]:
        visual = [node.node_id for node in ctx.nodes.values()
                  if node.media_kind in {"portrait", "photo"}
                  or node.role in {VisualRole.PORTRAIT,
                                   VisualRole.ARCHIVAL_IMAGE}]
        labels = [node.node_id for node in ctx.nodes.values()
                  if node.text_role is not None]
        documents = [node.node_id for node in ctx.nodes.values()
                     if node.media_kind == "document"]
        primary = visual[:1] or labels[:1] or _semantic_nodes(ctx)[:1]
        if primary:
            ctx.nodes[primary[0]].preferred_regions = [
                CanvasRegion.LEFT, CanvasRegion.CENTER_LEFT]
            for label in labels:
                ctx.add_constraint(
                    ConstraintType.NEAR, [label, primary[0]],
                    ConstraintStrength.STRONG,
                    "Identity labels stay associated with the narrated subject.")
            ctx.add_group("character", primary + labels, 0.92,
                          "Portrait and identity labels form one character group.",
                          CanvasRegion.LEFT, "portrait_with_identity")
            for document in documents:
                ctx.add_edge(primary[0], document, EdgeType.ASSOCIATED_WITH,
                             "The source document is associated with the subject named in this beat.")
        return primary + documents + labels


class DocumentEvidenceGeometry:
    family_id = "document_evidence"

    def build(self, ctx: GeometryFamilyContext) -> list[str]:
        documents = [node.node_id for node in ctx.nodes.values()
                     if node.media_kind == "document"
                     or node.role == VisualRole.DOCUMENT]
        details = [node.node_id for node in ctx.nodes.values()
                   if node.text_role is not None
                   or ctx.composition.layer_by_id(node.node_id).type
                   in {LayerType.LINE, LayerType.SHAPE}]
        primary = documents[:1] or details[:1] or _semantic_nodes(ctx)[:1]
        if documents:
            ctx.nodes[documents[0]].preferred_regions = [
                CanvasRegion.RIGHT, CanvasRegion.CENTER_RIGHT]
            for detail in details:
                if detail == documents[0]:
                    continue
                ctx.add_constraint(
                    ConstraintType.CONTAINED_IN, [detail, documents[0]],
                    ConstraintStrength.HARD,
                    "Quoted or highlighted evidence belongs inside its source document.")
                if ctx.nodes[detail].text_role is not None:
                    ctx.add_edge(detail, documents[0], EdgeType.QUOTED_FROM,
                                 "The displayed quotation is extracted from this document.")
            ctx.add_group("evidence", documents + details, 0.95,
                          "Source, quotation and marks form one evidence group.",
                          CanvasRegion.RIGHT, "document_with_evidence")
        return primary + [node for node in documents + details
                          if node not in primary]


class GeographicMapGeometry:
    family_id = "geographic_map"

    def build(self, ctx: GeometryFamilyContext) -> list[str]:
        maps = [node.node_id for node in ctx.nodes.values()
                if node.media_kind == "map" or node.role == VisualRole.MAP]
        contained = ctx.layers_of_type(LayerType.ICON, LayerType.LINE,
                                       LayerType.ARROW, LayerType.SHAPE)
        labels = [node.node_id for node in ctx.nodes.values()
                  if node.text_role is not None]
        primary = maps[:1] or _semantic_nodes(ctx)[:1]
        if maps:
            ctx.nodes[maps[0]].preferred_regions = [CanvasRegion.CENTER,
                                                    CanvasRegion.FULL]
            for node_id in contained:
                if node_id != maps[0]:
                    ctx.add_constraint(
                        ConstraintType.CONTAINED_IN, [node_id, maps[0]],
                        ConstraintStrength.HARD,
                        "Geographic markers and routes must remain inside their map.")
            for label in labels:
                ctx.add_constraint(
                    ConstraintType.ANCHOR_TO, [label, maps[0]],
                    ConstraintStrength.STRONG,
                    "Place labels remain anchored to the map they describe.")
            endpoints = ctx.layers_of_type(LayerType.ICON)
            if len(endpoints) >= 2:
                ctx.add_edge(endpoints[0], endpoints[1], EdgeType.ROUTE_TO,
                             "Narrated movement establishes an origin-to-destination route.",
                             style="route")
                ctx.add_constraint(
                    ConstraintType.CONNECT, endpoints[:2],
                    ConstraintStrength.HARD,
                    "A route requires valid source and destination endpoints.")
            ctx.add_group("geography", maps + contained + labels, 0.90,
                          "Map, geographic marks and place labels form one spatial group.",
                          CanvasRegion.CENTER, "map_with_overlays")
        return primary + [node for node in labels + contained
                          if node not in primary]


class ChronologicalTimelineGeometry:
    family_id = "chronological_timeline"

    def build(self, ctx: GeometryFamilyContext) -> list[str]:
        axes = ctx.layers_of_type(LayerType.LINE)
        events = [layer.id for layer in ctx.composition.layers
                  if layer.id in ctx.nodes and "_ev_" in layer.id]
        labels = [layer.id for layer in ctx.composition.layers
                  if layer.id in ctx.nodes and "_lbl_" in layer.id]
        order = events or labels or _semantic_nodes(ctx)
        if len(order) > 1:
            ctx.add_constraint(
                ConstraintType.READING_ORDER, order,
                ConstraintStrength.HARD,
                "Timeline events preserve the semantic chronology.",
                {"direction": "CHRONOLOGICAL"})
            ctx.add_constraint(
                ConstraintType.ORDER_LEFT_TO_RIGHT, order,
                ConstraintStrength.MEDIUM,
                "Horizontal chronology is preferred without fixing coordinates.")
            ctx.add_constraint(
                ConstraintType.NO_OVERLAP, order,
                ConstraintStrength.HARD,
                "Distinct timeline events must remain independently readable.")
            for source, target in zip(order, order[1:]):
                ctx.add_edge(source, target, EdgeType.BEFORE,
                             "Earlier narrated event precedes the next event.")
        ctx.add_group("chronology", axes + events + labels, 0.88,
                      "Axis, events and labels form one chronological group.",
                      CanvasRegion.CENTER, "ordered_sequence")
        return order + axes + labels


class CausalNetworkGeometry:
    family_id = "causal_network"

    def build(self, ctx: GeometryFamilyContext) -> list[str]:
        nodes = [layer.id for layer in ctx.composition.layers
                 if layer.id in ctx.nodes and layer.type == LayerType.LABEL]
        for relationship in ctx.composition.relationships:
            kind = (EdgeType.CONTRASTS_WITH if relationship.kind == "contrasts"
                    else EdgeType.CAUSES)
            ctx.add_edge(relationship.from_layer, relationship.to_layer, kind,
                         "The visual connection preserves the narrated semantic relationship.",
                         directed=kind != EdgeType.CONTRASTS_WITH,
                         style="causal_arrow")
        if len(nodes) > 1:
            ctx.add_constraint(
                ConstraintType.NO_OVERLAP, nodes,
                ConstraintStrength.HARD,
                "Causal factors and outcomes must remain distinct readable nodes.")
        for edge in ctx.edges:
            ctx.add_constraint(
                ConstraintType.CONNECT,
                [edge.source_node_id, edge.target_node_id],
                ConstraintStrength.HARD,
                "Every causal connector must join two real semantic nodes.",
                {"edge_id": edge.edge_id})
        if nodes:
            ctx.add_group("causal_graph", nodes, 0.90,
                          "Narrated factors and outcomes form one causal graph.",
                          CanvasRegion.CENTER, "relationship_graph")
        return nodes or _semantic_nodes(ctx)


class FullFrameCinematicGeometry:
    family_id = "full_frame_cinematic"

    def build(self, ctx: GeometryFamilyContext) -> list[str]:
        hero = [node.node_id for node in ctx.nodes.values()
                if node.role in {VisualRole.HERO, VisualRole.ARCHIVAL_IMAGE,
                                 VisualRole.PORTRAIT}]
        overlays = [node.node_id for node in ctx.nodes.values()
                    if node.text_role is not None]
        primary = hero[:1] or overlays[:1] or _semantic_nodes(ctx)[:1]
        if primary:
            ctx.nodes[primary[0]].preferred_regions = [CanvasRegion.FULL,
                                                       CanvasRegion.CENTER]
        for overlay in overlays:
            if primary and overlay != primary[0]:
                ctx.add_constraint(
                    ConstraintType.NEAR, [overlay, primary[0]],
                    ConstraintStrength.MEDIUM,
                    "Editorial text remains associated with the full-frame image.")
        return primary + [node for node in overlays if node not in primary]


FAMILY_GEOMETRY_BUILDERS: dict[str, GeometryFamilyBuilder] = {
    builder.family_id: builder for builder in (
        ArchivalSubjectGeometry(), DocumentEvidenceGeometry(),
        GeographicMapGeometry(), ChronologicalTimelineGeometry(),
        CausalNetworkGeometry(), FullFrameCinematicGeometry(),
    )
}
