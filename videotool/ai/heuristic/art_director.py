"""Deterministic per-episode art direction.

Maps the episode's concept cluster (political division, nuclear disaster,
ocean liner, space mission, epidemic, abandoned places...) to a distinct
visual identity: one episode must never inherit another episode's look.
Cluster detection is lexicon driven and topic agnostic.
"""
from __future__ import annotations

from videotool.domain.art_direction import EpisodeArtDirection
from videotool.domain.narration import Narration
from videotool.domain.semantic_beat import SemanticBeat

_MOTION_CHARACTER = ["tactile", "restrained", "physical", "documentary",
                     "stop_motion_influence"]
_TYPOGRAPHY = ["editorial", "condensed", "institutional"]
_FORBIDDEN = ["glossy_ui", "generic_slideshow", "constant_zoom",
              "random_camera_motion", "repeated_template_composition"]

_CLUSTERS: dict[str, dict] = {
    "political_division": {
        "keywords": ["wall", "border", "division", "regime", "government",
                     "protest", "state", "party", "minister", "chancellor",
                     "checkpoint", "collapse of", "unification", "cold war",
                     "east", "west", "revolution"],
        "motifs": ["divided front pages", "concrete wall texture",
                   "checkpoint signage", "government documents",
                   "East/West division graphics", "stamped travel permits"],
        "archival": ["monochrome photography", "photocopy texture", "newsprint"],
        "geometry": ["divided frames", "horizontal barriers", "map boundaries"],
        "accent": {"primary": "muted_red", "warning": "stamped_red",
                   "neutral": "paper_black"},
    },
    "nuclear_disaster": {
        "keywords": ["reactor", "radiation", "nuclear", "meltdown", "core",
                     "contamination", "dosimeter", "exclusion zone", "chernobyl",
                     "sarcophagus"],
        "motifs": ["reactor schematics", "radiation warning signage",
                   "dosimeter readings", "engineer logbooks",
                   "contamination maps", "concrete sarcophagus texture"],
        "archival": ["fax-grade documents", "grainy telephoto footage",
                     "technical blueprints"],
        "geometry": ["concentric zones", "cutaway diagrams", "isolated systems"],
        "accent": {"primary": "safety_orange", "warning": "alarm_yellow",
                   "neutral": "graphite"},
    },
    "ocean liner": {
        "keywords": ["ship", "liner", "ocean", "maiden voyage", "iceberg",
                       " Titanic".strip(), "wireless", "lifeboat", "sank",
                       "passenger", "hull", "telegraph", "deck"],
        "motifs": ["nautical charts", "hull rivet texture", "marconi telegrams",
                   "passenger manifests", "shipyard blueprints",
                   "North Atlantic charts"],
        "archival": ["sepia photography", "halftone print", "ticket stubs"],
        "geometry": ["long horizontal horizons", "depth bands",
                     "chart grids"],
        "accent": {"primary": "deep_navy", "warning": "signal_red",
                   "neutral": "ivory"},
    },
    "space_mission": {
        "keywords": ["spacecraft", "orbit", "lunar", "mission control",
                     "astronaut", "rocket", "capsule", "apollo", "telemetry",
                     "launch", "module"],
        "motifs": ["mission control consoles", "telemetry printouts",
                   "checklists", "orbit diagrams", "capsule schematics",
                   "flight plans"],
        "archival": ["green-phosphor readouts", "70mm film frames",
                     "stamped mission documents"],
        "geometry": ["orbital arcs", "console grids", "round gauges"],
        "accent": {"primary": "signal_yellow", "warning": "caution_red",
                   "neutral": "mission_grey"},
    },
    "epidemic": {
        "keywords": ["plague", "outbreak", "epidemic", "virus", "infection",
                     "quarantine", "hospital", "fever", "vaccine", "cholera"],
        "motifs": ["mortality ledgers", "quarantine notices", "city maps",
                   "medical charts", "apothecary labels"],
        "archival": ["handwritten registers", "faded typescript", "engraving"],
        "geometry": ["stacked ledgers", "spreading rings", "street grids"],
        "accent": {"primary": "sickly_green", "warning": "placard_yellow",
                   "neutral": "bone_white"},
    },
    "abandoned_places": {
        "keywords": ["abandoned", "ghost town", "ruins", "derelict", "forgotten",
                     "evacuated", "empty city", "decay"],
        "motifs": ["peeling signage", "empty street photography",
                   "relocation notices", "dust textures", "survey maps"],
        "archival": ["faded kodachrome", "survey documents", "parcel maps"],
        "geometry": ["empty centers", "off-axis framing", "repeating voids"],
        "accent": {"primary": "dust_ochre", "warning": "rust_red",
                   "neutral": "washed_grey"},
    },
}


def _detect_cluster(text: str) -> tuple[str, dict]:
    low = text.lower()
    best, best_hits = "generic", -1
    for name, spec in _CLUSTERS.items():
        hits = sum(1 for k in spec["keywords"] if k in low)
        if hits > best_hits:
            best, best_hits = name, hits
    if best_hits <= 0:
        return "generic", {}
    return best, _CLUSTERS[best]


class HeuristicArtDirector:
    """Deterministic implementation of ArtDirectionGenerator."""

    def generate(self, episode_id: str, subject: str,
                 narration: Narration, beats: list[SemanticBeat]) -> EpisodeArtDirection:
        corpus = subject + " " + narration.text
        cluster, spec = _detect_cluster(corpus)

        if cluster == "generic":
            # derive identity from the episode's own entities instead of a preset
            entities: list[str] = []
            for b in beats:
                for e in b.entities:
                    if e not in entities:
                        entities.append(e)
            motifs = [f"{e.lower()} archival material" for e in entities[:4]] or \
                     ["subject-related archival material"]
            spec = {
                "motifs": motifs,
                "archival": ["archival photography", "document texture"],
                "geometry": ["asymmetric frames", "annotative overlays"],
                "accent": {"primary": "ink_black", "warning": "mark_red",
                           "neutral": "paper_white"},
            }
            reason = (f"No strong concept cluster detected; identity derived "
                      f"from episode entities: {', '.join(entities[:3]) or 'subject'}.")
        else:
            reason = (f"Concept cluster '{cluster}' matched episode keywords; "
                      f"motifs, archival language, geometry and accent follow "
                      f"that cluster, not a fixed template.")

        return EpisodeArtDirection(
            episode_id=episode_id,
            subject=subject,
            visual_motifs=spec["motifs"],
            archival_language=spec["archival"],
            geometry=spec["geometry"],
            typography_character=list(_TYPOGRAPHY),
            accent=spec["accent"],
            motion_character=list(_MOTION_CHARACTER),
            forbidden_patterns=list(_FORBIDDEN),
            concept_cluster=cluster,
            generation_reason=reason,
        )
