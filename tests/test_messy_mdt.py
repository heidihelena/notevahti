"""Messy MDT cases: integrity, and characterization of the string-provenance boundary.

These tests pin down what the current deterministic provenance can and cannot do on realistic,
abbreviated, implicitly-staged notes. They are honest boundary markers, not aspirational targets:
when provenance gains synonym/word-boundary handling, the relevant assertions should be updated.
"""

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from eval_messy_mdt import evaluate
from notevahti.provenance import verify_span
from notevahti.types import FieldType, ProvenanceStatus

DATA = Path(__file__).resolve().parent.parent / "corpus" / "messy_mdt" / "cases.jsonl"


def _cases() -> list[dict]:
    return [json.loads(ln) for ln in DATA.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_fixture_integrity():
    cases = _cases()
    assert len(cases) == 5
    for c in cases:
        gt = c["ground_truth"]
        assert c["note_text"]
        assert gt["case_id"] == c["case_id"]
        assert set(gt) >= {
            "cT",
            "cN",
            "cM",
            "stage_group",
            "biomarkers",
            "mdt_decision",
            "key_date",
        }
        date.fromisoformat(gt["key_date"])  # valid ISO date
        assert "implicit_staging" in c["difficulty_features"]


def test_implicit_staging_cannot_be_bound_by_string_provenance():
    # The hard boundary: canonical cTNM / stage group are inferred, never verbatim in messy notes,
    # so search-based provenance binds NONE of them. An extractor that emits these must supply a span
    # (or NoteVahti correctly flags them as unsupported). This is the motivation for Stage-1 work.
    r = evaluate(DATA)
    assert r.staging_total == 18
    assert r.staging_found == 0


def test_abbreviated_values_are_missed():
    # 'negative' is written 'neg', 'adenocarcinoma' as 'adenoCa' -> not found without a synonym layer.
    note = _cases()[0]["note_text"]  # SYN-MDT-001
    assert verify_span("negative", note, field_type=FieldType.CATEGORICAL).status is (
        ProvenanceStatus.NO_SPAN_FOUND
    )
    assert verify_span("adenocarcinoma", note, field_type=FieldType.CATEGORICAL).status is (
        ProvenanceStatus.NO_SPAN_FOUND
    )


def test_trivial_single_token_value_can_bind_spuriously():
    # ECOG is '1', but the first literal '1' in SYN-MDT-001 is inside '4.1 cm', not the ECOG mention.
    # Naive substring search returns that incidental span -> a FALSE provenance. Documents why
    # single-token values need word-boundary/context handling (a known weakness, not a feature).
    note = _cases()[0]["note_text"]
    p = verify_span("1", note, field_type=FieldType.NUMERIC)
    assert p.status is ProvenanceStatus.SPAN_FOUND
    assert p.matched_span is not None
    start = p.matched_span[0]
    assert "ECOG" not in note[max(0, start - 6) : start]  # not the ECOG mention


def test_literal_values_are_bound():
    # Values written verbatim (the date, a PD-L1 percentage number) are correctly located.
    note = _cases()[0]["note_text"]
    assert verify_span("2026-06-03", note, field_type=FieldType.TEXT).status is (
        ProvenanceStatus.SPAN_FOUND
    )
    assert verify_span("65", note, field_type=FieldType.NUMERIC).status is (
        ProvenanceStatus.SPAN_FOUND
    )
