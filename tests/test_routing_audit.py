"""The review route is recorded in the tamper-evident audit trail."""

from notevahti.audit import AuditLog, audit_payload
from notevahti.routing import route_validation
from notevahti.types import (
    Agreement,
    AgreementStatus,
    FieldSpec,
    FieldType,
    Independence,
    IndependenceStatus,
    MatchKind,
    Provenance,
    ProvenanceStatus,
    ValidationRecord,
    Validity,
)


def _record(*, hallucination: bool) -> ValidationRecord:
    if hallucination:
        prov = Provenance(
            status=ProvenanceStatus.NO_SPAN_FOUND,
            claimed_span=None,
            matched_span=None,
            matched_text=None,
            match_kind=MatchKind.NONE,
            hallucination_flag=True,
        )
        validity = Validity(score=0.1, flag_for_human_review=True, threshold=0.8)
    else:
        prov = Provenance(
            status=ProvenanceStatus.SPAN_FOUND,
            claimed_span=(0, 1),
            matched_span=(0, 1),
            matched_text="x",
            match_kind=MatchKind.EXACT,
            hallucination_flag=False,
        )
        validity = Validity(score=0.9, flag_for_human_review=False, threshold=0.8)
    return ValidationRecord(
        value="x",
        field=FieldSpec(name="f", field_type=FieldType.CATEGORICAL),
        provenance=prov,
        validity=validity,
        agreement=Agreement(status=AgreementStatus.AVAILABLE),
        independence=Independence(status=IndependenceStatus.SATISFIED, reason=""),
    )


def test_route_to_dict_is_json_serializable():
    import json

    route = route_validation(_record(hallucination=True))
    d = route.to_dict()
    json.dumps(d)  # must not raise
    assert d["route"] == "blocked"
    assert "source_span_missing" in d["blocking_flags"]


def test_audit_payload_embeds_routing():
    record = _record(hallucination=True)
    route = route_validation(record)
    payload = audit_payload(record, note="MDT note", routing=route.to_dict())
    assert payload["routing"]["route"] == "blocked"
    assert payload["routing"]["rationale"]
    # PHI handling unchanged: note hashed, not stored raw
    assert "note_sha256" in payload and "note_text" not in payload


def test_audit_payload_without_routing_unchanged():
    payload = audit_payload(_record(hallucination=False), note="MDT note")
    assert "routing" not in payload


def test_routed_decision_is_in_the_hash_chain(tmp_path):
    log = AuditLog(str(tmp_path / "audit.jsonl"))
    record = _record(hallucination=True)
    route = route_validation(record, field_impact="high")
    payload = audit_payload(record, note="MDT note", routing=route.to_dict())
    log.append("r1", "2026-06-28T00:00:00Z", "abstractor_A", payload)
    ok, _ = log.verify()
    assert ok
    entry = log.entries()[0]
    assert entry["payload"]["routing"]["route"] == "blocked"

    # Tampering with the recorded route breaks the chain.
    import json
    from pathlib import Path

    p = Path(log.path)
    line = json.loads(p.read_text().splitlines()[0])
    line["payload"]["routing"]["route"] = "accept"
    p.write_text(json.dumps(line) + "\n")
    ok2, msg = log.verify()
    assert ok2 is False
    assert "tampered" in msg.lower()
