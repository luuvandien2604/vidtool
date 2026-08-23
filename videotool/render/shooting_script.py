"""Shooting script generator (Phase 3A / AI Editorial Director).

Produces two synced artifacts:
1. shooting_script.json - machine-readable source of truth containing every element per beat
   with real timestamps, coordinates, motion, source tracking ([raw] vs [ai_authored]), and asset links.
2. shooting_script.md - human-readable 13-column markdown table generated directly from the script data.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from videotool.render.frame_plan import (
    BeatFramePlan,
    ConnectorRenderElement,
    EpisodeFramePlan,
    MediaRenderElement,
    TextRenderElement,
)


def _format_time(sec: float) -> str:
    """Format seconds into M:SS.SS format."""
    m = int(sec // 60)
    s = sec % 60
    return f"{m}:{s:05.2f}"


def build_shooting_script_data(
    plan: EpisodeFramePlan,
    timeline: dict[str, Any],
    semantic_beats: list[dict[str, Any]],
    geometry_plans: list[dict[str, Any]] | None = None,
    media_assets: list[dict[str, Any]] | None = None,
    visual_compositions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Construct the canonical, machine-readable shooting script dictionary."""
    beat_meta_by_id = {b["beat_id"]: b for b in semantic_beats}
    geo_by_beat = {g["beat_id"]: g for g in (geometry_plans or [])}
    asset_by_id = {a["asset_id"]: a for a in (media_assets or [])}
    comp_by_beat = {c["beat_id"]: c for c in (visual_compositions or [])}

    script_beats = []

    for beat_plan in plan.beats:
        b_id = beat_plan.beat_id
        b_meta = beat_meta_by_id.get(b_id, {})
        geo_plan = geo_by_beat.get(b_id, {})
        comp_plan = comp_by_beat.get(b_id, {})

        node_map = {n["node_id"]: n for n in geo_plan.get("nodes", [])}
        placement_map = {p["node_id"]: p for p in geo_plan.get("solved_placements", [])}

        elements = []
        elem_idx = 1

        # 1. Media Elements
        for m_elem in beat_plan.media_elements:
            node = node_map.get(m_elem.element_id, {})
            placement = placement_map.get(m_elem.element_id, {})
            asset = asset_by_id.get(m_elem.asset_id) if m_elem.asset_id else None

            region = placement.get("region", "CENTER")
            b_norm = m_elem.bounds_norm
            coords_str = f"{b_norm.get('x', 0.0):.2f},{b_norm.get('y', 0.0):.2f},{b_norm.get('width', 1.0):.2f},{b_norm.get('height', 1.0):.2f}"

            asset_provider = asset.get("provider", "fixture") if asset else ("placeholder" if m_elem.is_placeholder else "archive")
            asset_ref = m_elem.asset_id or "(none)"
            if m_elem.is_placeholder:
                display_content = f"*(placeholder - {m_elem.description or m_elem.media_kind})*"
                content_src = "placeholder"
            else:
                display_content = f"*(ảnh {m_elem.media_kind}: {m_elem.description or m_elem.asset_id})*"
                content_src = "archive"

            importance = node.get("importance", 0.8)
            reason = f"importance {importance:.2f}" if importance else "hero visual"

            elements.append({
                "index": elem_idx,
                "element_id": m_elem.element_id,
                "element_type": f"Media ({m_elem.media_kind})",
                "role": m_elem.role,
                "display_content": display_content,
                "content_source": content_src,
                "asset_provider": asset_provider,
                "asset_id": asset_ref,
                "region": region,
                "bounds_norm": coords_str,
                "bounds_px": m_elem.bounds_px.to_dict(),
                "entrance_sec": round(m_elem.entrance_sec, 2),
                "exit_sec": round(m_elem.exit_sec, 2),
                "motion": m_elem.camera_motion.lower(),
                "connects_to": "—",
                "semantic_reason": reason,
            })
            elem_idx += 1

        # 2. Text / Graphic Elements
        for t_elem in beat_plan.text_elements:
            node = node_map.get(t_elem.element_id, {})
            placement = placement_map.get(t_elem.element_id, {})

            region = placement.get("region", "CENTER")
            b_norm = t_elem.bounds_norm
            coords_str = f"{b_norm.get('x', 0.0):.2f},{b_norm.get('y', 0.0):.2f},{b_norm.get('width', 1.0):.2f},{b_norm.get('height', 1.0):.2f}"

            type_desc = f"Text badge ({t_elem.text_role})" if t_elem.text_role != "QUOTE" else "Text card (QUOTE)"
            source_tag = f"[{t_elem.content_source}]"

            # Check if this node connects to another node
            connects_list = []
            for c_elem in beat_plan.connectors:
                if c_elem.source_node_id == t_elem.element_id:
                    connects_list.append(f"→ {c_elem.target_node_id.split(':')[-1]} (`{c_elem.relationship_type}`)")
            connects_str = ", ".join(connects_list) if connects_list else "—"

            reason = node.get("semantic_refs", [""])[0] or t_elem.role.lower()

            elements.append({
                "index": elem_idx,
                "element_id": t_elem.element_id,
                "element_type": type_desc,
                "role": t_elem.role,
                "display_content": f'**"{t_elem.text}"**',
                "content_source": source_tag,
                "asset_provider": "—",
                "asset_id": "—",
                "region": region,
                "bounds_norm": coords_str,
                "bounds_px": t_elem.bounds_px.to_dict(),
                "entrance_sec": round(t_elem.entrance_sec, 2),
                "exit_sec": round(t_elem.exit_sec, 2),
                "motion": "fade-in ~0.4s",
                "connects_to": connects_str,
                "semantic_reason": f"anchor '{reason}'",
            })
            elem_idx += 1

        # 3. Connectors
        for c_elem in beat_plan.connectors:
            src_short = c_elem.source_node_id.split(":")[-1]
            tgt_short = c_elem.target_node_id.split(":")[-1]

            elements.append({
                "index": elem_idx,
                "element_id": c_elem.connector_id,
                "element_type": "Connector",
                "role": "CONNECTOR",
                "display_content": "*(đường có hướng)*" if c_elem.directed else "*(đường liên kết)*",
                "content_source": "—",
                "asset_provider": "—",
                "asset_id": "—",
                "region": "—",
                "bounds_norm": f"nối ({src_short})→({tgt_short})",
                "bounds_px": {},
                "entrance_sec": round(beat_plan.start_sec + 0.3, 2),
                "exit_sec": round(beat_plan.end_sec, 2),
                "motion": "draw-in",
                "connects_to": f"{src_short} → {tgt_short}",
                "semantic_reason": f"`{c_elem.relationship_type}`",
            })
            elem_idx += 1

        strategy_name = comp_plan.get("strategy", beat_plan.visual_family)

        script_beats.append({
            "beat_id": b_id,
            "start_sec": round(beat_plan.start_sec, 2),
            "end_sec": round(beat_plan.end_sec, 2),
            "duration_sec": round(beat_plan.duration_sec, 2),
            "visual_family": beat_plan.visual_family,
            "strategy": strategy_name,
            "narration_text": b_meta.get("narration_text", ""),
            "transition_in": beat_plan.transition_in,
            "transition_out": beat_plan.transition_out,
            "elements": elements,
        })

    return {
        "episode_id": plan.episode_id,
        "total_duration_sec": round(plan.total_duration_sec, 2),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "beats": script_beats,
    }


def render_shooting_script_markdown(script_data: dict[str, Any]) -> str:
    """Render the shooting_script.md Markdown document directly from script dictionary."""
    lines = [
        f"# Shooting Script: {script_data.get('episode_id', 'Episode')}",
        f"**Total Duration**: {script_data.get('total_duration_sec', 0.0)}s | **Generated**: {script_data.get('generated_at', '')}",
        "",
        "---",
        "",
    ]

    for i, beat in enumerate(script_data.get("beats", []), start=1):
        b_id = beat["beat_id"]
        t_start = _format_time(beat["start_sec"])
        t_end = _format_time(beat["end_sec"])
        family = beat["visual_family"]
        strat = beat["strategy"]
        narration = beat["narration_text"]
        trans_out = beat.get("transition_out", "CONTINUATION")

        lines.append(f"### Beat {i:02d} (`{b_id}`) — [{t_start} .. {t_end}] | {family} (`{strat}`)")
        lines.append(f'**Narration**: "{narration}"')
        lines.append("")
        lines.append("| # | Element ID | Loại | Nội dung hiển thị | Nguồn nội dung | Asset/nguồn ảnh | Vùng đặt | Tọa độ (x,y,w,h) | Vào lúc | Ra lúc | Chuyển động | Nối tới | Lý do (semantic) |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")

        for elem in beat.get("elements", []):
            idx = elem["index"]
            elem_id = f"`{elem['element_id']}`"
            el_type = elem["element_type"]
            display = elem["display_content"]
            source = elem["content_source"]
            asset_info = f"`{elem['asset_id']}`" if elem['asset_id'] != "—" else "—"
            region = elem["region"]
            coords = elem["bounds_norm"]
            t_in = _format_time(elem["entrance_sec"])
            t_out = _format_time(elem["exit_sec"])
            motion = elem["motion"]
            connects = elem["connects_to"]
            reason = elem["semantic_reason"]

            lines.append(
                f"| {idx} | {elem_id} | {el_type} | {display} | {source} | {asset_info} | {region} | {coords} | {t_in} | {t_out} | {motion} | {connects} | {reason} |"
            )

        lines.append("")
        lines.append(f"*Chuyển cảnh tiếp theo: {trans_out}*")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def generate_shooting_script(
    plan: EpisodeFramePlan,
    timeline: dict[str, Any],
    semantic_beats: list[dict[str, Any]],
    geometry_plans: list[dict[str, Any]] | None = None,
    media_assets: list[dict[str, Any]] | None = None,
    visual_compositions: list[dict[str, Any]] | None = None,
    out_json_path: str | Path | None = None,
    out_md_path: str | Path | None = None,
    out_yaml_path: str | Path | None = None,  # Legacy alias redirected to JSON
) -> tuple[dict[str, Any], str]:
    """Generate both shooting_script.json and shooting_script.md files."""
    script_data = build_shooting_script_data(
        plan=plan,
        timeline=timeline,
        semantic_beats=semantic_beats,
        geometry_plans=geometry_plans,
        media_assets=media_assets,
        visual_compositions=visual_compositions,
    )

    md_content = render_shooting_script_markdown(script_data)

    target_json_path = out_json_path or out_yaml_path
    if target_json_path:
        p_json = Path(target_json_path)
        p_json.parent.mkdir(parents=True, exist_ok=True)
        with open(p_json, "w", encoding="utf-8") as f:
            json.dump(script_data, f, indent=2, ensure_ascii=False)

    if out_md_path:
        p_md = Path(out_md_path)
        p_md.parent.mkdir(parents=True, exist_ok=True)
        with open(p_md, "w", encoding="utf-8") as f:
            f.write(md_content)

    return script_data, md_content
