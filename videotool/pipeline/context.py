"""Pipeline execution context (spec sections 20-21).

Encapsulates all runtime dependencies, configuration, episode data, execution mode,
and persistence store. Eliminates global state and provides dependency injection boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from videotool.ai.heuristic import HeuristicArtDirector, HeuristicBeatAnalyzer
from videotool.domain.narration import Narration
from videotool.editorial.geometry import SemanticGeometryBuilder
from videotool.editorial.media import MediaAcquisitionConfig
from videotool.editorial.strategies import PlanningConfig, StrategyPlanner
from videotool.editorial.timing import EditorialTimingPolicy
from videotool.pipeline.artifact_store import ArtifactStore
from videotool.providers.media import build_provider
from videotool.providers.timing import DeterministicNarrationTimingProvider

if TYPE_CHECKING:
    from videotool.providers.media.base import MediaProvider


@dataclass
class EpisodeInput:
    """Carries episode input data without execution policy or runner state."""
    episode_id: str
    subject: str
    narration: Narration
    catalog: list[dict] = field(default_factory=list)


class PipelineContext:
    """Execution context injected into every pipeline stage."""

    def __init__(
        self,
        episode: EpisodeInput,
        store: ArtifactStore,
        mode: str = "final",
        force: bool = False,
        planner_config: PlanningConfig | None = None,
        media_config: MediaAcquisitionConfig | None = None,
        timing_provider: Any | None = None,
        timing_policy: EditorialTimingPolicy | None = None,
        beat_analyzer: Any | None = None,
        art_director: Any | None = None,
        planner: StrategyPlanner | None = None,
        geometry_builder: Any | None = None,
    ):
        self.episode = episode
        self.store = store
        self.mode = mode
        self.force = force
        self.planner_config = planner_config or PlanningConfig()
        self._media_config_override = media_config
        self.timing_provider = timing_provider or DeterministicNarrationTimingProvider()
        self.timing_policy = timing_policy or EditorialTimingPolicy()
        self.beat_analyzer = beat_analyzer or HeuristicBeatAnalyzer()
        self.art_director = art_director or HeuristicArtDirector()
        self.planner = planner or StrategyPlanner(self.planner_config)
        self.geometry_builder = geometry_builder or SemanticGeometryBuilder()

        # In-memory stage state & execution logs
        self.state: dict[str, Any] = {}
        self._meta: dict[str, Any] = {}
        self._statuses: dict[str, dict[str, str]] = {}
        self._repairs: list[dict[str, str]] = []

    @property
    def episode_id(self) -> str:
        return self.episode.episode_id

    @property
    def narration(self) -> Narration:
        return self.episode.narration

    @property
    def media_config(self) -> MediaAcquisitionConfig:
        """Resolve media config: explicit override wins; catalog rides along as provider data."""
        cfg = self._media_config_override or MediaAcquisitionConfig()
        if cfg.provider == "fixture" and self.episode.catalog:
            cfg = MediaAcquisitionConfig(**{**cfg.to_dict(), "provider": "fixture"})
        return cfg

    def build_media_provider(self) -> MediaProvider:
        cfg = self.media_config
        if cfg.provider == "fixture":
            return build_provider("fixture", catalog=self.episode.catalog)
        return build_provider(
            cfg.provider,
            timeout_sec=cfg.timeout_sec,
            retries=cfg.retries,
            user_agent=cfg.user_agent,
        )

    def load_meta(self) -> dict[str, Any]:
        if not self._meta:
            loaded = self.store.load(self.episode_id, "stage_meta")
            self._meta = dict(loaded) if isinstance(loaded, dict) else {}
        return self._meta

    def record_status(self, stage_id: str, status: str, fingerprint: str) -> None:
        self._statuses[stage_id] = {"status": status, "fingerprint": fingerprint}

    def record_repair(self, stage: str, issue: str, action: str) -> None:
        self._repairs.append({"stage": stage, "issue": issue, "action": action})

    def get_status(self, stage_id: str) -> dict[str, str] | None:
        return self._statuses.get(stage_id)
