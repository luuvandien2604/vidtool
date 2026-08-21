"""CLI: run the planning pipeline or render video on a fixture episode.

Usage:
    python -m videotool.cli berlin_wall [--mode draft|final] [--artifacts DIR] [--force]
    python -m videotool.cli render berlin_wall [--artifacts DIR] [--out out.mp4] [--renderer ffmpeg]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from videotool.artifacts import ArtifactStore
from videotool.pipeline.runner import EpisodeInput, PipelineRunner

FIXTURES = {}


def _register():
    from videotool.fixtures import berlin_wall
    FIXTURES["berlin_wall"] = berlin_wall.load_episode


_register()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="videotool")
    subparsers = parser.add_subparsers(dest="command")

    # Subcommand: render
    render_parser = subparsers.add_parser("render", help="render episode to mp4 video")
    render_parser.add_argument("fixture", choices=sorted(FIXTURES), help="fixture episode name")
    render_parser.add_argument("--artifacts", default="artifacts", help="artifacts directory")
    render_parser.add_argument("--out", default="out.mp4", help="output mp4 path")
    render_parser.add_argument("--renderer", default="ffmpeg", choices=["ffmpeg"],
                               help="rendering backend (default: ffmpeg)")

    # Subcommand: run (also default if fixture name passed directly)
    run_parser = subparsers.add_parser("run", help="run planning pipeline")
    run_parser.add_argument("fixture", choices=sorted(FIXTURES))
    run_parser.add_argument("--mode", default="final", choices=["draft", "final"])
    run_parser.add_argument("--artifacts", default="artifacts")
    run_parser.add_argument("--media-provider", default="fixture",
                            choices=["fixture", "wikimedia"],
                            help="media provider (default: deterministic fixture)")
    run_parser.add_argument("--force", action="store_true",
                            help="recompute every stage, ignoring cached artifacts")

    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] not in ("render", "run", "-h", "--help"):
        args_list.insert(0, "run")

    args = parser.parse_args(args_list)

    if args.command == "render":
        data = FIXTURES[args.fixture]()
        episode_id = data["episode_id"]
        store = ArtifactStore(args.artifacts)
        try:
            from videotool.render import render_episode
            result = render_episode(
                episode_id=episode_id,
                store=store,
                output_path=args.out,
                renderer_name=args.renderer,
            )
            print(f"rendered {args.fixture} -> {result.output_path} ({result.duration_sec:.2f}s)")
            for w in result.warnings:
                print(f"  warn: {w}")
            return 0
        except Exception as exc:
            print(f"render ERROR: {exc}")
            return 1

    # Planning pipeline run
    data = FIXTURES[args.fixture]()
    from videotool.editorial.media import MediaAcquisitionConfig
    media_config = MediaAcquisitionConfig(provider=args.media_provider)
    runner = PipelineRunner(ArtifactStore(args.artifacts), mode=args.mode,
                            force=args.force, media_config=media_config)
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
