"""Prompt engineering and formatting for the AI Editorial Director (Phase 3A).

Constrains LLM generation to structured editorial intents conforming to the
catalog vocabulary without allowing coordinate placement or rendering commands.
"""
from __future__ import annotations

import json
from videotool.editorial.director.models import EditorialDirectorRequest

EDITORIAL_DIRECTOR_PROMPT_VERSION = 1


def build_system_prompt() -> str:
    return (
        "You are an expert AI Editorial Director for high-end documentary video production.\n"
        "Your task is to analyze a single documentary semantic beat and propose an editorial visual intent.\n\n"
        "STRICT EDITORIAL RULES:\n"
        "1. PROPOSE ONLY from the supplied candidate strategies and visual families. NEVER invent new strategy IDs.\n"
        "2. DO NOT provide pixel coordinates, screen layouts, ASS subtitles, or FFmpeg commands.\n"
        "3. Consider visual variety and avoid visual families that were recently used or are at their streak limit.\n"
        "4. For any text labels or badges (captions), propose concise, natural phrases (2-6 words) STRICTLY grounded in the beat narration/entities.\n"
        "5. Output MUST be a single valid JSON object strictly conforming to the requested schema.\n"
        "6. Keep reasoning professional, concise, and focused on narrative pacing."
    )


def build_beat_prompt(req: EditorialDirectorRequest) -> str:
    """Format a compact, deterministic prompt for an individual beat."""
    strategies_info = [
        {
            "id": d.strategy_id,
            "family": d.visual_family,
            "note": d.storytelling_note,
        }
        for d in req.candidate_descriptors
    ]

    prompt_data = {
        "prompt_version": EDITORIAL_DIRECTOR_PROMPT_VERSION,
        "beat": {
            "beat_id": req.beat_id,
            "semantic_function": req.semantic_function,
            "narration_text": req.narration_text,
            "entities": req.entities,
            "locations": req.locations,
            "dates": req.dates,
            "information_density": req.information_density,
        },
        "art_direction": {
            "motifs": req.art_direction_motifs,
            "accent_color": req.accent_color,
        },
        "recent_visual_history": {
            "recent_families": req.recent_families,
            "recent_strategies": req.recent_strategies,
            "family_streak": req.family_streak,
        },
        "valid_candidate_strategies": strategies_info,
        "available_visual_families": req.available_families,
        "text_nodes": req.text_nodes,
    }

    return (
        "Analyze the following documentary beat and return your editorial proposal in JSON format.\n\n"
        f"INPUT CONTEXT:\n{json.dumps(prompt_data, indent=2, ensure_ascii=False)}\n\n"
        "REQUIRED JSON OUTPUT SCHEMA:\n"
        "{\n"
        '  "story_role": "<semantic function or storytelling role>",\n'
        '  "visual_goal": "<concise statement of what viewer should notice>",\n'
        '  "information_priority": ["<element 1>", "<element 2>"],\n'
        '  "information_density": 0.5,\n'
        '  "emotional_goal": "<intended atmosphere/emotion>",\n'
        '  "candidate_strategies": ["<strategy_id from valid list>", ...],\n'
        '  "preferred_visual_families": ["<family_id from available list>", ...],\n'
        '  "avoid_visual_families": ["<family_id to avoid due to repetition>", ...],\n'
        '  "must_show": ["<key entity or document>"],\n'
        '  "must_not_show": ["<cliché or distracting element>"],\n'
        '  "emphasis": "<key narrative focus>",\n'
        '  "reason": "<editorial justification for chosen strategies>",\n'
        '  "confidence": 0.95,\n'
        '  "captions": {\n'
        '    "<entity_or_node_id>": "<grounded short phrase 2-6 words>"\n'
        '  }\n'
        "}\n"
    )
