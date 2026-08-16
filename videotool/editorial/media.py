"""Media acquisition: semantic requirements -> scored assets (spec sections 15-16).

Generic acquirer over a pluggable catalog. Relevance is semantic (entity/
event/date/location/context overlap); visually-attractive-but-unrelated
material scores low. Unresolved requirements become placeholders in draft
mode and hard failures in final mode.
"""
from __future__ import annotations

import re

from videotool.domain.assets import AssetRequirement, MediaAsset

MIN_RELEVANCE = 0.35


def _tokens(text: str) -> set[str]:
    return {t.lower().strip(".,;:!?") for t in text.split() if len(t) > 2}


def _entity_tokens(entities: list[str]) -> set[str]:
    return {t.lower().strip(".,;:!?") for e in entities for t in e.split()
            if len(t) > 2}


class CatalogAcquirer:
    """Acquirer over an in-memory catalog of synthetic/procedural assets.

    Catalog rows: {asset_id, kind, description, entities: [..], quality: 0..1}
    Works for any topic; the fixture supplies a topic-specific catalog.
    """

    def __init__(self, catalog: list[dict], mode: str = "draft"):
        self.catalog = catalog
        self.mode = mode

    def acquire(self, requirements: list[AssetRequirement]) -> list[MediaAsset]:
        out: list[MediaAsset] = []
        used: set[str] = set()
        for req in requirements:
            match = self._best_for(req, used)
            if match:
                used.add(match["asset_id"])
                out.append(self._to_asset(match, req))
            elif self.mode == "draft":
                out.append(MediaAsset(
                    asset_id=f"placeholder:{req.kind}:{req.requirement_id}",
                    requirement_id=req.requirement_id,
                    description=f"PLACEHOLDER - {req.description}",
                    kind=req.kind, is_placeholder=True))
            # final mode: unresolved requirement intentionally omitted ->
            # downstream validation fails loudly (no silent filler B-roll)
        return out

    def _best_for(self, req: AssetRequirement, used: set[str]) -> dict | None:
        want = _entity_tokens(req.entities)
        want_tokens = _tokens(req.description) | want
        best, best_score = None, 0.0
        for row in self.catalog:
            if row["asset_id"] in used or row["kind"] != req.kind:
                continue
            have = _entity_tokens(row.get("entities", []))
            if want and have:
                # token-level overlap: surname token matches full-name token
                entity_match = len(want & have) / len(want)
            elif not want and have:
                entity_match = 0.0  # requirement has no who/where: weak anchor
            else:
                entity_match = 0.0
            row_tokens = _tokens(row["description"])
            context = len(want_tokens & row_tokens) / max(1, len(want_tokens))
            score = entity_match * 0.6 + context * 0.25 + row.get("quality", 0.5) * 0.15
            # generic historical imagery penalty (spec section 16)
            if entity_match == 0.0:
                score *= 0.5
            if score > best_score:
                best, best_score = row, score
        return best if best_score >= MIN_RELEVANCE else None

    def _to_asset(self, row: dict, req: AssetRequirement) -> MediaAsset:
        want = _entity_tokens(req.entities)
        have = _entity_tokens(row.get("entities", []))
        entity_match = (len(want & have) / len(want)) if want else 1.0
        context = len(_tokens(req.description) & _tokens(row["description"])) / \
            max(1, len(_tokens(req.description)))
        year = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", req.description)
        date_match = 1.0 if (year and year.group(1) in row["description"]) else (
            0.6 if year else 0.5)
        return MediaAsset(
            asset_id=row["asset_id"], requirement_id=req.requirement_id,
            description=row["description"], kind=row["kind"],
            entity_match=round(entity_match, 2),
            context_match=round(context, 2), date_match=date_match,
            visual_quality=row.get("quality", 0.6),
            source_quality=row.get("source_quality", 0.7),
            duplication_penalty=0.1 if row.get("reused") else 0.0)
