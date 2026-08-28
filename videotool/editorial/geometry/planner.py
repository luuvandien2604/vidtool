"""Semantic-first node and topology planning, independent of compositions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from videotool.domain.assets import AssetRequirement, MediaAsset
from videotool.domain.geometry import (CanvasRegion, ConstraintStrength,
                                       ConstraintType, EdgeType,
                                       GeometryConstraint, TextRole, VisualEdge,
                                       VisualGroup, VisualNode, VisualRole)
from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.timing import AnchorType, SemanticAnchor

from .policy import GeometryPolicy


@dataclass
class SemanticNodePlanningResult:
    nodes: list[VisualNode]
    groups: list[VisualGroup]
    edges: list[VisualEdge]
    constraints: list[GeometryConstraint]
    reading_order: list[str]


@dataclass
class _PlanningContext:
    beat: SemanticBeat
    family: str
    strategy_id: str
    policy: GeometryPolicy
    anchors: list[SemanticAnchor] = field(default_factory=list)
    nodes: list[VisualNode] = field(default_factory=list)
    groups: list[VisualGroup] = field(default_factory=list)
    edges: list[VisualEdge] = field(default_factory=list)
    constraints: list[GeometryConstraint] = field(default_factory=list)

    def add_node(self, role: VisualRole, refs: list[str], *,
                 asset: MediaAsset | None = None, media_kind: str = "",
                 text_role: TextRole | None = None,
                 regions: list[CanvasRegion] | None = None) -> str:
        node_id = f"semantic:{self.beat.beat_id}:{role.value.lower()}:{len(self.nodes):02d}"
        kind = asset.kind if asset else media_kind
        minimum = self.policy.min_size(role)
        crop, rotate = self.policy.crop_policy(role, kind)
        width = height = density = None
        max_lines = None
        if text_role is not None:
            width, height, density, max_lines = self.policy.measure_text(
                " ".join(refs), text_role)
        ratio = (round(asset.width / asset.height, 5)
                 if asset and asset.width > 0 and asset.height > 0 else None)
        self.nodes.append(VisualNode(
            node_id=node_id, beat_id=self.beat.beat_id, role=role,
            semantic_refs=list(refs), asset_id=asset.asset_id if asset else None,
            media_kind=kind, importance=self.policy.importance(role),
            salience=self.policy.salience(role),
            preferred_regions=list(regions or self.policy.regions(role)),
            min_width=minimum[0], min_height=minimum[1],
            preferred_aspect_ratio=ratio, can_crop=crop, can_scale=True,
            can_rotate=rotate, text_density=density or 0.0,
            text_role=text_role, estimated_width=width,
            estimated_height=height, max_lines=max_lines,
            source_layer_id=None))
        return node_id

    def add_edge(self, source: str, target: str, kind: EdgeType,
                 reason: str, directed: bool = True) -> None:
        if source == target:
            return
        self.edges.append(VisualEdge(
            edge_id=f"ge:{self.beat.beat_id}:{len(self.edges):03d}",
            source_node_id=source, target_node_id=target,
            relationship_type=kind, importance=0.8, directed=directed,
            connector_style_hint="semantic", reason=reason))

    def add_constraint(self, kind: ConstraintType, node_ids: list[str],
                       strength: ConstraintStrength, reason: str,
                       parameters: dict | None = None) -> None:
        self.constraints.append(GeometryConstraint(
            constraint_id=f"gc:{self.beat.beat_id}:semantic:{len(self.constraints):03d}",
            constraint_type=kind, node_ids=node_ids, strength=strength,
            weight=self.policy.strength_weight(strength),
            parameters=parameters or {}, reason=reason))

    def add_group(self, role: str, members: list[str], reason: str,
                  region: CanvasRegion = CanvasRegion.CENTER,
                  hint: str = "") -> None:
        members = list(dict.fromkeys(members))
        if not members:
            return
        group_id = f"group:{self.beat.beat_id}:{len(self.groups):02d}"
        self.groups.append(VisualGroup(
            group_id=group_id, node_ids=members, semantic_role=role,
            importance=0.9, preferred_region=region,
            internal_layout_hint=hint, reason=reason))
        self.add_constraint(ConstraintType.GROUP, members,
                            ConstraintStrength.STRONG, reason,
                            {"group_id": group_id,
                             "internal_layout_hint": hint})


def _asset_role(asset: MediaAsset, family: str) -> VisualRole:
    if asset.kind == "map":
        return VisualRole.MAP
    if asset.kind == "document":
        return VisualRole.DOCUMENT
    if asset.kind == "portrait":
        return VisualRole.PORTRAIT
    if asset.kind in {"photo", "image", "video"}:
        return (VisualRole.HERO if family == "full_frame_cinematic"
                else VisualRole.ARCHIVAL_IMAGE)
    return VisualRole.SUPPORT


def _relationship_parts(value: str) -> tuple[str, EdgeType, str] | None:
    patterns = (
        (r"^\s*(.+?)\s*->\s*(.+?)\s*$", EdgeType.CAUSES),
        (r"^\s*(.+?)\s+causes?\s+(.+?)\s*$", EdgeType.CAUSES),
        (r"^\s*(.+?)\s+(?:leads?|led)\s+to\s+(.+?)\s*$", EdgeType.LEADS_TO),
        (r"^\s*(.+?)\s+before\s+(.+?)\s*$", EdgeType.BEFORE),
        (r"^\s*(.+?)\s+contrasts?\s+(?:with\s+)?(.+?)\s*$",
         EdgeType.CONTRASTS_WITH),
    )
    for pattern, kind in patterns:
        match = re.match(pattern, value, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(), kind, match.group(2).strip()
    return None


class SemanticNodePlanner:
    """Derive inventory/topology only from semantic and plan-of-record inputs."""

    def __init__(self, policy: GeometryPolicy):
        self.policy = policy

    def plan(self, beat: SemanticBeat, visual_family: str,
             selected_strategy: str,
             assets: list[MediaAsset], requirements: list[AssetRequirement],
             art_direction, anchors: list[SemanticAnchor]
             ) -> SemanticNodePlanningResult:
        del art_direction  # direction is resolved after hierarchy is known.
        ctx = _PlanningContext(beat, visual_family, selected_strategy,
                               self.policy, list(anchors))
        builders = {
            "chronological_timeline": self._timeline,
            "causal_network": self._causal,
            "geographic_map": self._map,
            "document_evidence": self._document,
            "archival_subject": self._character,
            "full_frame_cinematic": self._full_frame,
            "paper_collage_hero": self._paper_collage,
        }
        builders.get(visual_family, self._full_frame)(
            ctx, assets, requirements)
        if not ctx.nodes:
            ctx.add_node(VisualRole.HERO,
                         beat.entities[:1] or beat.events[:1]
                         or beat.locations[:1] or [beat.visual_intent])
        order = [node.node_id for node in ctx.nodes]
        return SemanticNodePlanningResult(ctx.nodes, ctx.groups, ctx.edges,
                                          ctx.constraints, order)

    def _paper_collage(self, ctx: _PlanningContext, assets: list[MediaAsset], requirements: list[AssetRequirement]) -> None:
        del requirements
        # 1. Primary Hero Node (Archival background)
        hero_asset = next((a for a in assets if a.kind in ("photo", "portrait")), (assets[0] if assets else None))
        hero_refs = ctx.beat.entities[:1] or ctx.beat.events[:1] or ctx.beat.locations[:1] or [ctx.beat.visual_intent]
        ctx.add_node(VisualRole.HERO, hero_refs, asset=hero_asset, regions=[CanvasRegion.FULL])

        # 2. Left Sidebar Chapter / Headline Label
        title_ref = ctx.beat.entities[:1] or [ctx.beat.visual_intent]
        ctx.add_node(VisualRole.LABEL, title_ref, text_role=TextRole.TITLE, regions=[CanvasRegion.TOP_LEFT, CanvasRegion.LEFT])

        # 3. Gold Fact Date / Milestone Card (if dates exist)
        if ctx.beat.dates:
            ctx.add_node(VisualRole.DATE, ctx.beat.dates[:1], text_role=TextRole.DATE, regions=[CanvasRegion.BOTTOM_LEFT, CanvasRegion.LEFT])

        # 4. Secondary Inset Card (Map, Document, or Secondary Photo)
        secondary_asset = next((a for a in assets if a != hero_asset and a.kind in ("map", "document", "photo", "portrait")), None)
        if secondary_asset:
            role = VisualRole.MAP if secondary_asset.kind == "map" else (VisualRole.DOCUMENT if secondary_asset.kind == "document" else VisualRole.SUPPORT)
            inset_refs = ctx.beat.locations[:1] or ctx.beat.entities[:1] or ["inset"]
            ctx.add_node(role, inset_refs, asset=secondary_asset, regions=[CanvasRegion.TOP_RIGHT, CanvasRegion.RIGHT])

        # 5. Quote Banner (if quote function or quote text present)
        from videotool.domain.semantic_beat import SemanticFunction
        if ctx.beat.semantic_function == SemanticFunction.QUOTE or '"' in ctx.beat.narration_text:
            q_text = ctx.beat.narration_text
            ctx.add_node(VisualRole.QUOTE, [q_text], text_role=TextRole.QUOTE, regions=[CanvasRegion.BOTTOM, CanvasRegion.CENTER])

    def _timeline(self, ctx, assets, requirements) -> None:
        del assets, requirements
        anchor_values = [anchor.text for anchor in ctx.anchors
                         if anchor.anchor_type in {AnchorType.DATE_MENTION,
                                                   AnchorType.EVENT_MENTION}]
        values = list(dict.fromkeys(ctx.beat.dates + ctx.beat.events
                                    + anchor_values))
        if not values:
            values = ctx.beat.entities[:1] or [ctx.beat.visual_intent]
        nodes = [ctx.add_node(VisualRole.TIMELINE_NODE, [value],
                              text_role=(TextRole.DATE if value in ctx.beat.dates
                                         else TextRole.LABEL))
                 for value in values]
        if len(nodes) > 1:
            ctx.add_constraint(ConstraintType.READING_ORDER, nodes,
                               ConstraintStrength.HARD,
                               "Semantic events and dates preserve chronology.",
                               {"direction": "CHRONOLOGICAL_HORIZONTAL"})
            ctx.add_constraint(ConstraintType.ORDER_LEFT_TO_RIGHT, nodes,
                               ConstraintStrength.MEDIUM,
                               "Chronology prefers a horizontal progression.")
            ctx.add_constraint(ConstraintType.NO_OVERLAP, nodes,
                               ConstraintStrength.HARD,
                               "Timeline events remain independently readable.")
            for source, target in zip(nodes, nodes[1:]):
                ctx.add_edge(source, target, EdgeType.BEFORE,
                             "Earlier semantic event precedes the next event.")
        ctx.add_group("chronology", nodes,
                      "Semantic events form one chronological sequence.",
                      hint="ordered_sequence")

    def _causal(self, ctx, assets, requirements) -> None:
        del assets, requirements
        relationship_values = ctx.beat.relationships + [
            anchor.text for anchor in ctx.anchors
            if anchor.anchor_type in {AnchorType.RELATIONSHIP,
                                      AnchorType.CAUSE, AnchorType.EFFECT}]
        parsed = [part for value in relationship_values
                  if (part := _relationship_parts(value))]
        concepts: list[str] = []
        if parsed:
            for source, _, target in parsed:
                concepts.extend((source, target))
        else:
            concepts = (ctx.beat.entities + ctx.beat.events
                        + ctx.beat.objects + ctx.beat.locations)
        concepts = list(dict.fromkeys(value for value in concepts if value))
        while len(concepts) < 2:
            concepts.append("effect" if concepts else "cause")
        by_concept = {value: ctx.add_node(VisualRole.EVIDENCE, [value],
                                          text_role=TextRole.LABEL)
                      for value in concepts}
        if parsed:
            for source, kind, target in parsed:
                ctx.add_edge(by_concept[source], by_concept[target], kind,
                             "Directed edge preserves the semantic relationship.",
                             directed=kind != EdgeType.CONTRASTS_WITH)
        else:
            for source, target in zip(concepts, concepts[1:]):
                ctx.add_edge(by_concept[source], by_concept[target],
                             EdgeType.CAUSES,
                             "Semantic causal function establishes cause-to-effect flow.")
        nodes = list(by_concept.values())
        ctx.add_constraint(ConstraintType.NO_OVERLAP, nodes,
                           ConstraintStrength.HARD,
                           "Causal concepts remain distinct readable nodes.")
        for edge in ctx.edges:
            ctx.add_constraint(ConstraintType.CONNECT,
                               [edge.source_node_id, edge.target_node_id],
                               ConstraintStrength.HARD,
                               "Every semantic edge joins real graph nodes.",
                               {"edge_id": edge.edge_id})
        ctx.add_group("causal_graph", nodes,
                      "Semantic factors and outcomes form one causal graph.",
                      hint="relationship_graph")

    def _map(self, ctx, assets, requirements) -> None:
        map_assets = [asset for asset in assets if asset.kind == "map"]
        map_asset = map_assets[0] if map_assets else None
        map_id = ctx.add_node(VisualRole.MAP,
                              ctx.beat.locations or [ctx.beat.visual_intent],
                              asset=map_asset, media_kind="map",
                              regions=[CanvasRegion.CENTER, CanvasRegion.FULL])
        semantic_locations = list(dict.fromkeys(
            ctx.beat.locations + [anchor.text for anchor in ctx.anchors
                                  if anchor.anchor_type
                                  == AnchorType.LOCATION_MENTION]))
        endpoints = [ctx.add_node(VisualRole.CONNECTOR_ENDPOINT, [location],
                                  text_role=TextRole.LOCATION)
                     for location in semantic_locations]
        for endpoint in endpoints:
            ctx.add_constraint(ConstraintType.CONTAINED_IN,
                               [endpoint, map_id], ConstraintStrength.HARD,
                               "Semantic location endpoint belongs inside its map.")
            ctx.add_constraint(ConstraintType.ANCHOR_TO,
                               [endpoint, map_id], ConstraintStrength.STRONG,
                               "Place semantics remain anchored to the map.")
        if len(endpoints) >= 2:
            ctx.add_edge(endpoints[0], endpoints[-1], EdgeType.ROUTE_TO,
                         "Semantic locations establish route endpoints.")
            ctx.add_constraint(ConstraintType.CONNECT,
                               [endpoints[0], endpoints[-1]],
                               ConstraintStrength.HARD,
                               "A route joins its semantic endpoints.")
        ctx.add_group("geography", [map_id] + endpoints,
                      "Map and semantic locations form one spatial group.",
                      hint="map_with_endpoints")

    def _document(self, ctx, assets, requirements) -> None:
        docs = [asset for asset in assets if asset.kind == "document"]
        doc = docs[0] if docs else None
        doc_id = ctx.add_node(VisualRole.DOCUMENT,
                              ctx.beat.objects[:1] or ["document"],
                              asset=doc, media_kind="document",
                              regions=[CanvasRegion.RIGHT,
                                       CanvasRegion.CENTER_RIGHT])
        quote_refs = [anchor.text for anchor in ctx.anchors
                      if anchor.anchor_type == AnchorType.QUOTE_MENTION]
        evidence_refs = (quote_refs or ctx.beat.relationships or ctx.beat.events
                         or ctx.beat.objects or [ctx.beat.visual_intent])
        evidence_id = ctx.add_node(VisualRole.QUOTE, evidence_refs[:1],
                                   text_role=TextRole.QUOTE)
        ctx.add_constraint(ConstraintType.CONTAINED_IN,
                           [evidence_id, doc_id], ConstraintStrength.HARD,
                           "Evidence belongs inside its semantic source document.")
        ctx.add_edge(evidence_id, doc_id, EdgeType.QUOTED_FROM,
                     "Displayed evidence is extracted from the document.")
        ctx.add_group("evidence", [doc_id, evidence_id],
                      "Document and evidence form one provenance group.",
                      CanvasRegion.RIGHT, "document_with_evidence")

    def _character(self, ctx, assets, requirements) -> None:
        portraits = [asset for asset in assets
                     if asset.kind in {"portrait", "photo"}]
        subject_refs = ctx.beat.entities[:1] or [ctx.beat.visual_intent]
        subject = ctx.add_node(
            _asset_role(portraits[0], ctx.family) if portraits else VisualRole.PORTRAIT,
            subject_refs, asset=portraits[0] if portraits else None,
            media_kind=portraits[0].kind if portraits else "portrait",
            regions=[CanvasRegion.LEFT, CanvasRegion.CENTER_LEFT])
        identity = ctx.add_node(VisualRole.LABEL, subject_refs,
                                text_role=TextRole.LABEL)
        ctx.add_constraint(ConstraintType.NEAR, [identity, subject],
                           ConstraintStrength.STRONG,
                           "Identity semantics remain associated with the subject.")
        ctx.add_group("character", [subject, identity],
                      "Entity, portrait and identity form a character group.",
                      CanvasRegion.LEFT, "portrait_with_identity")
        for asset in [item for item in assets if item.kind == "document"]:
            document = ctx.add_node(VisualRole.DOCUMENT, subject_refs,
                                    asset=asset, media_kind="document")
            ctx.add_edge(subject, document, EdgeType.ASSOCIATED_WITH,
                         "Source document is associated with the subject.")
        if not any(item.kind == "document" for item in assets):
            document_requirement = next(
                (item for item in requirements if item.kind == "document"), None)
            if document_requirement:
                document = ctx.add_node(
                    VisualRole.DOCUMENT,
                    document_requirement.entities
                    or [document_requirement.description],
                    media_kind="document")
                ctx.add_edge(subject, document, EdgeType.ASSOCIATED_WITH,
                             "Required source document supports the subject.")

    def _full_frame(self, ctx, assets, requirements) -> None:
        visual = next((asset for asset in assets
                       if asset.kind in {"photo", "portrait", "image", "video"}),
                      None)
        hero = ctx.add_node(_asset_role(visual, ctx.family) if visual
                            else VisualRole.HERO,
                            ctx.beat.entities[:1] or ctx.beat.events[:1]
                            or [ctx.beat.visual_intent], asset=visual,
                            media_kind=(visual.kind if visual else
                                        next((item.kind for item in requirements
                                              if item.kind in {"photo", "portrait",
                                                               "image", "video"}), "")),
                            regions=[CanvasRegion.FULL, CanvasRegion.CENTER])
        if (ctx.beat.semantic_function.value in {"QUOTE", "DATA"}
                or any(token in ctx.strategy_id.lower()
                       for token in ("quote", "data", "evidence"))):
            overlay = ctx.add_node(VisualRole.QUOTE, [ctx.beat.visual_intent],
                                   text_role=TextRole.QUOTE)
            ctx.add_constraint(ConstraintType.NEAR, [overlay, hero],
                               ConstraintStrength.MEDIUM,
                               "Overlay hierarchy remains associated with the hero.")
