"""Step 4: the validity heuristic and the review flag."""

from notevahti.independence import check_independence
from notevahti.provenance import verify_span
from notevahti.types import (
    FieldType,
    Lineage,
    Signal,
    SignalKind,
)
from notevahti.validity import DEFAULT_WEIGHTS, score_validity

NOTE = "Clinical stage cT2a N0 M0. Plan: SABR."
VALUE = "cT2aN0M0"
VLIN = Lineage(source_id="note_1", model_id="regex_v1")


def _score(value, note, anchors, field_type=FieldType.STAGING, claimed_span=None):
    prov = verify_span(value, note, claimed_span=claimed_span, field_type=field_type)
    indep = check_independence(VLIN, anchors)
    return score_validity(value, VLIN, prov, anchors, indep, field_type=field_type)


def test_weights_sum_to_one():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_strong_case_passes_threshold():
    anchors = [Signal(VALUE, Lineage(human_id="B"), SignalKind.INDEPENDENT_HUMAN)]
    v = _score(VALUE, NOTE, anchors)
    assert v.flag_for_human_review is False
    assert v.score >= v.threshold


def test_missing_span_is_capped_and_flagged():
    anchors = [Signal("pneumonectomy", Lineage(human_id="B"))]
    v = _score("pneumonectomy", NOTE, anchors)
    assert v.score <= 0.10
    assert v.flag_for_human_review is True


def test_no_independent_anchor_lowers_score_vs_independent():
    indep_anchor = [Signal(VALUE, Lineage(human_id="B"))]
    circular_anchor = [Signal(VALUE, Lineage(model_id="regex_v1"))]
    strong = _score(VALUE, NOTE, indep_anchor)
    weak = _score(VALUE, NOTE, circular_anchor)
    assert strong.score > weak.score


def test_disagreeing_independent_anchor_lowers_score():
    agree = [Signal(VALUE, Lineage(human_id="B"))]
    disagree = [Signal("cT1aN0M0", Lineage(human_id="B"))]
    assert _score(VALUE, NOTE, agree).score > _score(VALUE, NOTE, disagree).score


def test_monotonic_in_span_quality():
    # exact claimed span vs value found elsewhere (claimed mismatch) -> exact scores higher
    span = (NOTE.index("cT2a"), NOTE.index("cT2a") + len("cT2a N0 M0"))
    exact = _score(
        "cT2a N0 M0", NOTE, [Signal("cT2a N0 M0", Lineage(human_id="B"))], claimed_span=span
    )
    bad_span = (NOTE.index("SABR"), NOTE.index("SABR") + 4)
    mismatch = _score(
        "cT2a N0 M0", NOTE, [Signal("cT2a N0 M0", Lineage(human_id="B"))], claimed_span=bad_span
    )
    assert exact.score > mismatch.score


def test_disagreeing_independent_anchor_always_flags():
    # A wrong-but-present value with strong (exact) provenance would otherwise clear the threshold;
    # a disagreeing independent anchor must force review regardless of score.
    note = "Pre-MDT cTNM cT2a N0 M0. MDT recommendation: cTNM cT2a N2 M0."
    wrong = "cT2a N0 M0"  # present in note (pre-MDT), but the registry value is the post-MDT stage
    anchor = [Signal("cT2a N2 M0", Lineage(human_id="B"), SignalKind.INDEPENDENT_HUMAN)]
    v = _score(wrong, note, anchor)
    assert v.flag_for_human_review is True
    assert "disagree" in v.detail


def test_agreeing_anchor_does_not_force_flag():
    anchor = [Signal(VALUE, Lineage(human_id="B"))]
    v = _score(VALUE, NOTE, anchor)
    assert v.flag_for_human_review is False


def test_score_is_deterministic():
    anchors = [Signal(VALUE, Lineage(human_id="B"))]
    a = _score(VALUE, NOTE, anchors)
    b = _score(VALUE, NOTE, anchors)
    assert a.score == b.score and a.components == b.components
