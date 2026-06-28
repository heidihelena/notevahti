"""Step 1: core types construct and serialize round-trip cleanly."""

import json

from notevahti.types import (
    Agreement,
    AgreementStatus,
    AuditEntry,
    FieldSpec,
    FieldType,
    Independence,
    IndependenceStatus,
    Lineage,
    MatchKind,
    Provenance,
    ProvenanceStatus,
    Signal,
    SignalKind,
    ValidationRecord,
    Validity,
)


def _record() -> ValidationRecord:
    return ValidationRecord(
        value="cT2aN0M0",
        field=FieldSpec(name="clinical_stage", field_type=FieldType.STAGING),
        provenance=Provenance(
            status=ProvenanceStatus.SPAN_FOUND,
            claimed_span=(10, 18),
            matched_span=(10, 18),
            matched_text="cT2aN0M0",
            match_kind=MatchKind.EXACT,
            hallucination_flag=False,
        ),
        validity=Validity(score=0.9, flag_for_human_review=False, threshold=0.8),
        agreement=Agreement(status=AgreementStatus.NOT_AVAILABLE),
        independence=Independence(
            status=IndependenceStatus.SATISFIED,
            reason="anchor lineage disjoint",
            anchors_considered=1,
            independent_anchors=1,
        ),
        audit=AuditEntry(
            record_id="r1",
            timestamp="2026-06-27T00:00:00Z",
            actor="tester",
            prev_hash="0" * 64,
            payload={"k": "v"},
            entry_hash="abc",
        ),
        notevahti_version="0.1.0.dev0",
    )


def test_to_dict_is_json_serializable():
    d = _record().to_dict()
    s = json.dumps(d)  # must not raise
    back = json.loads(s)
    assert back["value"] == "cT2aN0M0"
    # enums serialized to their string values
    assert back["field"]["field_type"] == "staging"
    assert back["provenance"]["match_kind"] == "exact"
    assert back["independence"]["status"] == "satisfied"
    # tuple span becomes a list
    assert back["provenance"]["claimed_span"] == [10, 18]


def test_lineage_disjointness():
    a = Lineage(model_id="regex_v1", source_id="note_1")
    b = Lineage(human_id="abstractor_B", source_id="note_1")
    # shares source_id -> not disjoint
    assert a.shares_with(b) == "source_id"
    c = Lineage(human_id="abstractor_B")
    assert a.shares_with(c) is None
    assert Lineage().is_empty()
    assert not a.is_empty()


def test_signal_and_fieldspec_construct():
    s = Signal(value="cT2aN0M0", lineage=Lineage(human_id="B"), kind=SignalKind.INDEPENDENT_HUMAN)
    assert s.kind == "independent_human"
    f = FieldSpec(name="grade", field_type=FieldType.CATEGORICAL, allowed_values=("1", "2", "3"))
    assert f.allowed_values == ("1", "2", "3")
