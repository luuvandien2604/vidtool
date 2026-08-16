"""Per-episode visual identity.

Generated once per episode from the topic/research/narration. Global channel
style lives elsewhere (style constants); this is what makes Chernobyl look
different from the next.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EpisodeArtDirection:
    episode_id: str
    subject: str
    visual_motifs: list[str] = field(default_factory=list)
    archival_language: list[str] = field(default_factory=list)
    geometry: list[str] = field(default_factory=list)
    typography_character: list[str] = field(default_factory=list)
    accent: dict = field(default_factory=dict)  # primary / warning / neutral
    motion_character: list[str] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)
    concept_cluster: str = "generic"
    generation_reason: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "EpisodeArtDirection":
        return cls(**d)
