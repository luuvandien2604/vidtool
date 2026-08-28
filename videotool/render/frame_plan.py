"""Renderer-independent frame planning and keyframe generation.

Converts solved semantic geometry, motion plans, and timeline data into an
explicit, deterministic keyframe schedule. Pure Python, no external subprocesses.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from videotool.domain.geometry import VisualRole
from videotool.render.subtitles import generate_node_text_dialogue, generate_subtitles_ass
from videotool.render.svg_overlay import generate_svg_overlay


@dataclass(frozen=True)
class PixelRect:
    x: int
    y: int
    width: int
    height: int

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class Keyframe:
    time_offset_sec: float  # relative to beat start (0.0 .. duration_sec)
    scale: float = 1.0      # 1.0 = normal 100%, 1.08 = 8% zoom
    pan_x: float = 0.0      # normalized pan offset (-1.0 .. 1.0)
    pan_y: float = 0.0
    opacity: float = 1.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class MediaRenderElement:
    element_id: str
    asset_id: str | None
    checksum: str | None
    media_kind: str
    role: str
    is_placeholder: bool
    z_index: int
    bounds_norm: dict[str, float]
    bounds_px: PixelRect
    entrance_sec: float
    exit_sec: float
    description: str = ""
    emphasis_start_sec: float | None = None
    emphasis_end_sec: float | None = None
    camera_motion: str = "STABLE"
    keyframes: list[Keyframe] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "media",
            "element_id": self.element_id,
            "asset_id": self.asset_id,
            "checksum": self.checksum,
            "media_kind": self.media_kind,
            "role": self.role,
            "is_placeholder": self.is_placeholder,
            "z_index": self.z_index,
            "bounds_norm": dict(self.bounds_norm),
            "bounds_px": self.bounds_px.to_dict(),
            "entrance_sec": round(self.entrance_sec, 3),
            "exit_sec": round(self.exit_sec, 3),
            "description": self.description,
            "emphasis_start_sec": round(self.emphasis_start_sec, 3) if self.emphasis_start_sec is not None else None,
            "emphasis_end_sec": round(self.emphasis_end_sec, 3) if self.emphasis_end_sec is not None else None,
            "camera_motion": self.camera_motion,
            "keyframes": [k.to_dict() for k in self.keyframes],
        }


@dataclass
class TextRenderElement:
    element_id: str
    text: str
    role: str
    text_role: str
    z_index: int
    bounds_norm: dict[str, float]
    bounds_px: PixelRect
    entrance_sec: float
    exit_sec: float
    content_source: str = "raw"  # "raw" | "ai_authored" | "override"
    style_name: str = "NodeLabel"
    ass_dialogue: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "text",
            "element_id": self.element_id,
            "text": self.text,
            "role": self.role,
            "text_role": self.text_role,
            "content_source": self.content_source,
            "z_index": self.z_index,
            "bounds_norm": dict(self.bounds_norm),
            "bounds_px": self.bounds_px.to_dict(),
            "entrance_sec": round(self.entrance_sec, 3),
            "exit_sec": round(self.exit_sec, 3),
            "style_name": self.style_name,
            "ass_dialogue": self.ass_dialogue,
        }


@dataclass
class ConnectorRenderElement:
    connector_id: str
    source_node_id: str
    target_node_id: str
    relationship_type: str
    connector_style_hint: str
    directed: bool
    start_px: tuple[float, float]
    end_px: tuple[float, float]
    is_dashed: bool = False
    stroke_width: float = 3.5
    color: str = "#E6C280"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "connector",
            "connector_id": self.connector_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "relationship_type": self.relationship_type,
            "connector_style_hint": self.connector_style_hint,
            "directed": self.directed,
            "start_px": [round(v, 2) for v in self.start_px],
            "end_px": [round(v, 2) for v in self.end_px],
            "is_dashed": self.is_dashed,
            "stroke_width": self.stroke_width,
            "color": self.color,
        }


@dataclass
class BeatFramePlan:
    beat_id: str
    start_sec: float
    end_sec: float
    duration_sec: float
    visual_family: str
    camera_behavior: str
    media_elements: list[MediaRenderElement] = field(default_factory=list)
    text_elements: list[TextRenderElement] = field(default_factory=list)
    connectors: list[ConnectorRenderElement] = field(default_factory=list)
    svg_overlay_content: str | None = None
    transition_in: str = "CONTINUATION"
    transition_out: str = "CONTINUATION"

    def to_dict(self) -> dict[str, Any]:
        return {
            "beat_id": self.beat_id,
            "start_sec": round(self.start_sec, 3),
            "end_sec": round(self.end_sec, 3),
            "duration_sec": round(self.duration_sec, 3),
            "visual_family": self.visual_family,
            "camera_behavior": self.camera_behavior,
            "media_elements": [m.to_dict() for m in self.media_elements],
            "text_elements": [t.to_dict() for t in self.text_elements],
            "connectors": [c.to_dict() for c in self.connectors],
            "has_svg_overlay": self.svg_overlay_content is not None,
            "transition_in": self.transition_in,
            "transition_out": self.transition_out,
        }


@dataclass
class EpisodeFramePlan:
    episode_id: str
    canvas_width: int
    canvas_height: int
    fps: int
    total_duration_sec: float
    beats: list[BeatFramePlan] = field(default_factory=list)
    subtitles_ass: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "fps": self.fps,
            "total_duration_sec": round(self.total_duration_sec, 3),
            "beats": [b.to_dict() for b in self.beats],
            "subtitle_dialogue_count": len([line for line in self.subtitles_ass.splitlines() if line.startswith("Dialogue:")]),
        }


def _norm_to_px_rect(norm_rect: dict[str, float], canvas_w: int, canvas_h: int) -> PixelRect:
    x = int(round(norm_rect["x"] * canvas_w))
    y = int(round(norm_rect["y"] * canvas_h))
    w = max(2, int(round(norm_rect["width"] * canvas_w)))
    h = max(2, int(round(norm_rect["height"] * canvas_h)))
    # Clamp within canvas bounds
    x = max(0, min(canvas_w - w, x))
    y = max(0, min(canvas_h - h, y))
    return PixelRect(x=x, y=y, width=w, height=h)


def _extract_quote_or_label_text(node: dict[str, Any], beat: dict[str, Any]) -> str:
    """Extract legible human text for a text-only node, filtering out internal developer prompts."""
    refs = node.get("semantic_refs", [])
    if refs:
        for ref in refs:
            ref_str = str(ref).strip()
            # Filter developer instructions/prompts
            if not any(bad in ref_str.lower() for bad in ("present the", "identity metadata", "prompt", "debug", "placeholder", "portrait +")):
                if len(ref_str) > 0 and len(ref_str) < 40:
                    return ref_str

    text_role = node.get("text_role", "")
    role = node.get("role", "")

    if text_role == "QUOTE" or role == "QUOTE":
        narration = beat.get("narration_text", "")
        # Look for quoted text in narration
        match = re.search(r'["\u201c]([^"\u201d]+)["\u201d]', narration)
        if match:
            return f'"{match.group(1)}"'
        if narration:
            words = narration.split()
            return " ".join(words[:6]) + "..."

    # If node has label or entity name from beat, use it
    entities = beat.get("entities", [])
    if entities:
        return str(entities[0])

    raw_id = node.get("node_id", "").split(":")[-2] if ":" in node.get("node_id", "") else node.get("node_id", "")
    clean = raw_id.replace("_", " ").title()
    if any(bad in clean.lower() for bad in ("present the", "identity metadata", "prompt")):
        return beat.get("subject", "Tư liệu lịch sử")
    return clean


COLOR_NAME_MAP: dict[str, str] = {
    "muted_red": "#C84B31",
    "red": "#D9534F",
    "gold": "#E6C280",
    "yellow": "#F0AD4E",
    "blue": "#4A90E2",
    "dark_blue": "#2D4263",
    "green": "#5CB85C",
    "forest_green": "#2E7D32",
    "white": "#FFFFFF",
    "gray": "#888888",
    "slate": "#1E2228",
}


def _resolve_hex_color(val: str | None, default: str = "#E6C280") -> str:
    """Resolve semantic color names or raw hex strings into valid SVG/CSS hex color."""
    if not val:
        return default
    if val.startswith("#") and len(val) in (4, 7, 9):
        return val
    lower = val.lower().strip()
    if lower in COLOR_NAME_MAP:
        return COLOR_NAME_MAP[lower]
    if len(val) in (3, 6, 8) and all(c in "0123456789abcdefABCDEF" for c in val):
        return "#" + val
    return default


def build_episode_frame_plan(
    timeline: dict,
    geometry_plans: list[dict],
    motion_plan: dict | None = None,
    media_assets: list[dict] | None = None,
    visual_compositions: list[dict] | None = None,
    art_direction: dict | None = None,
    semantic_beats: list[dict] | None = None,
    editorial_intents: dict[str, Any] | list[dict[str, Any]] | None = None,
    editorial_overrides: list[dict[str, Any]] | None = None,
) -> EpisodeFramePlan:
    """Build a deterministic, pure-Python frame plan from planning pipeline artifacts."""
    canvas_info = timeline.get("canvas", {})
    canvas_w = int(canvas_info.get("width", 1920))
    canvas_h = int(canvas_info.get("height", 1080))
    fps = 30
    total_duration = float(timeline.get("total_duration_sec", 0.0))

    geo_by_beat = {p["beat_id"]: p for p in geometry_plans}
    motion_by_beat = {p["beat_id"]: p for p in (motion_plan or {}).get("plans", [])}
    asset_by_id = {a["asset_id"]: a for a in (media_assets or [])}
    beat_by_id = {b["beat_id"]: b for b in (semantic_beats or [])}

    # Normalize editorial_intents into dict by beat_id
    intents_by_beat: dict[str, Any] = {}
    if isinstance(editorial_intents, dict):
        if "items" in editorial_intents and isinstance(editorial_intents["items"], list):
            for item in editorial_intents["items"]:
                if isinstance(item, dict) and "beat_id" in item:
                    intents_by_beat[item["beat_id"]] = item
        else:
            intents_by_beat = dict(editorial_intents)
    elif isinstance(editorial_intents, list):
        for item in editorial_intents:
            if isinstance(item, dict) and "beat_id" in item:
                intents_by_beat[item["beat_id"]] = item
            elif hasattr(item, "beat_id"):
                intents_by_beat[item.beat_id] = item

    # Color palette
    raw_accent = (art_direction or {}).get("accent", {}).get("primary", "#E6C280")
    accent = _resolve_hex_color(raw_accent, default="#E6C280")

    # Generate ASS subtitles for the episode
    subtitles_ass = generate_subtitles_ass(timeline, canvas=canvas_info)

    beat_plans: list[BeatFramePlan] = []
    segments = timeline.get("segments", [])

    for segment in segments:
        beat_id = segment["beat_id"]
        start_sec = float(segment["start_sec"])
        end_sec = float(segment["end_sec"])
        duration = max(0.1, end_sec - start_sec)
        visual_family = segment.get("visual_family", "full_frame_cinematic")
        trans_in = segment.get("transition_in", "CONTINUATION")
        trans_out = segment.get("transition_out", "CONTINUATION")

        geo_plan = geo_by_beat.get(beat_id)
        comp_motion = motion_by_beat.get(beat_id, {})
        camera_behavior = comp_motion.get("camera_behavior", "stable")
        beat_info = beat_by_id.get(beat_id, {})
        beat_intent = intents_by_beat.get(beat_id)

        # Build motion events map by layer
        emphasis_by_layer: dict[str, dict] = {}
        for ev in comp_motion.get("events", []):
            if ev.get("kind") == "EMPHASIS":
                emphasis_by_layer[ev["layer_id"]] = ev

        media_elements: list[MediaRenderElement] = []
        text_elements: list[TextRenderElement] = []
        placement_px_by_node: dict[str, PixelRect] = {}

        if geo_plan:
            node_map = {n["node_id"]: n for n in geo_plan.get("nodes", [])}
            placements = sorted(geo_plan.get("solved_placements", []), key=lambda p: p.get("z_index", 0))

            for placement in placements:
                node_id = placement["node_id"]
                node = node_map.get(node_id, {})
                bounds_norm = placement["bounds"]
                bounds_px = _norm_to_px_rect(bounds_norm, canvas_w, canvas_h)
                placement_px_by_node[node_id] = bounds_px
                z_index = int(placement.get("z_index", 0))
                role = node.get("role", "HERO")
                asset_id = node.get("asset_id")

                # Is this an image/asset-backed node?
                is_media_role = (
                    role in {VisualRole.HERO.value, VisualRole.PORTRAIT.value,
                             VisualRole.DOCUMENT.value, VisualRole.MAP.value,
                             VisualRole.ARCHIVAL_IMAGE.value, "HERO", "PORTRAIT",
                             "DOCUMENT", "MAP", "ARCHIVAL_IMAGE"}
                    or asset_id is not None
                )

                if is_media_role and (asset_id is not None or not node.get("text_role")):
                    asset = asset_by_id.get(asset_id) if asset_id else None
                    checksum = asset.get("checksum") if asset else None
                    is_placeholder = asset.get("is_placeholder", False) if asset else True
                    desc = asset.get("description", "") if asset else (node.get("semantic_refs", [""])[0] if node.get("semantic_refs") else "")

                    # Check for emphasis motion event on this node or source layer
                    src_layer = node.get("source_layer_id", node_id)
                    emp_ev = emphasis_by_layer.get(src_layer) or emphasis_by_layer.get(node_id)

                    camera_motion = "STABLE"
                    emp_start = None
                    emp_end = None
                    keyframes = []

                    if emp_ev is not None:
                        camera_motion = "KEN_BURNS_ZOOM_IN"
                        emp_start = float(emp_ev.get("start_sec", start_sec))
                        emp_end = float(emp_ev.get("end_sec", end_sec))
                        rel_emp_start = max(0.0, emp_start - start_sec)
                        rel_emp_end = min(duration, emp_end - start_sec)

                        keyframes = [
                            Keyframe(time_offset_sec=0.0, scale=1.0, pan_x=0.0, pan_y=0.0, opacity=1.0),
                            Keyframe(time_offset_sec=rel_emp_start, scale=1.0, pan_x=0.0, pan_y=0.0, opacity=1.0),
                            Keyframe(time_offset_sec=rel_emp_end, scale=1.08, pan_x=0.01, pan_y=0.01, opacity=1.0),
                            Keyframe(time_offset_sec=duration, scale=1.08, pan_x=0.01, pan_y=0.01, opacity=1.0),
                        ]
                    elif camera_behavior == "slow_push":
                        camera_motion = "SLOW_PUSH"
                        keyframes = [
                            Keyframe(time_offset_sec=0.0, scale=1.0, pan_x=0.0, pan_y=0.0, opacity=1.0),
                            Keyframe(time_offset_sec=duration, scale=1.06, pan_x=0.0, pan_y=0.0, opacity=1.0),
                        ]
                    else:
                        keyframes = [
                            Keyframe(time_offset_sec=0.0, scale=1.0, pan_x=0.0, pan_y=0.0, opacity=1.0),
                            Keyframe(time_offset_sec=duration, scale=1.0, pan_x=0.0, pan_y=0.0, opacity=1.0),
                        ]

                    media_elements.append(MediaRenderElement(
                        element_id=node_id,
                        asset_id=asset_id,
                        checksum=checksum,
                        media_kind=node.get("media_kind", asset.get("kind", "photo") if asset else "photo"),
                        role=role,
                        is_placeholder=is_placeholder,
                        z_index=z_index,
                        bounds_norm=bounds_norm,
                        bounds_px=bounds_px,
                        entrance_sec=start_sec,
                        exit_sec=end_sec,
                        description=desc,
                        emphasis_start_sec=emp_start,
                        emphasis_end_sec=emp_end,
                        camera_motion=camera_motion,
                        keyframes=keyframes,
                    ))
                else:
                    # Text / Graphic Node
                    text_role_val = node.get("text_role", "LABEL") or "LABEL"
                    content_source = "raw"
                    text_str = ""

                    # 1. Check editorial overrides
                    if editorial_overrides:
                        for ovr in editorial_overrides:
                            if ovr.get("target_id") == node_id and ovr.get("field") == "caption":
                                text_str = ovr.get("new_value", "")
                                content_source = "override"
                                break
                            elif ovr.get("beat_id") == beat_id and ovr.get("target_id") in (node_id, role, (node.get("semantic_refs") or [""])[0]):
                                text_str = ovr.get("new_value", "")
                                content_source = "override"
                                break

                    # 2. Check AI proposed captions (if no override applied)
                    if not text_str and beat_intent:
                        captions = (
                            beat_intent.get("captions", {})
                            if isinstance(beat_intent, dict)
                            else getattr(beat_intent, "captions", {})
                        )
                        cand_caption = captions.get(node_id)
                        if not cand_caption:
                            for ref in node.get("semantic_refs", []):
                                if ref in captions:
                                    cand_caption = captions[ref]
                                    break
                                for k, v in captions.items():
                                    if k.lower() == ref.lower():
                                        cand_caption = v
                                        break
                                if cand_caption:
                                    break

                        if cand_caption:
                            from videotool.editorial.director.caption_validator import validate_caption
                            is_valid, _ = validate_caption(
                                caption=cand_caption,
                                narration_text=beat_info.get("narration_text", "") if isinstance(beat_info, dict) else getattr(beat_info, "narration_text", ""),
                                entities=beat_info.get("entities", []) if isinstance(beat_info, dict) else getattr(beat_info, "entities", []),
                                locations=beat_info.get("locations", []) if isinstance(beat_info, dict) else getattr(beat_info, "locations", []),
                                dates=beat_info.get("dates", []) if isinstance(beat_info, dict) else getattr(beat_info, "dates", []),
                                text_role=text_role_val,
                            )
                            if is_valid:
                                text_str = cand_caption
                                content_source = "ai_authored"

                    # 3. Fallback to deterministic raw entity text extraction
                    if not text_str:
                        text_str = _extract_quote_or_label_text(node, beat_info)
                        content_source = "raw"

                    style_name = "NodeLabel"
                    if text_role_val == "QUOTE" or role == "QUOTE":
                        style_name = "NodeQuote"
                    elif text_role_val in ("DATE", "TIMELINE_NODE") or role == "TIMELINE_NODE":
                        style_name = "NodeTimeline"

                    # For paper_collage_hero beats, vector SVG handles typography cleanly; suppress duplicate ASS labels
                    ass_line = "" if visual_family == "paper_collage_hero" else generate_node_text_dialogue(
                        text=text_str,
                        start_sec=start_sec,
                        end_sec=end_sec,
                        center_x_px=bounds_px.center_x,
                        center_y_px=bounds_px.center_y,
                        style_name=style_name,
                    )

                    text_elements.append(TextRenderElement(
                        element_id=node_id,
                        text=text_str,
                        role=role,
                        text_role=text_role_val,
                        content_source=content_source,
                        z_index=z_index,
                        bounds_norm=bounds_norm,
                        bounds_px=bounds_px,
                        entrance_sec=start_sec,
                        exit_sec=end_sec,
                        style_name=style_name,
                        ass_dialogue=ass_line,
                    ))

            # Connectors (VisualEdge)
            connectors: list[ConnectorRenderElement] = []
            for edge in geo_plan.get("edges", []):
                src_id = edge["source_node_id"]
                tgt_id = edge["target_node_id"]
                src_px = placement_px_by_node.get(src_id)
                tgt_px = placement_px_by_node.get(tgt_id)

                if src_px is not None and tgt_px is not None:
                    rel_type = edge.get("relationship_type", "CAUSES")
                    style_hint = edge.get("connector_style_hint", "semantic")
                    directed = edge.get("directed", True)
                    is_dashed = rel_type in ("ROUTE_TO", "ASSOCIATED_WITH") or style_hint == "dashed"

                    connectors.append(ConnectorRenderElement(
                        connector_id=edge.get("edge_id", f"{src_id}->{tgt_id}"),
                        source_node_id=src_id,
                        target_node_id=tgt_id,
                        relationship_type=rel_type,
                        connector_style_hint=style_hint,
                        directed=directed,
                        start_px=(float(src_px.center_x), float(src_px.center_y)),
                        end_px=(float(tgt_px.center_x), float(tgt_px.center_y)),
                        is_dashed=is_dashed,
                        stroke_width=4.0,
                        color=accent,
                    ))

        # Dynamic Vox Collage styling for editorial excellence
        from videotool.render.vox_collage import VoxCollageData
        chap_num = getattr(beat_info, "chapter", None) or segment.get("chapter") or ((len(beat_plans) // 2) + 1)
        chap_str = f"CHƯƠNG {chap_num}"

        # 1. Dynamic Headline
        headline_raw = (
            segment.get("headline")
            or beat_info.get("headline")
            or segment.get("title")
            or (beat_intent.get("title") if isinstance(beat_intent, dict) else getattr(beat_intent, "title", None))
        )
        if isinstance(headline_raw, list):
            headline_parts = [str(l).strip().upper() for l in headline_raw if str(l).strip()]
        elif headline_raw:
            headline_parts = [l.strip().upper() for l in str(headline_raw).splitlines() if l.strip()]
            if len(headline_parts) == 1 and len(headline_parts[0]) > 18:
                words = headline_parts[0].split()
                mid = len(words) // 2
                headline_parts = [" ".join(words[:mid]), " ".join(words[mid:])]
        else:
            entities = (beat_info.get("entities", []) if isinstance(beat_info, dict) else getattr(beat_info, "entities", [])) or []
            subj = timeline.get("topic") or beat_info.get("subject") or timeline.get("episode_id", "").replace("_", " ")
            e1 = str(entities[0]).upper() if entities else str(subj).upper()
            if len(e1) > 22:
                words = e1.split()
                mid = max(1, len(words) // 2)
                headline_parts = [" ".join(words[:mid]), " ".join(words[mid:])]
            else:
                headline_parts = [e1, "DIỄN BIẾN LỊCH SỬ"]

        if not headline_parts:
            headline_parts = [str(timeline.get("topic") or timeline.get("episode_id", "")).upper()[:22], "SỰ KIỆN TRỌNG TÂM"]

        # 2. Dynamic Body Paragraph
        body_txt = (
            (beat_info.get("narration_text", "") if isinstance(beat_info, dict) else getattr(beat_info, "narration_text", ""))
            or (beat_info.get("summary", "") if isinstance(beat_info, dict) else getattr(beat_info, "summary", ""))
            or ""
        )

        # 3. Dynamic Fact Card (Date, Title, Subtitle)
        dates = (beat_info.get("dates", []) if isinstance(beat_info, dict) else getattr(beat_info, "dates", [])) or []
        entities = (beat_info.get("entities", []) if isinstance(beat_info, dict) else getattr(beat_info, "entities", [])) or []
        date_m = dates[0] if dates else ""
        date_t = entities[0].upper() if entities else timeline.get("episode_id", "").replace("_", " ").upper()
        date_sub = entities[1].upper() if len(entities) > 1 else "TƯ LIỆU LỊCH SỬ"

        # 4. Dynamic Quote & Emphasis Keywords
        q_text = ""
        q_emp = []
        if beat_intent and isinstance(beat_intent, dict) and "quote" in beat_intent:
            q_text = beat_intent["quote"].get("text", "")
            q_emp = beat_intent["quote"].get("emphasis", [])
        elif hasattr(beat_intent, "quote") and getattr(beat_intent, "quote"):
            q_data = getattr(beat_intent, "quote")
            q_text = q_data.get("text", "") if isinstance(q_data, dict) else getattr(q_data, "text", "")
            q_emp = q_data.get("emphasis", []) if isinstance(q_data, dict) else getattr(q_data, "emphasis", [])

        if not q_text and text_elements:
            for te in text_elements:
                if te.style_name == "NodeQuote":
                    q_text = te.text
                    q_emp = [e for e in entities if e.lower() in q_text.lower()]
                    break

        if not q_text and body_txt:
            sentences = [s.strip() for s in re.split(r"[.!?]+", body_txt) if len(s.strip()) > 10]
            if sentences:
                q_text = sentences[0]
                words = q_text.split()
                q_emp = [w for w in words if len(w) > 4][:2]

        insets_info = []
        for me in media_elements:
            if me.role != "HERO":
                insets_info.append({
                    "x": float(me.bounds_px.x),
                    "y": float(me.bounds_px.y),
                    "w": float(me.bounds_px.width),
                    "h": float(me.bounds_px.height),
                    "taped": True,
                })

        collage_data = VoxCollageData(
            beat_id=beat_id,
            chapter_text=chap_str,
            headline_lines=headline_parts,
            body_paragraph=body_txt,
            date_milestone=date_m,
            date_title=date_t,
            date_subtitle=date_sub,
            quote_text=q_text,
            quote_emphasis=q_emp,
            insets=insets_info,
            accent_color=accent,
        )

        # SVG Overlay (connectors, text node cards/badges, or full paper collage)
        svg_overlay = generate_svg_overlay(
            connectors=connectors,
            text_elements=text_elements,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            accent_color=accent,
            visual_family=visual_family,
            collage_data=collage_data,
        )

        beat_plans.append(BeatFramePlan(
            beat_id=beat_id,
            start_sec=start_sec,
            end_sec=end_sec,
            duration_sec=duration,
            visual_family=visual_family,
            camera_behavior=camera_behavior,
            media_elements=media_elements,
            text_elements=text_elements,
            connectors=connectors,
            svg_overlay_content=svg_overlay,
            transition_in=trans_in,
            transition_out=trans_out,
        ))

    return EpisodeFramePlan(
        episode_id=timeline.get("episode_id", "episode"),
        canvas_width=canvas_w,
        canvas_height=canvas_h,
        fps=fps,
        total_duration_sec=total_duration,
        beats=beat_plans,
        subtitles_ass=subtitles_ass,
    )
