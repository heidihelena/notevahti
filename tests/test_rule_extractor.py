"""Deterministic rule-based extractor: golden, negation, determinism, offline, span fidelity, e2e."""

import json
import socket
from pathlib import Path

import pytest

from notevahti.extractors import (
    Extractor,
    PassThroughExtractor,
    RegexExtractor,
    RuleBasedExtractor,
    rules_lineage,
)
from notevahti.extractors.rules import MODEL_ID
from notevahti.types import FieldSpec, FieldType, ProvenanceStatus
from notevahti.validate import validate_field

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "rule_extractor_cases.json").read_text(encoding="utf-8")
)
EX = RuleBasedExtractor()


def test_package_reexports_and_protocol():
    assert isinstance(EX, Extractor)
    # the package still re-exports the original adapters (import stability)
    assert PassThroughExtractor is not None and RegexExtractor is not None
    assert EX.version == MODEL_ID == "rules_v1"


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_golden_cases(case):
    note = case["note"]
    field = case["field"]
    cands = EX.candidates(note, field)
    values = {c.value for c in cands}

    # span fidelity: every reported span indexes exactly the reported surface text
    for c in cands:
        assert note[c.span[0] : c.span[1]] == c.matched_text, case["id"]

    if case.get("expect") is not None:
        assert case["expect"] in values, (case["id"], values)
    for absent in case.get("absent", []):
        assert absent not in values, (case["id"], absent, values)
    if case.get("absent_field"):
        assert cands == [], (case["id"], values)


def test_negation_suite_no_positive_findings():
    # absent/negated statements must not yield a positive finding
    assert EX.candidates("No evidence of metastasis.", "clinical_stage") == []
    assert EX.candidates("Ei merkkejä etäpesäkkeistä.", "clinical_stage") == []
    egfr = {c.value for c in EX.candidates("EGFR negatiivinen.", "biomarker")}
    assert "EGFR positive" not in egfr and "EGFR negative" in egfr
    histo = {c.value for c in EX.candidates("No adenocarcinoma seen.", "histology")}
    assert "adenocarcinoma" not in histo


def test_no_value_when_field_absent():
    res = EX.extract(
        "Bland note with no oncology content.",
        FieldSpec(name="clinical_stage", field_type=FieldType.STAGING),
    )
    assert res.value == "" and res.source_span is None


def test_single_valued_ambiguity_returns_no_value():
    # two distinct, non-overlapping clinical stages -> ambiguous -> no guess
    note = "First cT1a N0 M0, later cT3 N2 M0."
    res = EX.extract(note, FieldSpec(name="clinical_stage", field_type=FieldType.STAGING))
    assert res.value == ""  # ambiguous
    assert (
        len({c.value for c in EX.candidates(note, "clinical_stage")}) == 2
    )  # visible as candidates


def test_multi_valued_biomarker_returns_all_via_candidates():
    note = "EGFR negative, ALK negative, PD-L1 TPS 90%."
    vals = {c.value for c in EX.candidates(note, "biomarker")}
    assert {"EGFR negative", "ALK negative", "PD-L1 TPS 90%"} <= vals
    # the protocol single-value path still returns a real, span-bound finding (not empty)
    res = EX.extract(note, FieldSpec(name="biomarker", field_type=FieldType.CATEGORICAL))
    assert res.value and res.source_span is not None


def test_determinism_byte_for_byte():
    note = "RUL adenocarcinoma, cT2a N0 M0, EGFR negative, ECOG 1, SABR, curative."
    a = EX.extract_all(note)
    b = RuleBasedExtractor().extract_all(note)
    assert a == b


def test_end_to_end_with_validate_field_offline(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)

    note = "MDT: RUL adenocarcinoma, clinical stage cT2a N0 M0. ECOG 1. Plan: SABR."
    res = EX.extract(note, FieldSpec(name="clinical_stage", field_type=FieldType.STAGING))
    assert res.source_span is not None
    rec = validate_field(
        res.value,
        note,
        field_type=FieldType.STAGING,
        field_name="clinical_stage",
        claimed_span=res.source_span,
        value_lineage=rules_lineage(source_id="n1"),
    )
    assert rec.provenance.status is ProvenanceStatus.SPAN_FOUND
    assert rec.notevahti_version  # full record produced end-to-end, offline


def test_lineage_is_independent_rules_v1():
    lin = rules_lineage(source_id="note_7")
    assert lin.model_id == "rules_v1"
    assert lin.source_id == "note_7"
    assert lin.human_id is None
