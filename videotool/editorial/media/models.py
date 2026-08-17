"""Domain models for production media acquisition (Phase 2A).

Provider-specific payloads are normalized into MediaCandidate at the
provider boundary; nothing provider-shaped ever leaks into editorial logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MediaType(str, Enum):
    PHOTO = "PHOTO"
    PORTRAIT = "PORTRAIT"
    DOCUMENT = "DOCUMENT"
    MAP = "MAP"
    ILLUSTRATION = "ILLUSTRATION"


# requirement kinds (strings used by feasibility policies) -> media types
KIND_TO_MEDIA_TYPE = {
    "photo": MediaType.PHOTO,
    "portrait": MediaType.PORTRAIT,
    "document": MediaType.DOCUMENT,
    "map": MediaType.MAP,
    "illustration": MediaType.ILLUSTRATION,
}


@dataclass
class MediaSearchPlan:
    """Deterministic semantic search plan for one requirement."""
    requirement_id: str
    requirement_kind: str
    primary_query: str
    alternate_queries: list[str] = field(default_factory=list)
    entity_terms: list[str] = field(default_factory=list)
    location_terms: list[str] = field(default_factory=list)
    date_terms: list[str] = field(default_factory=list)
    event_terms: list[str] = field(default_factory=list)
    negative_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "MediaSearchPlan":
        return cls(**d)


@dataclass
class MediaCandidate:
    """Provider-normalized candidate; no provider dicts beyond
    provider_metadata, which editorial logic must never read."""
    candidate_id: str
    provider: str
    title: str = ""
    description: str = ""
    media_type: str = MediaType.PHOTO.value
    width: int = 0
    height: int = 0
    creator: str = ""
    date_created: str = ""
    date_published: str = ""
    license_name: str = ""
    license_url: str = ""
    source_page: str = ""
    source_url: str = ""
    media_url: str = ""
    thumbnail_url: str = ""
    entities: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    provider_metadata: dict = field(default_factory=dict)

    def searchable_text(self) -> str:
        return " ".join([self.title, self.description,
                         " ".join(self.categories)])

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "MediaCandidate":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ScoredCandidate:
    candidate_id: str
    score: float
    components: dict = field(default_factory=dict)
    penalties: dict = field(default_factory=dict)
    reason: str = ""
    rejected_reason: str = ""      # license / below-threshold / generic

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "ScoredCandidate":
        return cls(**d)


@dataclass
class AcquisitionTrace:
    """Per-requirement record of everything the acquisition tried (spec 21)."""
    requirement_id: str
    provider: str = ""
    queries_attempted: list[str] = field(default_factory=list)
    candidates_seen: int = 0
    candidate_ids: list[str] = field(default_factory=list)
    candidate_scores: list[dict] = field(default_factory=list)
    selected_candidate_id: str | None = None
    selected_score: float = 0.0
    selected_reason: str = ""
    cache_status: str = ""
    unresolved_reason: str = ""
    rejections: list[dict] = field(default_factory=list)
    search_results: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "AcquisitionTrace":
        return cls(**d)


@dataclass
class MediaAttribution:
    asset_id: str
    creator: str = ""
    source_name: str = ""
    source_page: str = ""
    license_name: str = ""
    license_url: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "MediaAttribution":
        return cls(**d)


@dataclass
class MediaAcquisitionConfig:
    provider: str = "fixture"
    max_candidates_per_query: int = 10
    minimum_candidate_score: float = 0.40
    timeout_sec: float = 15.0
    retries: int = 2
    min_photo_width: int = 800
    min_document_width: int = 1000
    max_bytes: int = 50 * 1024 * 1024
    min_bytes: int = 4 * 1024
    user_agent: str = ("vidtool/0.2 "
                       "(https://github.com/luuvandien2604/vidtool; "
                       "+luuvandien2604@gmail.com)")
    # None -> cache under the artifact store root (gitignored)
    cache_dir: str | None = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()
