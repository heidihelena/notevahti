"""Step 9: CLI smoke test and JSON output shape."""

import json
from pathlib import Path

from notevahti.cli import main


def _write_items(tmp_path) -> str:
    items = [
        {
            "value": "cT2aN0M0",
            "note": "Clinical stage cT2a N0 M0. Plan: SABR.",
            "field_type": "staging",
            "field_name": "clinical_stage",
            "value_lineage": {"source_id": "n1", "model_id": "m"},
            "anchors": [
                {"value": "cT2aN0M0", "lineage": {"human_id": "B"}, "kind": "independent_human"}
            ],
            "reference": "cT2aN0M0",
        },
        {
            "value": "pneumonectomy",
            "note": "Clinical stage cT2a N0 M0. Plan: SABR.",
            "field_type": "categorical",
            "field_name": "treatment",
            "value_lineage": {"source_id": "n1", "model_id": "m"},
        },
    ]
    p = tmp_path / "items.json"
    p.write_text(json.dumps(items))
    return str(p)


def test_cli_validate_outputs_json(tmp_path, capsys):
    rc = main(["validate", _write_items(tmp_path), "--field-type", "categorical"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["summary"]["n"] == 2
    assert out["summary"]["flagged_for_review"] >= 1  # the hallucinated one
    assert len(out["records"]) == 2
    # the hallucinated value is flagged
    hall = next(r for r in out["records"] if r["value"] == "pneumonectomy")
    assert hall["provenance"]["hallucination_flag"] is True


def test_cli_writes_audit_and_out_file(tmp_path):
    items = _write_items(tmp_path)
    # add audit fields by rewriting with ids
    data = json.loads(Path(items).read_text())
    for i, it in enumerate(data):
        it.update(record_id=f"r{i}", timestamp="2026-06-27T00:00:00Z", actor="A")
    Path(items).write_text(json.dumps(data))

    audit = str(tmp_path / "audit.jsonl")
    out = str(tmp_path / "result.json")
    rc = main(["validate", items, "--field-type", "categorical", "--audit", audit, "--out", out])
    assert rc == 0
    assert Path(out).exists()
    from notevahti.audit import AuditLog

    ok, _ = AuditLog(audit).verify()
    assert ok
