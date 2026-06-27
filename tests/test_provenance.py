"""Step 2: provenance verification and hallucination flagging."""

from notevahti.provenance import verify_span
from notevahti.types import FieldType, MatchKind, ProvenanceStatus

NOTE = (
    "MDT 2026-06-20. 64F, RUL adenocarcinoma. Clinical stage cT2a N0 M0. "
    "PET-CT no distant disease. Plan: SABR."
)


def test_exact_claimed_span_verified():
    span = (NOTE.index("SABR"), NOTE.index("SABR") + 4)
    p = verify_span("SABR", NOTE, claimed_span=span, field_type=FieldType.CATEGORICAL)
    assert p.status is ProvenanceStatus.SPAN_FOUND
    assert p.match_kind is MatchKind.EXACT
    assert p.matched_span == span
    assert p.hallucination_flag is False


def test_compact_normalized_match_for_staging():
    # value has no spaces, note writes it spaced -> compact match for STAGING
    p = verify_span("cT2aN0M0", NOTE, claimed_span=None, field_type=FieldType.STAGING)
    assert p.status is ProvenanceStatus.SPAN_FOUND
    assert p.match_kind is MatchKind.NORMALIZED
    assert NOTE[p.matched_span[0]:p.matched_span[1]].replace(" ", "") == "cT2aN0M0"
    assert p.hallucination_flag is False


def test_value_absent_is_flagged_hallucination():
    p = verify_span("pneumonectomy", NOTE, claimed_span=None, field_type=FieldType.CATEGORICAL)
    assert p.status is ProvenanceStatus.NO_SPAN_FOUND
    assert p.hallucination_flag is True
    assert p.matched_span is None


def test_wrong_claimed_span_but_value_present_elsewhere():
    # claim the span of "PET-CT" but assert value "SABR" -> mismatch, found elsewhere
    bad = (NOTE.index("PET-CT"), NOTE.index("PET-CT") + 6)
    p = verify_span("SABR", NOTE, claimed_span=bad, field_type=FieldType.CATEGORICAL)
    assert p.status is ProvenanceStatus.SPAN_FOUND
    assert p.hallucination_flag is False
    assert p.matched_span != bad
    assert "elsewhere" in p.detail


def test_out_of_bounds_claimed_span():
    p = verify_span("SABR", NOTE, claimed_span=(10_000, 10_004), field_type=FieldType.CATEGORICAL)
    # value still present in note -> found elsewhere
    assert p.status is ProvenanceStatus.SPAN_FOUND
    assert "out of bounds" in p.detail


def test_case_insensitive_text_match():
    p = verify_span("adenocarcinoma", NOTE.upper(), field_type=FieldType.TEXT)
    assert p.status is ProvenanceStatus.SPAN_FOUND
    assert p.match_kind is MatchKind.NORMALIZED


def test_empty_value_not_supported():
    p = verify_span("", NOTE, field_type=FieldType.TEXT)
    assert p.status is ProvenanceStatus.NO_SPAN_FOUND
    assert p.hallucination_flag is True
