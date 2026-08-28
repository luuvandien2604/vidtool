"""Unit and integration tests for the 8-Stage Hierarchical Micro-Pipeline Architecture."""
from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from videotool.domain.fact_registry import FactItem, FactRegistry, HistoricalEntity
from videotool.domain.story_structure import ChapterOutline, MacroStoryArc
from videotool.domain.micro_script import BeatScript, ChapterScript
from videotool.domain.master_timeline import MasterSceneItem, MasterTimelineSpec
from videotool.pipeline.stages.fact_registry import FactRegistryStage
from videotool.pipeline.stages.chapter_outline import ChapterOutlineStage
from videotool.pipeline.stages.chapter_scriptwriting import ChapterScriptwritingStage
from videotool.pipeline.stages.scene_compilation import SceneCompilationStage
from videotool.pipeline.stages.master_assembly import MasterAssemblyStage
from videotool.pipeline.context import PipelineContext
from videotool.artifacts import ArtifactStore


def test_fact_registry_model_serialization():
    registry = FactRegistry(
        project_id="test_ep",
        topic="Sự kiện lịch sử",
        central_thesis="Phim tài liệu điều tra",
        entities=[
            HistoricalEntity(
                name="Nhân chứng A",
                category="person",
                role="Nhân chứng lịch sử",
            )
        ],
        facts=[
            FactItem(
                id="f01",
                statement="Bức tường được xây dựng trong đêm.",
                historical_date="13/08/1961",
                confidence=1.0,
            )
        ],
    )
    d = registry.to_dict()
    assert d["project_id"] == "test_ep"
    assert len(d["facts"]) == 1
    assert d["facts"][0]["historical_date"] == "13/08/1961"

    restored = FactRegistry.from_dict(d)
    assert restored.project_id == "test_ep"
    assert restored.entities[0].name == "Nhân chứng A"


def test_story_structure_time_budgeting():
    arc = MacroStoryArc(
        project_id="test_ep",
        title="Tài liệu 10 phút",
        target_total_duration_sec=600.0,
        chapters=[
            ChapterOutline(
                chapter_index=1,
                chapter_id="ch01",
                title="Bối cảnh",
                narrative_goal="Setup",
                target_duration_sec=120.0,
                start_time_sec=0.0,
                end_time_sec=120.0,
                emotional_tone="investigative",
            ),
            ChapterOutline(
                chapter_index=2,
                chapter_id="ch02",
                title="Đỉnh điểm",
                narrative_goal="Crisis",
                target_duration_sec=180.0,
                start_time_sec=120.0,
                end_time_sec=300.0,
                emotional_tone="tense",
            ),
        ],
    )
    d = arc.to_dict()
    assert len(d["chapters"]) == 2
    assert d["chapters"][1]["target_duration_sec"] == 180.0

    restored = MacroStoryArc.from_dict(d)
    assert restored.chapters[0].chapter_id == "ch01"


def test_micro_scripting_beat_chunking():
    script = ChapterScript(
        chapter_id="ch01",
        chapter_index=1,
        title="Bối cảnh ra đời",
        beats=[
            BeatScript(
                beat_id="b01",
                beat_index=1,
                narration_text="Bối cảnh ra đời của sự kiện.",
                target_duration_sec=6.0,
                semantic_function="ESTABLISHING_CONTEXT",
                emphasis_keywords=["bối cảnh", "sự kiện"],
                pause_after_sec=0.5,
            )
        ],
    )
    d = script.to_dict()
    assert d["chapter_id"] == "ch01"
    assert len(d["beats"]) == 1
    assert "bối cảnh" in d["beats"][0]["emphasis_keywords"]

    restored = ChapterScript.from_dict(d)
    assert restored.beats[0].semantic_function == "ESTABLISHING_CONTEXT"


def test_master_timeline_assembly_spec():
    spec = MasterTimelineSpec(
        project_id="test_ep",
        title="Master Title",
        total_scenes=2,
        total_duration_sec=12.0,
        scenes=[
            MasterSceneItem(
                scene_index=1,
                scene_id="sc01",
                video_file_path="scenes/sc01.mp4",
                duration_sec=6.0,
                transition_type="cut",
            ),
            MasterSceneItem(
                scene_index=2,
                scene_id="sc02",
                video_file_path="scenes/sc02.mp4",
                duration_sec=6.0,
                transition_type="paper_whip",
            ),
        ],
    )
    d = spec.to_dict()
    assert d["total_scenes"] == 2
    assert d["scenes"][1]["transition_type"] == "paper_whip"

    restored = MasterTimelineSpec.from_dict(d)
    assert len(restored.scenes) == 2


def test_hierarchical_stages_execution():
    with tempfile.TemporaryDirectory() as tmpdir:
        from videotool.domain.narration import Narration
        from videotool.pipeline.context import EpisodeInput

        store = ArtifactStore(tmpdir)
        ep = EpisodeInput(
            episode_id="test_hierarchical_ep",
            subject="Bức tường lịch sử",
            narration=Narration(text="Lời thuyết minh mẫu."),
        )
        ctx = PipelineContext(
            episode=ep,
            store=store,
        )
        ctx.state = {"topic": "Bức tường lịch sử", "raw_script_text": "Lời thuyết minh mẫu."}

        # Stage 1: Fact Registry
        stage1 = FactRegistryStage()
        fact_payload = stage1.execute(ctx)
        assert stage1.validate(fact_payload, ctx)
        ctx.state["fact_registry"] = fact_payload
        ctx.state["fact_registry_payload"] = fact_payload

        # Stage 2: Chapter Outline
        stage2 = ChapterOutlineStage()
        outline_payload = stage2.execute(ctx)
        assert stage2.validate(outline_payload, ctx)
        ctx.state["chapter_outline"] = outline_payload
        ctx.state["chapter_outline_payload"] = outline_payload

        # Stage 3: Chapter Scriptwriting
        stage3 = ChapterScriptwritingStage()
        scripts_payload = stage3.execute(ctx)
        assert stage3.validate(scripts_payload, ctx)
        ctx.state["chapter_scripts"] = scripts_payload

        # Stage 7: Scene Compilation
        stage7 = SceneCompilationStage()
        scenes_payload = stage7.execute(ctx)
        assert stage7.validate(scenes_payload, ctx)
        ctx.state["scene_compilation"] = scenes_payload
        ctx.state["scene_compilation_payload"] = scenes_payload

        # Stage 8: Master Assembly
        stage8 = MasterAssemblyStage()
        master_payload = stage8.execute(ctx)
        assert stage8.validate(master_payload, ctx)
        assert master_payload["total_scenes"] >= 1
