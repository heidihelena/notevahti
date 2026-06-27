"""Step 6: tamper-evident, PHI-aware, append-only audit log."""

import json

from notevahti.audit import AuditLog, GENESIS_HASH, audit_payload, hash_text
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
    Validity,
    ValidationRecord,
)


def _record():
    return ValidationRecord(
        value="cT2aN0M0",
        field=FieldSpec(name="clinical_stage", field_type=FieldType.STAGING),
        provenance=Provenance(
            status=ProvenanceStatus.SPAN_FOUND, claimed_span=(14, 24), matched_span=(14, 24),
            matched_text="cT2a N0 M0", match_kind=MatchKind.NORMALIZED, hallucination_flag=False,
        ),
        validity=Validity(score=0.9, flag_for_human_review=False, threshold=0.8),
        agreement=Agreement(status=AgreementStatus.NOT_AVAILABLE),
        independence=Independence(status=IndependenceStatus.SATISFIED, reason="ok"),
    )


def test_chain_appends_and_verifies(tmp_path):
    log = AuditLog(str(tmp_path / "audit.jsonl"))
    assert log.last_hash() == GENESIS_HASH
    e1 = log.append("r1", "2026-06-27T00:00:00Z", "abstractor_A", {"k": 1})
    e2 = log.append("r2", "2026-06-27T00:01:00Z", "abstractor_A", {"k": 2})
    assert e1.prev_hash == GENESIS_HASH
    assert e2.prev_hash == e1.entry_hash
    ok, msg = log.verify()
    assert ok, msg
    assert "2 entries" in msg


def test_tamper_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(str(path))
    log.append("r1", "2026-06-27T00:00:00Z", "A", {"value": "cT2aN0M0"})
    log.append("r2", "2026-06-27T00:01:00Z", "A", {"value": "cT1aN0M0"})

    # Edit a past entry's payload without recomputing hashes.
    lines = path.read_text().splitlines()
    first = json.loads(lines[0])
    first["payload"]["value"] = "TAMPERED"
    lines[0] = json.dumps(first)
    path.write_text("\n".join(lines) + "\n")

    ok, msg = log.verify()
    assert ok is False
    assert "tampered" in msg.lower()


def test_payload_hashes_phi_by_default():
    note = "MDT note: 64F, RUL adenocarcinoma, clinical stage cT2a N0 M0."
    payload = audit_payload(_record(), note=note)
    assert payload["note_sha256"] == hash_text(note)
    assert "note_text" not in payload
    # matched snippet (PHI) hashed, raw removed
    assert "matched_text_sha256" in payload["provenance"]
    assert payload["provenance"].get("matched_text") is None
    # the registry value itself is retained (attributable subject of the audit)
    assert payload["value"] == "cT2aN0M0"


def test_payload_retains_text_on_optin():
    note = "MDT note text"
    payload = audit_payload(_record(), note=note, retain_text=True)
    assert payload["note_text"] == note
    assert payload["provenance"]["matched_text"] == "cT2a N0 M0"


def test_attribution_and_timestamp_present(tmp_path):
    log = AuditLog(str(tmp_path / "audit.jsonl"))
    log.append("r1", "2026-06-27T08:00:00Z", "abstractor_B", {"k": 1})
    e = log.entries()[0]
    assert e["actor"] == "abstractor_B"
    assert e["timestamp"] == "2026-06-27T08:00:00Z"
