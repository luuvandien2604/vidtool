"""Render Scene Graph Adapter (spec section 22, Phase 2F Hardening).

Provides a structured, hierarchical scene graph representation wrapping FramePlan.
Maintains 100% parity with EpisodeFramePlan / BeatFramePlan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from videotool.render.frame_plan import (
    BeatFramePlan,
    ConnectorRenderElement,
    EpisodeFramePlan,
    Keyframe,
    MediaRenderElement,
    PixelRect,
    TextRenderElement,
)


@dataclass
class SceneNode:
    node_id: str
    node_type: str  # "media", "text", "connector"
    z_index: int
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "z_index": self.z_index,
            "data": dict(self.data),
        }


@dataclass
class SceneBeat:
    beat_id: str
    start_sec: float
    end_sec: float
    duration_sec: float
    visual_family: str
    camera_behavior: str
    transition_in: str = "CONTINUATION"
    transition_out: str = "CONTINUATION"
    nodes: list[SceneNode] = field(default_factory=list)
    svg_overlay_content: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "beat_id": self.beat_id,
            "start_sec": round(self.start_sec, 3),
            "end_sec": round(self.end_sec, 3),
            "duration_sec": round(self.duration_sec, 3),
            "visual_family": self.visual_family,
            "camera_behavior": self.camera_behavior,
            "transition_in": self.transition_in,
            "transition_out": self.transition_out,
            "nodes": [n.to_dict() for n in self.nodes],
            "has_svg_overlay": self.svg_overlay_content is not None,
        }


@dataclass
class RenderSceneGraph:
    """Hierarchical SceneGraph adapter representing an episode render schedule."""
    episode_id: str
    canvas_width: int
    canvas_height: int
    fps: int
    total_duration_sec: float
    beats: list[SceneBeat] = field(default_factory=list)
    subtitles_ass: str = ""
    schema_version: int = 1

    @classmethod
    def from_frame_plan(cls, plan: EpisodeFramePlan) -> "RenderSceneGraph":
        scene_beats: list[SceneBeat] = []
        for b in plan.beats:
            nodes: list[SceneNode] = []
            for m in b.media_elements:
                nodes.append(SceneNode(
                    node_id=m.element_id,
                    node_type="media",
                    z_index=m.z_index,
                    data=m.to_dict(),
                ))
            for t in b.text_elements:
                nodes.append(SceneNode(
                    node_id=t.element_id,
                    node_type="text",
                    z_index=t.z_index,
                    data=t.to_dict(),
                ))
            for c in b.connectors:
                nodes.append(SceneNode(
                    node_id=c.connector_id,
                    node_type="connector",
                    z_index=15,  # connectors default mid-layer
                    data=c.to_dict(),
                ))
            scene_beats.append(SceneBeat(
                beat_id=b.beat_id,
                start_sec=b.start_sec,
                end_sec=b.end_sec,
                duration_sec=b.duration_sec,
                visual_family=b.visual_family,
                camera_behavior=b.camera_behavior,
                transition_in=b.transition_in,
                transition_out=b.transition_out,
                nodes=nodes,
                svg_overlay_content=b.svg_overlay_content,
            ))
        return cls(
            episode_id=plan.episode_id,
            canvas_width=plan.canvas_width,
            canvas_height=plan.canvas_height,
            fps=plan.fps,
            total_duration_sec=plan.total_duration_sec,
            beats=scene_beats,
            subtitles_ass=plan.subtitles_ass,
            schema_version=1,
        )

    def to_frame_plan(self) -> EpisodeFramePlan:
        beat_plans: list[BeatFramePlan] = []
        for sb in self.beats:
            media_elements: list[MediaRenderElement] = []
            text_elements: list[TextRenderElement] = []
            connectors: list[ConnectorRenderElement] = []

            for n in sb.nodes:
                d = n.data
                if n.node_type == "media":
                    px_dict = d["bounds_px"]
                    px_rect = PixelRect(
                        x=px_dict["x"], y=px_dict["y"],
                        width=px_dict["width"], height=px_dict["height"],
                    )
                    keyframes = [
                        Keyframe(
                            time_offset_sec=k["time_offset_sec"],
                            scale=k.get("scale", 1.0),
                            pan_x=k.get("pan_x", 0.0),
                            pan_y=k.get("pan_y", 0.0),
                            opacity=k.get("opacity", 1.0),
                        )
                        for k in d.get("keyframes", [])
                    ]
                    media_elements.append(MediaRenderElement(
                        element_id=d["element_id"],
                        asset_id=d.get("asset_id"),
                        checksum=d.get("checksum"),
                        media_kind=d.get("media_kind", "photo"),
                        role=d.get("role", "hero"),
                        is_placeholder=d.get("is_placeholder", False),
                        z_index=d.get("z_index", 10),
                        bounds_norm=d.get("bounds_norm", {}),
                        bounds_px=px_rect,
                        entrance_sec=d["entrance_sec"],
                        exit_sec=d["exit_sec"],
                        description=d.get("description", ""),
                        emphasis_start_sec=d.get("emphasis_start_sec"),
                        emphasis_end_sec=d.get("emphasis_end_sec"),
                        camera_motion=d.get("camera_motion", "STABLE"),
                        keyframes=keyframes,
                    ))
                elif n.node_type == "text":
                    px_dict = d["bounds_px"]
                    px_rect = PixelRect(
                        x=px_dict["x"], y=px_dict["y"],
                        width=px_dict["width"], height=px_dict["height"],
                    )
                    text_elements.append(TextRenderElement(
                        element_id=d["element_id"],
                        text=d["text"],
                        role=d.get("role", "support"),
                        text_role=d.get("text_role", "label"),
                        z_index=d.get("z_index", 20),
                        bounds_norm=d.get("bounds_norm", {}),
                        bounds_px=px_rect,
                        entrance_sec=d["entrance_sec"],
                        exit_sec=d["exit_sec"],
                        style_name=d.get("style_name", "NodeLabel"),
                        ass_dialogue=d.get("ass_dialogue", ""),
                    ))
                elif n.node_type == "connector":
                    start_tuple = tuple(d.get("start_px", [0.0, 0.0]))
                    end_tuple = tuple(d.get("end_px", [0.0, 0.0]))
                    connectors.append(ConnectorRenderElement(
                        connector_id=d["connector_id"],
                        source_node_id=d["source_node_id"],
                        target_node_id=d["target_node_id"],
                        relationship_type=d.get("relationship_type", "leads_to"),
                        connector_style_hint=d.get("connector_style_hint", "arrow_straight"),
                        directed=d.get("directed", True),
                        start_px=(float(start_tuple[0]), float(start_tuple[1])),
                        end_px=(float(end_tuple[0]), float(end_tuple[1])),
                        is_dashed=d.get("is_dashed", False),
                        stroke_width=float(d.get("stroke_width", 3.5)),
                        color=d.get("color", "#E6C280"),
                    ))

            beat_plans.append(BeatFramePlan(
                beat_id=sb.beat_id,
                start_sec=sb.start_sec,
                end_sec=sb.end_sec,
                duration_sec=sb.duration_sec,
                visual_family=sb.visual_family,
                camera_behavior=sb.camera_behavior,
                media_elements=media_elements,
                text_elements=text_elements,
                connectors=connectors,
                svg_overlay_content=sb.svg_overlay_content,
                transition_in=sb.transition_in,
                transition_out=sb.transition_out,
            ))

        return EpisodeFramePlan(
            episode_id=self.episode_id,
            canvas_width=self.canvas_width,
            canvas_height=self.canvas_height,
            fps=self.fps,
            total_duration_sec=self.total_duration_sec,
            beats=beat_plans,
            subtitles_ass=self.subtitles_ass,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "fps": self.fps,
            "total_duration_sec": round(self.total_duration_sec, 3),
            "beats": [b.to_dict() for b in self.beats],
        }
