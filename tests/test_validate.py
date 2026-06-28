"""Step 7: the validate_field orchestrator end-to-end."""

import notevahti
from notevahti.audit import AuditLog
from notevahti.types import (
    AgreementStatus,
    FieldType,
    IndependenceStatus,
    Lineage,
    ProvenanceStatus,
    Signal,
    SignalKind,
)
from notevahti.validate import validate_field

NOTE = "MDT 2026-06-20. RUL adenocarcinoma. Clinical stage cT2a N0 M0. Plan: SABR."


def test_strong_field_full_record():
    rec = validate_field(
        "cT2aN0M0",
        NOTE,
        field_type=FieldType.STAGING,
        field_name="clinical_stage",
        value_lineage=Lineage(source_id="note_1", model_id="regex_v1"),
        anchors=[Signal("cT2aN0M0", Lineage(human_id="B"), SignalKind.INDEPENDENT_HUMAN)],
    )
    assert rec.provenance.status is ProvenanceStatus.SPAN_FOUND
    assert rec.independence.status is IndependenceStatus.SATISFIED
    assert rec.validity.flag_for_human_review is False
    assert rec.agreement.status is AgreementStatus.NOT_AVAILABLE
    assert rec.notevahti_version == notevahti.__version__


def test_hallucination_flagged_end_to_end():
    rec = validate_field(
        "pneumonectomy", NOTE, field_type=FieldType.CATEGORICAL, value_lineage=Lineage(model_id="m")
    )
    assert rec.provenance.hallucination_flag is True
    assert rec.validity.flag_for_human_review is True
    assert rec.validity.score <= 0.10


def test_circular_validation_refused():
    rec = validate_field(
        "cT2aN0M0",
        NOTE,
        field_type=FieldType.STAGING,
        value_lineage=Lineage(model_id="regex_v1"),
        anchors=[Signal("cT2aN0M0", Lineage(model_id="regex_v1"))],  # self-validation
    )
    assert rec.independence.status is IndependenceStatus.VIOLATED


def test_public_api_export():
    assert notevahti.validate_field is validate_field


def test_reference_gives_single_item_agreement():
    rec = validate_field("cT2aN0M0", NOTE, field_type=FieldType.STAGING, reference="cT2a N0 M0")
    assert rec.agreement.status is AgreementStatus.AVAILABLE
    assert rec.agreement.accuracy == 1.0
    assert rec.agreement.kappa is None  # not meaningful at n=1


def test_audit_persisted_and_verifies(tmp_path):
    log = AuditLog(str(tmp_path / "audit.jsonl"))
    rec = validate_field(
        "cT2aN0M0",
        NOTE,
        field_type=FieldType.STAGING,
        value_lineage=Lineage(source_id="note_1", model_id="m"),
        audit_log=log,
        record_id="r1",
        timestamp="2026-06-27T00:00:00Z",
        actor="A",
    )
    assert rec.audit is not None and rec.audit.entry_hash
    ok, _ = log.verify()
    assert ok
    # PHI not stored raw by default
    payload = log.entries()[0]["payload"]
    assert "note_text" not in payload
    assert "note_sha256" in payload


def test_determinism_same_inputs_same_record():
    kw = dict(
        field_type=FieldType.STAGING,
        value_lineage=Lineage(source_id="n", model_id="m"),
        anchors=[Signal("cT2aN0M0", Lineage(human_id="B"))],
    )
    a = validate_field("cT2aN0M0", NOTE, **kw).to_dict()
    b = validate_field("cT2aN0M0", NOTE, **kw).to_dict()
    assert a == b
