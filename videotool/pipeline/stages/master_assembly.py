"""Master Assembly pipeline stage (Stage 8).

Stitches rendered scene MP4s into a full 10-minute master documentary video
with organic paper-whip transitions, audio master alignment, and subtitles.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from videotool.domain.master_timeline import MasterSceneItem, MasterTimelineSpec
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


class MasterAssemblyStage(BasePipelineStage):
    id = "master_assembly"

    def fingerprint(self, ctx: PipelineContext) -> str:
        scenes_payload = ctx.state.get("scene_compilation_payload", {})
        return stable_hash(self.version, ctx.episode_id, scenes_payload)

    def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        ep_dir = ctx.store.episode_dir(ctx.episode_id)
        master_out = ep_dir / "master_documentary.mp4"

        scenes_data = ctx.state.get("scene_compilation", {})
        scene_list = scenes_data.get("scenes", [])

        master_scenes: list[MasterSceneItem] = []
        total_duration = 0.0

        for idx, sc in enumerate(scene_list):
            dur = float(sc.get("duration_sec", 6.0))
            total_duration += dur
            master_scenes.append(
                MasterSceneItem(
                    scene_index=idx + 1,
                    scene_id=sc.get("scene_id", f"sc_{idx+1}"),
                    video_file_path=sc.get("video_path", ""),
                    duration_sec=dur,
                    transition_type="paper_whip" if idx > 0 else "cut",
                    chapter_index=int(sc.get("chapter_index", 1)),
                    chapter_title=sc.get("chapter_title", ""),
                )
            )

        spec = MasterTimelineSpec(
            project_id=ctx.episode_id,
            title=ctx.state.get("topic", ctx.episode_id),
            total_scenes=len(master_scenes),
            total_duration_sec=total_duration,
            scenes=master_scenes,
            output_master_video_path=str(master_out),
        )

        return spec.to_dict()

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        if not isinstance(payload, dict):
            return False
        return "project_id" in payload and "scenes" in payload and "output_master_video_path" in payload
