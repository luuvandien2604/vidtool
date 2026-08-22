"""Unit tests for AI Editorial Director providers (Phase 3A)."""
from __future__ import annotations

import io
import json
import urllib.request
from unittest.mock import MagicMock, patch

from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.editorial.director.models import EditorialDirectorRequest
from videotool.editorial.director.projector import EditorialContextProjector
from videotool.editorial.director.providers.gemini import (
    GeminiEditorialDirectorProvider,
    _extract_json_block,
)
from videotool.editorial.director.providers.mock import MockEditorialDirectorProvider


def _sample_request() -> EditorialDirectorRequest:
    beat = SemanticBeat(
        beat_id="beat_101",
        start_sec=0.0,
        end_sec=4.0,
        narration_text="Gunter Schabowski misread the note at the press conference.",
        word_start=0,
        word_end=9,
        semantic_function=SemanticFunction.TURNING_POINT,
        visual_intent="Historic press conference announcement",
        entities=["Gunter Schabowski"],
        locations=["East Berlin"],
        dates=["November 9, 1989"],
        information_density=0.7,
    )
    return EditorialContextProjector.project_beat(beat)


def test_mock_provider_determinism():
    provider = MockEditorialDirectorProvider()
    req = _sample_request()

    intent1 = provider.generate_intent(req)
    intent2 = provider.generate_intent(req)

    assert intent1.beat_id == "beat_101"
    assert intent1.story_role == "TURNING_POINT"
    assert len(intent1.candidate_strategies) > 0
    assert intent1.confidence == 0.90
    assert intent1.to_dict() == intent2.to_dict()


def test_gemini_json_extraction_formats():
    # 1. Plain JSON string
    raw1 = '{"story_role": "TURNING_POINT", "visual_goal": "Show press conference"}'
    assert _extract_json_block(raw1)["story_role"] == "TURNING_POINT"

    # 2. Markdown fenced JSON block
    raw2 = 'Here is the proposal:\n```json\n{"story_role": "TURNING_POINT", "confidence": 0.85}\n```\nHope this helps!'
    assert _extract_json_block(raw2)["confidence"] == 0.85

    # 3. Outer braces with surrounding commentary
    raw3 = 'Some preamble {"story_role": "HOOK", "emphasis": "Wall"} extra notes.'
    assert _extract_json_block(raw3)["story_role"] == "HOOK"


@patch("urllib.request.urlopen")
def test_gemini_provider_mocked_http(mock_urlopen):
    response_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "story_role": "TURNING_POINT",
                                "visual_goal": "Focus on historic press conference",
                                "information_priority": ["Gunter Schabowski", "press note"],
                                "information_density": 0.75,
                                "emotional_goal": "dramatic_confusion",
                                "candidate_strategies": ["archival_portrait", "silhouette_to_archive_reveal"],
                                "preferred_visual_families": ["archival_subject"],
                                "avoid_visual_families": ["geographic_map"],
                                "must_show": ["Schabowski"],
                                "must_not_show": [],
                                "emphasis": "The accidental announcement",
                                "reason": "Historic moment warrants close focus on speaker.",
                                "confidence": 0.92,
                            })
                        }
                    ]
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    provider = GeminiEditorialDirectorProvider(api_key="test_key_fake")
    req = _sample_request()
    intent = provider.generate_intent(req)

    assert intent.beat_id == "beat_101"
    assert intent.story_role == "TURNING_POINT"
    assert intent.candidate_strategies == ["archival_portrait", "silhouette_to_archive_reveal"]
    assert intent.confidence == 0.92
