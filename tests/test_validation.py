"""Validation + deterministic fallback tests (spec sections 22, 26, 29)."""
from videotool.domain.assets import MediaAsset
from videotool.domain.composition import (CompositionLayer, LayerType,
                                          MotionStyle, VisualComposition)
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.editorial.validation import (ValidationReport,
                                            deterministic_fallback_composition,
                                            validate_beats, validate_compositions)

import json


def make_beat(i=1):
    return SemanticBeat(beat_id=f"beat_{i:04d}", start_sec=(i - 1) * 5.0,
                        end_sec=i * 5.0, narration_text="text", word_start=0,
                        word_end=3, semantic_function=SemanticFunction.EVIDENCE,
                        visual_intent="t")


def make_comp(beat, sig, asset="archive:photo:1", x=0.1, family="document_evidence"):
    comp = VisualComposition(composition_id=f"comp_{beat.beat_id}",
                             beat_id=beat.beat_id, visual_family=family,
                             strategy="single_document_focus", duration_sec=5.0,
                             novelty_signature=sig)
    comp.layers.append(CompositionLayer(
        id="doc", type=LayerType.DOCUMENT, x=x, y=0.1, width=0.5, height=0.6,
        z_index=10, role="document", asset_id=asset))
    return comp


def test_valid_compositions_pass():
    beats = [make_beat(1), make_beat(2)]
    comps = [make_comp(beats[0], "sigA"), make_comp(beats[1], "sigB")]
    assets = [MediaAsset(asset_id="archive:photo:1", requirement_id="r",
                         description="d", kind="document")]
    report = validate_compositions(comps, beats, assets)
    assert report.ok, report.errors


def test_exact_signature_reuse_is_an_error():
    beats = [make_beat(1), make_beat(2)]
    comps = [make_comp(beats[0], "SAME"), make_comp(beats[1], "SAME")]
    report = validate_compositions(comps, beats, [])
    assert not report.ok
    assert any("signature" in e for e in report.errors)


def test_duplicate_composition_id_is_an_error():
    beats = [make_beat(1)]
    a = make_comp(beats[0], "sigA")
    b = make_comp(beats[0], "sigB")
    b.composition_id = a.composition_id
    report = validate_compositions([a, b], beats + [make_beat(2)], [])
    assert any("duplicate composition_id" in e for e in report.errors)


def test_family_streak_threshold_enforced():
    beats = [make_beat(i) for i in range(1, 5)]
    comps = [make_comp(b, f"sig{i}", family="document_evidence")
             for i, b in enumerate(beats)]
    report = validate_compositions(comps, beats, [])
    assert any("consecutive beats" in e for e in report.errors)


def test_layer_out_of_bounds_is_an_error():
    beat = make_beat(1)
    comp = make_comp(beat, "sig")
    comp.layers[0].x = 1.4
    report = validate_compositions([comp], [beat], [])
    assert any("outside [0,1]" in e for e in report.errors)


def test_unbound_asset_reference_is_an_error():
    beat = make_beat(1)
    comp = make_comp(beat, "sig", asset="archive:ghost:9")
    report = validate_compositions([comp], [beat], [])
    assert any("unbound asset" in e for e in report.errors)


def test_placeholder_rejected_in_final_mode():
    beat = make_beat(1)
    comp = make_comp(beat, "sig", asset="placeholder:document:req_1")
    assets = [MediaAsset(asset_id="placeholder:document:req_1",
                         requirement_id="req_1", description="p",
                         kind="document", is_placeholder=True)]
    final = validate_compositions([comp], [beat], assets, mode="final")
    draft = validate_compositions([comp], [beat], assets, mode="draft")
    assert any("placeholder" in e for e in final.errors)
    assert draft.ok


def test_negative_duration_beat_is_an_error():
    beat = make_beat(1)
    beat.end_sec = beat.start_sec - 1.0
    report = validate_beats([beat], narration_duration=10.0)
    assert not report.ok


def test_beat_beyond_narration_is_an_error():
    beat = make_beat(1)
    beat.end_sec = 99.0
    report = validate_beats([beat], narration_duration=10.0)
    assert any("beyond narration" in e for e in report.errors)


def test_deterministic_fallback_produces_valid_composition():
    beat = make_beat(1)
    comp = deterministic_fallback_composition(beat, 0, [])
    assert comp.is_fallback
    assert comp.layers
    assert comp.focus_target
    report = validate_compositions(
        [comp], [beat], [], mode="final",
        max_family_streak=99)
    # fallback has no assets and unique signature -> structurally valid
    assert report.ok, report.errors


def test_beat_repair_assigns_default_function():
    beat = make_beat(1)
    beat.semantic_function = None
    from videotool.editorial.validation import repair_beat
    repaired = repair_beat(beat)
    assert repaired.semantic_function == SemanticFunction.ESTABLISHING_CONTEXT
