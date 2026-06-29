"""CLI: notevahti extract-validate (rule extractor -> validate -> route -> registry-ready)."""

import json
import socket
from pathlib import Path

import pytest

from notevahti.audit import AuditLog
from notevahti.cli import main


def _write_input(tmp_path: Path, records: list[dict]) -> str:
    p = tmp_path / "input.json"
    p.write_text(json.dumps(records), encoding="utf-8")
    return str(p)


def test_extract_validate_produces_json(tmp_path, capsys):
    inp = _write_input(
        tmp_path,
        [
            {
                "record_id": "r1",
                "note": "RUL adenocarcinoma, clinical stage cT2a N0 M0. ECOG 1. Plan: SABR.",
                "fields": ["clinical_stage", "histology", "performance_status"],
            }
        ],
    )
    rc = main(["extract-validate", inp])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["extractor"] == "rules"
    rec = out["records"][0]
    cs = rec["fields"]["clinical_stage"]
    assert cs["chosen"]["value"] == "cT2a N0 M0"
    assert cs["validation"]["provenance"]["status"] == "span_found"
    assert cs["route"]["route"] in {"accept", "review", "specialist_review", "blocked"}
    assert isinstance(cs["registry_ready"], bool)


def test_ambiguous_field_returns_no_guess(tmp_path, capsys):
    inp = _write_input(
        tmp_path,
        [
            {
                "record_id": "r1",
                "note": "First cT1a N0 M0, later cT3 N2 M0.",
                "fields": ["clinical_stage"],
            }
        ],
    )
    assert main(["extract-validate", inp]) == 0
    out = json.loads(capsys.readouterr().out)
    cs = out["records"][0]["fields"]["clinical_stage"]
    assert cs["chosen"] is None and cs["validation"] is None
    assert len(cs["candidates"]) >= 2  # the conflict is visible, not guessed


def test_audit_written_and_verifies(tmp_path):
    inp = _write_input(
        tmp_path,
        [{"record_id": "r1", "note": "Clinical stage cT2a N0 M0.", "fields": ["clinical_stage"]}],
    )
    audit = str(tmp_path / "audit.jsonl")
    out = str(tmp_path / "out.json")
    assert main(["extract-validate", inp, "--audit", audit, "--out", out]) == 0
    assert Path(out).exists()
    ok, _ = AuditLog(audit).verify()
    assert ok
    entry = AuditLog(audit).entries()[0]
    assert entry["payload"]["routing"]["route"]  # routing recorded in the audit


def test_no_network(tmp_path, monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    inp = _write_input(
        tmp_path, [{"record_id": "r1", "note": "ECOG 2.", "fields": ["performance_status"]}]
    )
    assert main(["extract-validate", inp, "--out", str(tmp_path / "o.json")]) == 0


def test_malformed_input_fails_clearly(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["extract-validate", str(bad)])
    # wrong shape (object, not array)
    obj = tmp_path / "obj.json"
    obj.write_text(json.dumps({"note": "x"}), encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["extract-validate", str(obj)])


def test_validate_command_unchanged(tmp_path, capsys):
    items = tmp_path / "items.json"
    items.write_text(
        json.dumps([{"value": "cT2aN0M0", "note": "stage cT2a N0 M0", "field_type": "staging"}]),
        encoding="utf-8",
    )
    assert main(["validate", str(items), "--field-type", "staging"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["summary"]["n"] == 1
