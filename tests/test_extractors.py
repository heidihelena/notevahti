"""Step 8: extractor interface and example adapters; the contract is extractor-agnostic."""

from notevahti.extractors import Extractor, PassThroughExtractor, RegexExtractor
from notevahti.types import ExtractionResult, FieldSpec, FieldType, Lineage, ProvenanceStatus
from notevahti.validate import validate_field

NOTE = "Clinical stage cT2a N0 M0. Plan: SABR."
STAGE = FieldSpec(name="clinical_stage", field_type=FieldType.STAGING)


def test_adapters_satisfy_protocol():
    assert isinstance(PassThroughExtractor({"clinical_stage": "cT2aN0M0"}), Extractor)
    assert isinstance(RegexExtractor({"clinical_stage": r"c?T\d\w*\s*N\d\s*M\d"}), Extractor)


def test_passthrough_returns_value_and_span():
    ex = PassThroughExtractor({"clinical_stage": "cT2aN0M0"}, spans={"clinical_stage": (15, 25)})
    r = ex.extract(NOTE, STAGE)
    assert isinstance(r, ExtractionResult)
    assert r.value == "cT2aN0M0"
    assert r.source_span == (15, 25)
    assert r.extractor_id == "passthrough"


def test_regex_extracts_span():
    ex = RegexExtractor({"clinical_stage": r"(cT\d\w*\s*N\d\s*M\d)"})
    r = ex.extract(NOTE, STAGE)
    assert r.value == "cT2a N0 M0"
    assert NOTE[r.source_span[0] : r.source_span[1]] == "cT2a N0 M0"


def test_swapping_extractor_does_not_change_validation_contract():
    # Two different extractors propose the same value; validation produces an equivalent verdict.
    a = PassThroughExtractor({"clinical_stage": "cT2a N0 M0"})
    b = RegexExtractor({"clinical_stage": r"(cT\d\w*\s*N\d\s*M\d)"})
    ra = a.extract(NOTE, STAGE)
    rb = b.extract(NOTE, STAGE)

    vlin = Lineage(source_id="note_1", model_id="x")
    rec_a = validate_field(
        ra.value, NOTE, field=STAGE, claimed_span=ra.source_span, value_lineage=vlin
    )
    rec_b = validate_field(
        rb.value, NOTE, field=STAGE, claimed_span=rb.source_span, value_lineage=vlin
    )
    assert rec_a.provenance.status is ProvenanceStatus.SPAN_FOUND
    assert rec_b.provenance.status is ProvenanceStatus.SPAN_FOUND
    assert rec_a.validity.flag_for_human_review == rec_b.validity.flag_for_human_review


def test_missing_field_returns_empty():
    ex = RegexExtractor({"other": r"x"})
    r = ex.extract(NOTE, STAGE)
    assert r.value == ""
    assert r.source_span is None
