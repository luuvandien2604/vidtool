"""Master Timeline Assembly Domain Model (Stage 8).

Manages stitching individual scene MP4 videos, organic transitions (paper whip, cuts),
audio alignment, and burned-in subtitle coordination.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MasterSceneItem:
    scene_index: int
    scene_id: str
    video_file_path: str
    duration_sec: float
    transition_type: str = "cut"  # "cut" | "paper_whip" | "fade_black" | "crossdissolve"
    transition_duration_sec: float = 0.35
    chapter_index: int = 1
    chapter_title: str = ""


@dataclass
class MasterTimelineSpec:
    project_id: str
    title: str
    total_scenes: int
    total_duration_sec: float
    scenes: list[MasterSceneItem] = field(default_factory=list)
    audio_master_path: str | None = None
    subtitles_ass_path: str | None = None
    output_master_video_path: str = "artifacts/master_documentary_final.mp4"

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "total_scenes": self.total_scenes,
            "total_duration_sec": self.total_duration_sec,
            "scenes": [
                {
                    "scene_index": s.scene_index,
                    "scene_id": s.scene_id,
                    "video_file_path": s.video_file_path,
                    "duration_sec": s.duration_sec,
                    "transition_type": s.transition_type,
                    "transition_duration_sec": s.transition_duration_sec,
                    "chapter_index": s.chapter_index,
                    "chapter_title": s.chapter_title,
                }
                for s in self.scenes
            ],
            "audio_master_path": self.audio_master_path,
            "subtitles_ass_path": self.subtitles_ass_path,
            "output_master_video_path": self.output_master_video_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MasterTimelineSpec:
        scenes = [
            MasterSceneItem(
                scene_index=int(s.get("scene_index", idx + 1)),
                scene_id=s.get("scene_id", f"scene_{idx+1:02d}"),
                video_file_path=s.get("video_file_path", ""),
                duration_sec=float(s.get("duration_sec", 6.0)),
                transition_type=s.get("transition_type", "cut"),
                transition_duration_sec=float(s.get("transition_duration_sec", 0.35)),
                chapter_index=int(s.get("chapter_index", 1)),
                chapter_title=s.get("chapter_title", ""),
            )
            for idx, s in enumerate(data.get("scenes", []))
        ]
        return cls(
            project_id=data.get("project_id", "project"),
            title=data.get("title", ""),
            total_scenes=int(data.get("total_scenes", len(scenes))),
            total_duration_sec=float(data.get("total_duration_sec", 0.0)),
            scenes=scenes,
            audio_master_path=data.get("audio_master_path"),
            subtitles_ass_path=data.get("subtitles_ass_path"),
            output_master_video_path=data.get("output_master_video_path", "artifacts/master_documentary_final.mp4"),
        )
