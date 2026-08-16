"""CLI: run the planning pipeline on a fixture episode.

Usage:
    python -m videotool.cli berlin_wall [--mode draft|final] [--artifacts DIR] [--force]
"""
from __future__ import annotations

import argparse
import tempfile

from videotool.artifacts import ArtifactStore
from videotool.pipeline.runner import EpisodeInput, PipelineRunner

FIXTURES = {}


def _register():
    from videotool.fixtures import berlin_wall
    FIXTURES["berlin_wall"] = berlin_wall.load_episode


_register()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="videotool")
    parser.add_argument("fixture", choices=sorted(FIXTURES))
    parser.add_argument("--mode", default="final", choices=["draft", "final"])
    parser.add_argument("--artifacts", default="artifacts")
    parser.add_argument("--media-provider", default="fixture",
                        choices=["fixture", "wikimedia"],
                        help="media provider (default: deterministic fixture)")
    parser.add_argument("--force", action="store_true",
                        help="recompute every stage, ignoring cached artifacts")
    args = parser.parse_args(argv)

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
