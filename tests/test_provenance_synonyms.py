"""Opt-in provenance: word-boundary matching and clinical synonyms (default behaviour unchanged)."""

from notevahti.provenance import verify_span
from notevahti.synonyms import default_synonyms
from notevahti.types import FieldType, MatchKind, ProvenanceStatus

SYN = default_synonyms()


def test_word_boundary_blocks_substring_of_larger_token():
    note = "Male patient, never smoker."
    # default: 'M' matches inside 'Male'
    assert verify_span("M", note, field_type=FieldType.CATEGORICAL).status is (
        ProvenanceStatus.SPAN_FOUND
    )
    # word_boundary: 'M' is not a standalone token here -> not found
    assert verify_span("M", note, field_type=FieldType.CATEGORICAL, word_boundary=True).status is (
        ProvenanceStatus.NO_SPAN_FOUND
    )


def test_numeric_word_boundary_rejects_decimal_digit():
    note = "RUL mass 4.1 cm. ECOG 1."
    # default: '1' binds to the '1' inside '4.1'
    p_default = verify_span("1", note, field_type=FieldType.NUMERIC)
    assert p_default.status is ProvenanceStatus.SPAN_FOUND
    assert p_default.matched_span[0] == note.index("4.1") + 2  # the '1' in 4.1
    # word_boundary: skips the decimal and binds the standalone ECOG '1'
    p_wb = verify_span("1", note, field_type=FieldType.NUMERIC, word_boundary=True)
    assert p_wb.status is ProvenanceStatus.SPAN_FOUND
    assert p_wb.matched_span[0] == note.index("ECOG 1") + 5


def test_numeric_word_boundary_no_standalone_is_not_found():
    note = "tumour 4.1 cm only"
    assert verify_span("1", note, field_type=FieldType.NUMERIC, word_boundary=True).status is (
        ProvenanceStatus.NO_SPAN_FOUND
    )


def test_synonyms_match_abbreviations():
    note = "Hist: adenoCa. EGFR neg, KRAS pos."
    # default (no synonyms): canonical forms not present
    assert verify_span("adenocarcinoma", note, field_type=FieldType.CATEGORICAL).status is (
        ProvenanceStatus.NO_SPAN_FOUND
    )
    # opt-in synonyms: abbreviations count as support, reported as a normalised match
    p = verify_span("adenocarcinoma", note, field_type=FieldType.CATEGORICAL, synonyms=SYN)
    assert p.status is ProvenanceStatus.SPAN_FOUND
    assert p.match_kind is MatchKind.NORMALIZED
    assert note[p.matched_span[0] : p.matched_span[1]].lower() == "adenoca"
    assert verify_span("negative", note, field_type=FieldType.CATEGORICAL, synonyms=SYN).status is (
        ProvenanceStatus.SPAN_FOUND
    )


def test_synonyms_off_by_default_changes_nothing():
    note = "Biopsy: squamous NSCLC."
    assert verify_span(
        "squamous cell carcinoma", note, field_type=FieldType.CATEGORICAL
    ).status is (ProvenanceStatus.NO_SPAN_FOUND)
    assert (
        verify_span(
            "squamous cell carcinoma", note, field_type=FieldType.CATEGORICAL, synonyms=SYN
        ).status
        is ProvenanceStatus.SPAN_FOUND
    )


def test_default_path_unchanged_for_verbatim_value():
    note = "Clinical stage cT2a N0 M0. Plan: SABR."
    p = verify_span("cT2a N0 M0", note, field_type=FieldType.STAGING)
    assert p.status is ProvenanceStatus.SPAN_FOUND
    assert p.match_kind is MatchKind.EXACT
