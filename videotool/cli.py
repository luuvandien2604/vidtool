"""CLI: run the planning pipeline or render video on a fixture episode.

Usage:
    python -m videotool.cli berlin_wall [--mode draft|final] [--artifacts DIR] [--force]
    python -m videotool.cli render berlin_wall [--artifacts DIR] [--out out.mp4] [--renderer ffmpeg] [--audio-provider azure|silence] [--no-audio]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from videotool.artifacts import ArtifactStore
from videotool.pipeline.runner import EpisodeInput, PipelineRunner
from videotool.providers.audio import AUDIO_PROVIDERS
from videotool.providers.timing import TIMING_PROVIDERS, build_timing_provider

from videotool.providers.fact_verification import FACT_VERIFICATION_PROVIDERS
from videotool.providers.narration_writer import NARRATION_WRITER_PROVIDERS

FIXTURES = {}


def _register():
    from videotool.fixtures import berlin_wall
    FIXTURES["berlin_wall"] = berlin_wall.load_episode


_register()


def main(argv: list[str] | None = None) -> int:
    # Common parent parser for global observability flags
    obs_parser = argparse.ArgumentParser(add_help=False)
    obs_parser.add_argument("--verbose", "-v", action="store_true", default=False,
                            help="enable detailed execution trace output")
    obs_parser.add_argument("--trace", action="store_true", default=False,
                            help="enable maximum low-level payload and state dumping")
    obs_parser.add_argument("--trace-ffmpeg", action="store_true", default=False,
                            help="output raw frame-by-frame FFmpeg encoding lines")
    obs_parser.add_argument("--log-format", default="human", choices=["human", "json"],
                            help="log format (default: human)")

    parser = argparse.ArgumentParser(prog="videotool", parents=[obs_parser])
    subparsers = parser.add_subparsers(dest="command")

    # Subcommand: write-narration (Phase 4 AI Scriptwriter + Fact Verification)
    write_parser = subparsers.add_parser("write-narration", parents=[obs_parser], help="generate documentary narration script and verify facts")
    write_parser.add_argument("topic", help="documentary topic or title")
    write_parser.add_argument("--duration", type=float, default=60.0, help="target duration in seconds (default: 60.0)")
    write_parser.add_argument("--language", default="en", choices=["en", "vi"], help="script language (default: en)")
    write_parser.add_argument("--mode", default="draft", choices=["draft", "final"], help="pipeline mode (default: draft)")
    write_parser.add_argument("--writer-provider", default="gemini", choices=sorted(NARRATION_WRITER_PROVIDERS),
                              help="narration writer provider (default: gemini)")
    write_parser.add_argument("--verifier-provider", default="gemini", choices=sorted(FACT_VERIFICATION_PROVIDERS),
                              help="fact verification provider (default: gemini)")
    write_parser.add_argument("--allow-uncertain-claims", action="store_true",
                              help="allow UNCERTAIN claims in final mode")
    write_parser.add_argument("--out", default="artifacts/ai_narration/narration.json",
                              help="output path for generated narration.json")
    write_parser.add_argument("--report-out", default="artifacts/ai_narration/fact_verification_report.json",
                              help="output path for fact_verification_report.json")

    # Subcommand: shooting-script
    ss_parser = subparsers.add_parser("shooting-script", parents=[obs_parser], help="generate shooting_script.json and shooting_script.md artifacts")
    ss_parser.add_argument("fixture", help="fixture name or episode_id in artifacts")
    ss_parser.add_argument("--artifacts", default="artifacts", help="artifacts directory")
    ss_parser.add_argument("--out-json", default=None, help="custom output path for shooting_script.json")
    ss_parser.add_argument("--out-md", default=None, help="custom output path for shooting_script.md")

    # Subcommand: revise
    revise_parser = subparsers.add_parser("revise", parents=[obs_parser], help="propose or apply feedback-driven editorial revisions")
    revise_parser.add_argument("fixture", help="fixture name or episode_id in artifacts")
    revise_parser.add_argument("--feedback", help="free-text feedback string to propose revision")
    revise_parser.add_argument("--apply", help="proposal ID to apply to editorial_overrides.json")
    revise_parser.add_argument("--provider", default="mock", choices=["mock", "gemini"],
                               help="revision interpreter provider (default: mock)")
    revise_parser.add_argument("--artifacts", default="artifacts", help="artifacts directory")

    # Subcommand: render
    render_parser = subparsers.add_parser("render", parents=[obs_parser], help="render episode to mp4 video")
    render_parser.add_argument("fixture", help="fixture name or episode_id in artifacts")
    render_parser.add_argument("--artifacts", default="artifacts", help="artifacts directory")
    render_parser.add_argument("--out", default="out.mp4", help="output mp4 path")
    render_parser.add_argument("--renderer", default="ffmpeg", choices=["ffmpeg"],
                               help="rendering backend (default: ffmpeg)")
    render_parser.add_argument("--audio-provider", default="silence", choices=sorted(AUDIO_PROVIDERS),
                               help="narration audio provider (default: silence)")
    render_parser.add_argument("--voice", default="vi-VN-HoaiMyNeural",
                               help="TTS voice name (default: vi-VN-HoaiMyNeural)")
    render_parser.add_argument("--no-audio", action="store_true",
                               help="skip audio synthesis and render silent video")
    render_parser.add_argument("--click-track", action="store_true",
                               help="emit audible tone pulses at beat boundaries (silence provider only)")

    # Subcommand: serve
    serve_parser = subparsers.add_parser("serve", parents=[obs_parser], help="start local VideoTool Web UI dashboard")
    serve_parser.add_argument("--port", type=int, default=8080, help="server port (default: 8080)")
    serve_parser.add_argument("--host", default="127.0.0.1", help="server host (default: 127.0.0.1)")
    serve_parser.add_argument("--artifacts", default="artifacts", help="artifacts directory (default: artifacts)")
    serve_parser.add_argument("--open", action="store_true", help="open dashboard in default web browser")

    # Subcommand: render-scene
    scene_parser = subparsers.add_parser("render-scene", parents=[obs_parser], help="render a declarative scene YAML to mp4 video")
    scene_parser.add_argument("scene_yaml", help="path to scene YAML file")
    scene_parser.add_argument("--artifacts", default="artifacts", help="artifacts directory (default: artifacts)")
    scene_parser.add_argument("--out", default="scene_out.mp4", help="output mp4 path")
    scene_parser.add_argument("--fps", type=int, default=30, help="frame rate (default: 30)")

    # Subcommand: run (also default if fixture name passed directly)
    run_parser = subparsers.add_parser("run", parents=[obs_parser], help="run planning pipeline")
    run_parser.add_argument("fixture", help="fixture name or episode_id in artifacts")
    run_parser.add_argument("--mode", default="final", choices=["draft", "final"])
    run_parser.add_argument("--artifacts", default="artifacts")
    run_parser.add_argument("--media-provider", default="fixture",
                            choices=["fixture", "wikimedia"],
                            help="media provider (default: deterministic fixture)")
    run_parser.add_argument("--timing-provider", default="deterministic",
                            choices=sorted(TIMING_PROVIDERS),
                            help="narration timing provider (default: deterministic)")
    run_parser.add_argument("--editorial-ai-enabled", action="store_true",
                            help="enable AI Editorial Director advisory scoring and caption authoring")
    run_parser.add_argument("--editorial-ai-provider", default="mock",
                            choices=["mock", "gemini"],
                            help="editorial AI provider (default: mock)")
    run_parser.add_argument("--voice", default="vi-VN-HoaiMyNeural",
                            help="TTS voice name (default: vi-VN-HoaiMyNeural)")
    run_parser.add_argument("--force", action="store_true",
                            help="recompute every stage, ignoring cached artifacts")

    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] not in ("render", "render-scene", "run", "write-narration", "shooting-script", "revise", "serve", "-h", "--help"):
        args_list.insert(0, "run")

    args = parser.parse_args(args_list)

    # Initialize Pipeline Logger
    from videotool.observability import LogFormat, init_logger
    job_target = getattr(args, "fixture", None) or getattr(args, "topic", None) or getattr(args, "scene_yaml", None) or getattr(args, "command", "pipeline")
    logger = init_logger(
        job_id=str(job_target),
        verbose=args.verbose,
        trace=args.trace,
        trace_ffmpeg=args.trace_ffmpeg,
        log_format=LogFormat(args.log_format.upper()),
    )

    if args.command == "serve":
        from videotool.web import run_web_server
        run_web_server(
            host=args.host,
            port=args.port,
            artifacts_dir=args.artifacts,
            open_browser=args.open,
        )
        return 0

    if args.command == "write-narration":
        from videotool.pipeline.narration_intake import NarrationIntakeService
        try:
            service = NarrationIntakeService(
                writer_provider_name=args.writer_provider,
                verifier_provider_name=args.verifier_provider,
                mode=args.mode,
                allow_uncertain_claims=args.allow_uncertain_claims,
            )
            narration, report = service.process(
                topic=args.topic,
                target_duration_sec=args.duration,
                language=args.language,
                out_narration_path=args.out,
                out_report_path=args.report_out,
            )
            print(f"Topic: {report.topic}")
            print(f"Narration generated: {len(narration.text.split())} words (~{args.duration:.1f}s target)")
            print(f"Factual claims extracted: {report.total_claims}")
            print(f"  - Verified:    {report.verified_count}")
            print(f"  - Uncertain:   {report.uncertain_count}")
            print(f"  - Contradicted:{report.contradicted_count}")
            gate_status = "PASSED" if report.passed_gate else "FAILED"
            print(f"Gate Status: {gate_status} ({args.mode} mode)")
            for w in report.warnings:
                print(f"  warn: {w}")
            print("Artifacts written:")
            print(f"  - Narration:           {args.out}")
            print(f"  - Verification Report: {args.report_out}")
            return 0
        except Exception as exc:
            import traceback
            print(f"write-narration ERROR: {exc or repr(exc)}")
            traceback.print_exc()
            return 1

    if args.command == "shooting-script":
        if args.fixture in FIXTURES:
            data = FIXTURES[args.fixture]()
            episode_id = data["episode_id"]
        else:
            episode_id = args.fixture
        store = ArtifactStore(args.artifacts)
        try:
            from videotool.render.frame_plan import build_episode_frame_plan
            from videotool.render.shooting_script import generate_shooting_script

            timeline = store.load(episode_id, "timeline")
            if not timeline:
                print(f"shooting-script ERROR: timeline artifact not found for episode '{episode_id}'. Run planning pipeline first.")
                return 1

            geo_plans = store.load(episode_id, "semantic_geometry") or []
            motion_plan = store.load(episode_id, "motion_plan") or {}
            media_assets = store.load(episode_id, "media_assets") or []
            visual_comps = store.load(episode_id, "visual_compositions") or []
            art_dir = store.load(episode_id, "episode_art_direction") or {}
            semantic_beats = store.load(episode_id, "semantic_beats") or []
            editorial_intents = store.load(episode_id, "editorial_intents") or {}
            editorial_overrides = store.load(episode_id, "editorial_overrides") or []

            plan = build_episode_frame_plan(
                timeline=timeline,
                geometry_plans=geo_plans,
                motion_plan=motion_plan,
                media_assets=media_assets,
                visual_compositions=visual_comps,
                art_direction=art_dir,
                semantic_beats=semantic_beats,
                editorial_intents=editorial_intents,
                editorial_overrides=editorial_overrides,
            )

            json_path = args.out_json or (Path(args.artifacts) / f"{args.fixture}_shooting_script.json")
            md_path = args.out_md or (Path(args.artifacts) / f"{args.fixture}_shooting_script.md")

            script_data, md_text = generate_shooting_script(
                plan=plan,
                timeline=timeline,
                semantic_beats=semantic_beats,
                geometry_plans=geo_plans,
                media_assets=media_assets,
                visual_compositions=visual_comps,
                out_json_path=json_path,
                out_md_path=md_path,
            )
            print(f"Generated shooting script for {args.fixture} ({len(script_data['beats'])} beats):")
            print(f"  - Machine-readable JSON: {json_path}")
            print(f"  - Human-readable MD:   {md_path}")
            return 0
        except Exception as exc:
            import traceback
            print(f"shooting-script ERROR: {exc or repr(exc)}")
            traceback.print_exc()
            return 1

    if args.command == "revise":
        if args.fixture in FIXTURES:
            data = FIXTURES[args.fixture]()
            episode_id = data["episode_id"]
        else:
            episode_id = args.fixture
        store = ArtifactStore(args.artifacts)
        from videotool.editorial.director.revision import RevisionService

        service = RevisionService(provider_name=args.provider)
        try:
            if args.apply:
                # Apply step
                overrides = service.apply_revision(episode_id=episode_id, proposal_id=args.apply, store=store)
                print(f"Applied revision proposal '{args.apply}' to {args.fixture}:")
                print(f"  Durable overrides count: {len(overrides)}")
                for ovr in overrides:
                    print(f"  - [{ovr.get('override_id')}] Beat {ovr.get('beat_id')}: {ovr.get('field')} -> \"{ovr.get('new_value')}\"")
                print(f"\nOverride saved to {store.episode_dir(episode_id) / 'editorial_overrides.json'}.")
                print(f"To update video: run planning pipeline and render.")
                return 0

            elif args.feedback:
                # Propose step
                proposal = service.propose_revision(
                    episode_id=episode_id,
                    feedback_text=args.feedback,
                    store=store,
                )
                print("================================================================================")
                print("                      EDITORIAL REVISION PROPOSAL")
                print("================================================================================")
                print(f"Proposal ID:   {proposal.proposal_id}")
                print(f"Target Beat:   {proposal.beat_id or '(none)'}")
                print(f"Target Node:   {proposal.target_id or '(none)'}")
                print(f"Field:         {proposal.field}")
                print(f"Feedback Text: \"{proposal.feedback}\"")
                print("--------------------------------------------------------------------------------")
                if not proposal.is_valid:
                    print(f"Status:        REJECTED / UNABLE TO APPLY")
                    print(f"Reason:        {proposal.rejection_reason}")
                    print("================================================================================")
                    return 1

                print(f"Status:        VALID (Grounded)")
                print(f"Before:        \"{proposal.old_value}\"")
                print(f"After:         \"{proposal.new_value}\"")
                print(f"Rationale:     {proposal.reason}")
                print("--------------------------------------------------------------------------------")
                print(f"To apply this change, run:")
                print(f"  python -m videotool.cli revise {args.fixture} --apply {proposal.proposal_id}")
                print("================================================================================")
                return 0
            else:
                print("revise ERROR: Please provide either --feedback \"<text>\" to propose or --apply <proposal_id> to commit.")
                return 1
        except Exception as exc:
            import traceback
    if args.command == "render-scene":
        import yaml
        from videotool.domain.scene_schema import SceneSpec
        from videotool.render.scene_renderer import SceneRenderer

        scene_path = Path(args.scene_yaml)
        if not scene_path.exists():
            print(f"render-scene ERROR: File not found: {scene_path}")
            return 1

        try:
            yaml_content = yaml.safe_load(scene_path.read_text(encoding="utf-8"))
            spec = SceneSpec.from_dict(yaml_content)
            renderer = SceneRenderer(artifacts_dir=args.artifacts)
            out_file = Path(args.out)
            rendered_path = renderer.render_scene(spec, out_file, fps=args.fps)
            print("================================================================================")
            print("                REFERENCE-FAITHFUL SCENE RENDER COMPLETE")
            print("================================================================================")
            print(f"Scene Title:    {spec.scene.get('title', 'Historical Scene')}")
            print(f"Duration:       {spec.project.get('duration_seconds', 12.0)}s")
            print(f"Output Video:   {rendered_path}")
            print(f"Asset Manifest: {Path(args.artifacts) / spec.project.get('id', 'scene_project') / 'media' / 'manifest.yaml'}")
            print("================================================================================")
            return 0
        except Exception as exc:
            import traceback
            print(f"render-scene ERROR: {exc or repr(exc)}")
            traceback.print_exc()
            return 1

    if args.command == "render":
        if args.fixture in FIXTURES:
            data = FIXTURES[args.fixture]()
            episode_id = data["episode_id"]
        else:
            episode_id = args.fixture
        store = ArtifactStore(args.artifacts)
        try:
            from videotool.domain.timing import NarrationTiming
            from videotool.editorial.pacing import audit_speech_pacing
            from videotool.render import render_episode
            from videotool.render.shooting_script import generate_shooting_script

            audio_provider_name = None if args.no_audio else args.audio_provider
            out_target = store.root / f"{episode_id}.mp4" if args.out == "out.mp4" else Path(args.out)
            result = render_episode(
                episode_id=episode_id,
                store=store,
                output_path=out_target,
                renderer_name=args.renderer,
                audio_provider_name=audio_provider_name,
                click_track=args.click_track,
                voice=args.voice,
                progress_callback=print,
            )
            print(f"🎉 RENDER HOÀN TẤT: {args.fixture} -> {result.output_path} ({result.duration_sec:.2f}s)")

            # Auto-generate shooting script alongside render
            try:
                timeline = store.load(episode_id, "timeline")
                geo_plans = store.load(episode_id, "semantic_geometry") or []
                motion_plan = store.load(episode_id, "motion_plan") or {}
                media_assets = store.load(episode_id, "media_assets") or []
                visual_comps = store.load(episode_id, "visual_compositions") or []
                art_dir = store.load(episode_id, "episode_art_direction") or {}
                semantic_beats = store.load(episode_id, "semantic_beats") or []
                editorial_intents = store.load(episode_id, "editorial_intents") or {}
                editorial_overrides = store.load(episode_id, "editorial_overrides") or []

                from videotool.render.frame_plan import build_episode_frame_plan
                plan = build_episode_frame_plan(
                    timeline=timeline,
                    geometry_plans=geo_plans,
                    motion_plan=motion_plan,
                    media_assets=media_assets,
                    visual_compositions=visual_comps,
                    art_direction=art_dir,
                    semantic_beats=semantic_beats,
                    editorial_intents=editorial_intents,
                    editorial_overrides=editorial_overrides,
                )
                json_path = Path(args.artifacts) / f"{args.fixture}_shooting_script.json"
                md_path = Path(args.artifacts) / f"{args.fixture}_shooting_script.md"
                generate_shooting_script(
                    plan=plan,
                    timeline=timeline,
                    semantic_beats=semantic_beats,
                    geometry_plans=geo_plans,
                    media_assets=media_assets,
                    visual_compositions=visual_comps,
                    out_json_path=json_path,
                    out_md_path=md_path,
                )
                print(f"  shooting script: {json_path} and {md_path}")
            except Exception as ss_exc:
                print(f"  warn: failed to auto-generate shooting script: {ss_exc}")

            if result.audio_is_placeholder is True:
                click_info = " [click_track]" if args.click_track else ""
                print(f"  audio: {audio_provider_name} (placeholder){click_info}")
            elif result.audio_is_placeholder is False:
                print(f"  audio: {audio_provider_name} (production, 48000Hz, voice={args.voice})")
                # Perform speech pacing audit
                timing_data = store.load(episode_id, "narration_timing")
                timeline_data = store.load(episode_id, "timeline")
                if timing_data and timeline_data:
                    lang = "vi" if args.voice.startswith("vi") else "en"
                    pacing = audit_speech_pacing(timeline_data, NarrationTiming.from_dict(timing_data), language=lang)
                    rate_unit = "SPS" if lang == "vi" else "WPS"
                    print(f"  pacing: {pacing.avg_token_rate:.1f} {rate_unit} (score: {pacing.overall_pacing_score:.2f}), {pacing.avg_char_rate:.1f} CPS | cut alignment: {pacing.cut_alignment_score * 100:.0f}%")
                    for w in pacing.warnings:
                        print(f"  pacing warn: {w}")
            else:
                print("  audio: none (silent)")
            for w in result.warnings:
                print(f"  warn: {w}")
            return 0
        except Exception as exc:
            import traceback
            print(f"render ERROR: {exc or repr(exc)}")
            traceback.print_exc()
            return 1

    # Planning pipeline run
    if args.fixture in FIXTURES:
        data = FIXTURES[args.fixture]()
    else:
        store = ArtifactStore(args.artifacts)
        narration_data = store.load(args.fixture, "narration")
        from videotool.domain.narration import Narration
        if narration_data:
            narr = Narration.from_dict(narration_data)
        else:
            narr = Narration(text="Historical documentary episode.", words=[])
        data = {
            "episode_id": args.fixture,
            "subject": args.fixture.replace("_", " ").title(),
            "narration": narr,
            "catalog": [],
        }
    from videotool.editorial.media import MediaAcquisitionConfig
    from videotool.pipeline.policy import ExecutionPolicy
    media_config = MediaAcquisitionConfig(provider=args.media_provider)

    timing_provider = None
    if args.timing_provider == "azure":
        timing_provider = build_timing_provider("azure", voice=args.voice,
                                                cache_dir=Path(args.artifacts) / "tts_cache")

    policy = ExecutionPolicy(
        mode=args.mode,
        force=args.force,
        editorial_ai_enabled=args.editorial_ai_enabled,
        editorial_ai_provider=args.editorial_ai_provider,
    )

    runner = PipelineRunner(ArtifactStore(args.artifacts), policy=policy,
                            media_config=media_config,
                            timing_provider=timing_provider)
    result = runner.run(EpisodeInput(**data))

    for stage, info in result.manifest["stages"].items():
        status = info["status"] if isinstance(info, dict) else info
        print(f"  {stage:26s} {status}")
    for repair in result.manifest.get("repairs", []):
        print(f"  repair [{repair['stage']}] {repair['issue']} -> {repair['action']}")
    for adj in result.manifest.get("feasibility", []):
        print(f"  feasibility {adj['beat_id']}: {adj['from']} -> {adj['to']} "
              f"({adj['reason']})")
    for section, report in result.validation.items():
        for err in report["errors"]:
            print(f"  ERROR [{section}] {err}")
        for warn in report["warnings"]:
            print(f"  warn  [{section}] {warn}")
    print(f"episode: {result.episode_id} | beats: {len(result.beats)} | "
          f"compositions: {len(result.compositions)} | ok: {result.ok}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
