"""Acceptance fixture: The Fall of the Berlin Wall (spec section 25).

~30-60s of narration with enough semantic variety to trigger character
introduction, document evidence, geographic context, causal relationship,
chronology and consequence. Berlin-specific data lives HERE ONLY (spec 31):
nothing in the architecture knows about Berlin.

Deterministic: synthetic word timings, fixed catalog.
"""
from __future__ import annotations

from videotool.domain.narration import Narration, synthetic_word_timings

EPISODE_ID = "berlin_wall_phase1"
SUBJECT = "The Fall of the Berlin Wall"

NARRATION_TEXT = (
    "November 1989. For twenty-eight years, a wall has divided one city in two. "
    "Berlin sits at the heart of a divided Europe, half looking west, "
    "half locked behind the Iron Curtain. "
    "Gunter Schabowski was a tired official in East Berlin, "
    "a man who read scripts written by others. "
    "Hungary had opened its border with Austria. "
    "Thousands of East Germans fled through Hungary toward the West. "
    "Weeks later, protests spread to Prague and Warsaw. "
    "Because Moscow would not intervene, the regime in East Berlin "
    "had lost its strongest protector. "
    "Then Schabowski held the travel regulation document in his hands, "
    "shuffling his notes at the live press conference. "
    "He read aloud: "
    "\"Private trips abroad can be applied for without conditions.\" "
    "Asked when the rules would take effect, he answered with one sentence too many, "
    "immediately, without delay. "
    "That evening, crowds suddenly flooded the checkpoints. "
    "Within hours, the wall that stood for twenty-eight years collapsed into history. "
    "By dawn, the city was one city again."
)

# Synthetic archival catalog (Phase 1: procedural assets; Phase 2 swaps in a
# real archive/API provider behind the same acquirer interface).
CATALOG: list[dict] = [
    {"asset_id": "archive:portrait:schabowski_1989", "kind": "portrait",
     "description": "portrait of Gunter Schabowski at a 1989 press conference",
     "entities": ["Gunter Schabowski"], "quality": 0.85, "source_quality": 0.8},
    {"asset_id": "archive:portrait:honecker_1976", "kind": "portrait",
     "description": "official portrait of Erich Honecker, 1976",
     "entities": ["Erich Honecker"], "quality": 0.75, "source_quality": 0.75},
    {"asset_id": "archive:document:travel_regulation", "kind": "document",
     "description": "East German travel regulation draft, November 1989",
     "entities": ["Gunter Schabowski", "East Berlin"], "quality": 0.8,
     "source_quality": 0.85},
    {"asset_id": "archive:document:press_transcript", "kind": "document",
     "description": "transcript of the 9 November 1989 press conference",
     "entities": ["Gunter Schabowski", "press conference"], "quality": 0.8,
     "source_quality": 0.9},
    {"asset_id": "archive:map:divided_berlin", "kind": "map",
     "description": "map of divided Berlin, 1989",
     "entities": ["Berlin"], "quality": 0.8, "source_quality": 0.7},
    {"asset_id": "archive:map:escape_routes", "kind": "map",
     "description": "map of escape routes through Hungary and Austria, 1989",
     "entities": ["Hungary", "Austria", "Berlin"], "quality": 0.75,
     "source_quality": 0.7},
    {"asset_id": "archive:photo:bornholmer_night", "kind": "photo",
     "description": "crowds at the Bornholmer Bridge checkpoint, night of 9 November 1989",
     "entities": ["Berlin", "Bornholmer Bridge"], "quality": 0.9,
     "source_quality": 0.85},
    {"asset_id": "archive:photo:newspapers_10nov", "kind": "photo",
     "description": "East and West German newspaper front pages, 10 November 1989",
     "entities": ["Berlin"], "quality": 0.8, "source_quality": 0.8},
    {"asset_id": "archive:photo:wall_dismantled", "kind": "photo",
     "description": "citizens dismantling the wall at the Brandenburg Gate, 1989",
     "entities": ["Berlin", "Brandenburg Gate"], "quality": 0.85,
     "source_quality": 0.8},
    {"asset_id": "archive:photo:prague_protests", "kind": "photo",
     "description": "protests in Prague, autumn 1989",
     "entities": ["Prague"], "quality": 0.7, "source_quality": 0.7},
]


def load_episode() -> dict:
    """Fixture episode input for the pipeline runner.

    Execution mode is NOT part of episode data: PipelineRunner owns it.
    """
    return {
        "episode_id": EPISODE_ID,
        "subject": SUBJECT,
        "narration": Narration(text=NARRATION_TEXT,
                               words=synthetic_word_timings(NARRATION_TEXT)),
        "catalog": CATALOG,
    }
