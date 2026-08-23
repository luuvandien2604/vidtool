"""Tests for AI-authored caption grounding validator (Anti-Hallucination Gate)."""
from __future__ import annotations

import pytest

from videotool.editorial.director.caption_validator import validate_caption


def test_grounded_caption_passes():
    narration = "Gunter Schabowski was a tired official in East Berlin, a man who read scripts written by others."
    entities = ["Gunter Schabowski", "East Berlin"]
    locations = ["East Berlin"]
    dates = []

    # Valid grounded short phrase
    ok, reason = validate_caption(
        caption="Official Gunter Schabowski",
        narration_text=narration,
        entities=entities,
        locations=locations,
        dates=dates,
        text_role="LABEL",
    )
    assert ok is True
    assert "factually grounded" in reason


def test_ungrounded_entity_rejected():
    narration = "Gunter Schabowski was a tired official in East Berlin, a man who read scripts written by others."
    entities = ["Gunter Schabowski", "East Berlin"]

    # Invented proper noun: "Erich Honecker" not in this beat
    ok, reason = validate_caption(
        caption="Erich Honecker East Berlin",
        narration_text=narration,
        entities=entities,
        text_role="LABEL",
    )
    assert ok is False
    assert "Unreferenced proper noun/entity" in reason
    assert "Erich" in reason or "Honecker" in reason


def test_ungrounded_number_date_rejected():
    narration = "Hungary had opened its border with Austria."
    entities = ["Hungary", "Austria"]

    # Invented year 1961 not in beat context
    ok, reason = validate_caption(
        caption="Hungary border 1961",
        narration_text=narration,
        entities=entities,
        text_role="LABEL",
    )
    assert ok is False
    assert "Unreferenced number/date '1961'" in reason


def test_length_gate_rejected():
    narration = "Weeks later, protests spread to Prague and Warsaw."
    entities = ["Prague", "Warsaw"]

    # Caption with 12 words (exceeds max_label_words=8)
    long_caption = "Protests spread across Prague and Warsaw in a massive historical uprising across Eastern Europe"
    ok, reason = validate_caption(
        caption=long_caption,
        narration_text=narration,
        entities=entities,
        text_role="LABEL",
        max_label_words=8,
    )
    assert ok is False
    assert "exceeds 8 words" in reason


def test_empty_caption_rejected():
    ok, reason = validate_caption("", narration_text="Some text")
    assert ok is False
    assert "empty" in reason


def test_quote_caption_validation():
    narration = 'He read aloud: "Private trips abroad can be applied for without conditions."'

    # Grounded quote
    ok, reason = validate_caption(
        caption="Private trips abroad can be applied for without conditions",
        narration_text=narration,
        text_role="QUOTE",
    )
    assert ok is True

    # Ungrounded quote inventing new claims
    ok, reason = validate_caption(
        caption="Private flights to London and Paris are now completely free",
        narration_text=narration,
        text_role="QUOTE",
    )
    assert ok is False
    assert "Unreferenced proper noun/entity" in reason or "London" in reason
