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
    parser = argparse.ArgumentParser(prog="videotool")
    subparsers = parser.add_subparsers(dest="command")

    # Subcommand: write-narration (Phase 4 AI Scriptwriter + Fact Verification)
    write_parser = subparsers.add_parser("write-narration", help="generate documentary narration script and verify facts")
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

    # Subcommand: render
    render_parser = subparsers.add_parser("render", help="render episode to mp4 video")
    render_parser.add_argument("fixture", choices=sorted(FIXTURES), help="fixture episode name")
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

    # Subcommand: run (also default if fixture name passed directly)
    run_parser = subparsers.add_parser("run", help="run planning pipeline")
    run_parser.add_argument("fixture", choices=sorted(FIXTURES))
    run_parser.add_argument("--mode", default="final", choices=["draft", "final"])
    run_parser.add_argument("--artifacts", default="artifacts")
    run_parser.add_argument("--media-provider", default="fixture",
                            choices=["fixture", "wikimedia"],
                            help="media provider (default: deterministic fixture)")
    run_parser.add_argument("--timing-provider", default="deterministic",
                            choices=sorted(TIMING_PROVIDERS),
                            help="narration timing provider (default: deterministic)")
    run_parser.add_argument("--voice", default="vi-VN-HoaiMyNeural",
                            help="TTS voice name (default: vi-VN-HoaiMyNeural)")
    run_parser.add_argument("--force", action="store_true",
                            help="recompute every stage, ignoring cached artifacts")

    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] not in ("render", "run", "write-narration", "-h", "--help"):
        args_list.insert(0, "run")

    args = parser.parse_args(args_list)

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

    if args.command == "render":
        data = FIXTURES[args.fixture]()
        episode_id = data["episode_id"]
        store = ArtifactStore(args.artifacts)
        try:
            from videotool.domain.timing import NarrationTiming
            from videotool.editorial.pacing import audit_speech_pacing
            from videotool.render import render_episode

            audio_provider_name = None if args.no_audio else args.audio_provider
            result = render_episode(
                episode_id=episode_id,
                store=store,
                output_path=args.out,
                renderer_name=args.renderer,
                audio_provider_name=audio_provider_name,
                click_track=args.click_track,
                voice=args.voice,
            )
            print(f"rendered {args.fixture} -> {result.output_path} ({result.duration_sec:.2f}s)")
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
    data = FIXTURES[args.fixture]()
    from videotool.editorial.media import MediaAcquisitionConfig
    media_config = MediaAcquisitionConfig(provider=args.media_provider)

    timing_provider = None
    if args.timing_provider == "azure":
        timing_provider = build_timing_provider("azure", voice=args.voice,
                                                cache_dir=Path(args.artifacts) / "tts_cache")

    runner = PipelineRunner(ArtifactStore(args.artifacts), mode=args.mode,
                            force=args.force, media_config=media_config,
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
