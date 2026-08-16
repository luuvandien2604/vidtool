"""Visual history + composition signature tests (spec sections 10-11).

The critical property: changing the photo must NOT defeat repetition
detection - only structural changes may change the signature.
"""
from videotool.domain.composition import (CompositionLayer, LayerType,
                                          MotionStyle, VisualComposition)
from videotool.domain.visual_history import (HistoryEntry, VisualHistory,
                                             derive_signature)


def make_comp(family="archival_subject", hero_asset="archive:photo:a",
              hero_pos=(0.06, 0.10), extra_layers=1):
    comp = VisualComposition(
        composition_id="c1", beat_id="b1", visual_family=family,
        strategy="archival_portrait", duration_sec=5.0)
    comp.layers.append(CompositionLayer(
        id="hero", type=LayerType.IMAGE, x=hero_pos[0], y=hero_pos[1],
        width=0.4, height=0.6, z_index=10, role="hero", asset_id=hero_asset))
    for i in range(extra_layers):
        comp.layers.append(CompositionLayer(
            id=f"cap{i}", type=LayerType.LABEL, x=0.55, y=0.2 + 0.1 * i,
            width=0.3, height=0.06, z_index=20, role="caption"))
    comp.reading_order = [l.id for l in comp.layers]
    return comp


def test_same_layout_different_photo_same_signature():
    a = derive_signature(make_comp(hero_asset="archive:photo:a"))
    b = derive_signature(make_comp(hero_asset="archive:photo:totally_different"))
    assert a == b, "swapping the image must NOT change the structural signature"


def test_same_asset_type_counts_not_the_id():
    a = derive_signature(make_comp(hero_asset="archive:portrait:x"))
    b = derive_signature(make_comp(hero_asset="portrait:y"))
    # asset TYPE token differs -> signatures differ (both stay resolvable)
    assert a != b


def test_different_layout_different_signature():
    a = derive_signature(make_comp(hero_pos=(0.06, 0.10)))
    b = derive_signature(make_comp(hero_pos=(0.55, 0.10)))  # opposite quadrant
    assert a != b


def test_different_layer_count_different_signature():
    a = derive_signature(make_comp(extra_layers=1))
    b = derive_signature(make_comp(extra_layers=2))
    assert a != b


def test_signature_is_deterministic():
    c = make_comp()
    assert derive_signature(c) == derive_signature(c)


def test_family_recency_direction_is_correct():
    """recent use = LOW novelty, older use = higher, unseen = 1.0.

    (Phase 1.2.1 regression: this used to be inverted, and an old test
    locked the wrong behaviour.)
    """
    h = VisualHistory(max_window=10)
    assert h.family_recency("document_evidence") == 1.0  # unseen = novel
    h.record(HistoryEntry(beat_id="b1", visual_family="document_evidence",
                          strategy="s", composition_signature="sig1"))
    just_used = h.family_recency("document_evidence")
    h.record(HistoryEntry(beat_id="b2", visual_family="geographic_map",
                          strategy="s", composition_signature="sig2"))
    one_back = h.family_recency("document_evidence")
    h.record(HistoryEntry(beat_id="b3", visual_family="causal_network",
                          strategy="s", composition_signature="sig3"))
    h.record(HistoryEntry(beat_id="b4", visual_family="chronological_timeline",
                          strategy="s", composition_signature="sig4"))
    four_back = h.family_recency("document_evidence")
    assert just_used < one_back < four_back
    assert 0.0 < just_used < 0.2


def test_signature_recency_direction_is_correct():
    h = VisualHistory(max_window=8)
    h.record(HistoryEntry(beat_id="b1", visual_family="f", strategy="s",
                          composition_signature="sig_x"))
    assert h.signature_recency("sig_x") < 0.2
    assert h.signature_recency("sig_other") == 1.0


def test_family_streak_tracking():
    h = VisualHistory()
    for fam in ("document_evidence", "document_evidence", "geographic_map"):
        h.record(HistoryEntry(beat_id="b", visual_family=fam, strategy="s",
                              composition_signature=fam))
    assert h.family_streak() == ("geographic_map", 1)
    h.record(HistoryEntry(beat_id="b", visual_family="geographic_map",
                          strategy="s", composition_signature="g2"))
    assert h.family_streak() == ("geographic_map", 2)


def test_signature_seen_recently():
    h = VisualHistory()
    h.record(HistoryEntry(beat_id="b1", visual_family="f", strategy="s",
                          composition_signature="sig_x"))
    assert h.signature_seen_recently("sig_x")
    assert not h.signature_seen_recently("sig_y")


def test_history_persistence_roundtrip():
    h = VisualHistory()
    h.record(HistoryEntry(beat_id="b1", visual_family="f", strategy="s",
                          composition_signature="sig", dominant_asset="a1"))
    restored = VisualHistory.from_dict(h.to_dict())
    assert restored.entries[0].dominant_asset == "a1"


def test_history_artifact_persisted(berlin_run):
    raw = berlin_run["store"].load("berlin_wall_phase1", "visual_history")
    assert raw and len(raw["entries"]) == len(berlin_run["result"].beats)
