"""Production media acquisition subsystem (Phase 2A).

Public surface:
    CatalogAcquirer      - legacy catalog matching (kept for compat/tests)
    plan_search          - deterministic semantic query planning
    rank_candidates      - explainable semantic ranking
    license_allowed      - license policy
    MediaCache           - content-addressed cache
    validate_media       - download validation
    MediaAcquisitionService - orchestration (search results in, MediaAssets out)
"""
from videotool.editorial.media.catalog import CatalogAcquirer
from videotool.editorial.media.query_planner import (MEDIA_QUERY_VERSION,
                                                     build_search_plan,
                                                     plan_search)
from videotool.editorial.media.ranking import (MEDIA_RANKING_VERSION,
                                               rank_candidates)
from videotool.editorial.media.licensing import (LICENSE_POLICY_VERSION,
                                                 license_allowed)
from videotool.editorial.media.cache import MEDIA_CACHE_VERSION, MediaCache
from videotool.editorial.media.validation import (MEDIA_DOWNLOAD_VERSION,
                                                  validate_media,
                                                  validate_media_assets)
from videotool.editorial.media.acquisition import (ACQUISITION_SERVICE_VERSION,
                                                   MediaAcquisitionService,
                                                   search_candidates)
from videotool.editorial.media.models import (MediaAcquisitionConfig,
                                              MediaAttribution,
                                              MediaCandidate, MediaSearchPlan,
                                              MediaType, ScoredCandidate,
                                              AcquisitionTrace)

__all__ = [
    "CatalogAcquirer", "plan_search", "build_search_plan", "rank_candidates",
    "search_candidates", "license_allowed", "MediaCache", "validate_media",
    "validate_media_assets",
    "MediaAcquisitionService", "MediaAcquisitionConfig", "MediaAttribution",
    "MediaCandidate", "MediaSearchPlan", "MediaType", "ScoredCandidate",
    "AcquisitionTrace", "MEDIA_QUERY_VERSION", "MEDIA_RANKING_VERSION",
    "LICENSE_POLICY_VERSION", "MEDIA_DOWNLOAD_VERSION",
    "ACQUISITION_SERVICE_VERSION", "MEDIA_CACHE_VERSION",
]
