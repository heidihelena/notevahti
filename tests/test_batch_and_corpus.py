"""Step 9 + Step 7 integration: batch validation over the synthetic MDT corpus."""

import json
from pathlib import Path

from notevahti.audit import AuditLog
from notevahti.batch import validate_batch
from notevahti.types import AgreementStatus, FieldType, Lineage

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_mdt.json"


def _corpus_items():
    cases = json.loads(FIXTURE.read_text())
    items = []
    for case in cases:
        for fname, f in case["fields"].items():
            items.append(
                {
                    "value": f["value"],
                    "note": case["note"],
                    "field_type": f["field_type"],
                    "field_name": fname,
                    "reference": f["gold"],
                    "value_lineage": {
                        "source_id": case["case_id"],
                        "model_id": "synthetic_extractor",
                    },
                }
            )
    return items


def test_corpus_known_ground_truth_behaviour():
    items = [
        {**it, "value_lineage": Lineage(source_id=it["value_lineage"]["source_id"], model_id="m")}
        for it in _corpus_items()
    ]
    result = validate_batch(items, field_type=FieldType.CATEGORICAL)
    by_value = {(r.field.name, r.value): r for r in result.records}

    # The hallucinated treatment (value absent from note) must be flagged.
    hall = by_value[("treatment_hallucinated", "pneumonectomy")]
    assert hall.provenance.hallucination_flag is True
    assert hall.validity.flag_for_human_review is True

    # A correctly-supported, present value should not be flagged on provenance grounds.
    good = by_value[("clinical_stage", "cT2aN0M0")]
    assert good.provenance.hallucination_flag is False


def test_batch_agreement_reflects_wrong_value():
    # Build a batch where one staging value disagrees with gold; agreement < 1.
    items = []
    cases = json.loads(FIXTURE.read_text())
    for case in cases:
        for _fname, f in case["fields"].items():
            if f["field_type"] != "staging":
                continue
            items.append(
                {
                    "value": f["value"],
                    "note": case["note"],
                    "field_type": "staging",
                    "reference": f["gold"],
                }
            )
    result = validate_batch(items, field_type=FieldType.STAGING)
    assert result.agreement.status is AgreementStatus.AVAILABLE
    # one of the staging items (cT2bN0M0 vs gold cT2bN3M0) disagrees
    assert result.agreement.accuracy < 1.0


def test_batch_shares_audit_chain(tmp_path):
    log = AuditLog(str(tmp_path / "audit.jsonl"))
    items = [
        {
            "value": "SABR",
            "note": "Plan: SABR",
            "field_type": "categorical",
            "record_id": f"r{i}",
            "timestamp": "2026-06-27T00:00:00Z",
            "actor": "A",
        }
        for i in range(3)
    ]
    validate_batch(items, audit_log=log)
    ok, msg = log.verify()
    assert ok, msg
    assert "3 entries" in msg
