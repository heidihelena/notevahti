"""Synthetic-corpus row model: validation, round-trip, invariants, and schema/model agreement."""

import json
from pathlib import Path

import pytest

from notevahti.corpus import (
    CASE_CATEGORIES,
    DOC_FORMATS,
    ECOG_STATUSES,
    LANGUAGES,
    MDT_STATUSES,
    MESSINESS,
    SPLITS,
    TNM_PREFIXES,
    TREATMENT_INTENTS,
    SyntheticRow,
    validate_row,
)

_SCHEMA_DIR = Path(__file__).resolve().parents[1] / "corpus" / "schema"


def _row() -> dict:
    return {
        "dataset_version": "notevahti_lung_mdt_synthetic_v1",
        "case_id": "fi_0001",
        "record_id": "fi_0001_free_text",
        "language": "fi",
        "source_type": "synthetic",
        "documentation_format": "free_text",
        "messiness": "clean",
        "split_hint": "train",
        "ground_truth": {
            "mdt_discussed": True,
            "mdt_status": "completed",
            "ecog_ps": 1,
            "ecog_status": "explicit",
            "tnm": {
                "prefix": "c",
                "t": "T2a",
                "n": "N1",
                "m": "M0",
                "full": "cT2aN1M0",
                "complete": True,
                "ambiguous": False,
                "edition": "unknown",
            },
            "treatment_intent": "curative",
        },
        "note_text": "MDT-kokous pidetty. ECOG 1. cT2aN1M0.",
        "expected_output": {
            "mdt_discussed": {
                "value": True,
                "evidence": "MDT-kokous pidetty",
                "requires_review": False,
            },
            "ecog_ps": {"value": 1, "evidence": "ECOG 1", "requires_review": False},
            "tnm": {
                "value": "cT2aN1M0",
                "components": {"prefix": "c", "t": "T2a", "n": "N1", "m": "M0"},
                "evidence": "cT2aN1M0",
                "requires_review": False,
            },
        },
        "quality_labels": {"requires_review": False, "registry_ready": True},
    }


def test_minimal_row_is_valid_and_round_trips():
    payload = _row()
    assert validate_row(payload) == []
    row = SyntheticRow.from_dict(payload)
    assert row.case_id == "fi_0001"
    assert row.ground_truth.tnm.t == "T2a"
    assert row.ground_truth.tnm.completeness == "complete"  # derived, parse_tnm vocabulary
    assert row.source_type == "synthetic"


def test_committed_example_validates():
    payload = json.loads((_SCHEMA_DIR / "example_case.fi.json").read_text(encoding="utf-8"))
    assert validate_row(payload) == []
    row = SyntheticRow.from_dict(payload)
    assert row.ground_truth.ecog_ps == 1
    assert row.ground_truth.biomarkers and row.ground_truth.biomarkers["pdl1"] == "TPS 60%"


def test_missing_required_field_is_reported():
    payload = _row()
    del payload["note_text"]
    assert any("note_text" in e for e in validate_row(payload))


def test_bad_enums_are_reported():
    payload = _row()
    payload["language"] = "no"  # repo uses 'nb' for Norwegian, not 'no'
    payload["ground_truth"]["treatment_intent"] = "experimental"
    errors = validate_row(payload)
    assert any("language" in e for e in errors)
    assert any("treatment_intent" in e for e in errors)


def test_record_id_must_match_case_and_format():
    payload = _row()
    payload["record_id"] = "fi_0001_structured_mini"  # format says free_text
    assert any("record_id" in e for e in validate_row(payload))


def test_evidence_must_be_exact_span_of_note():
    payload = _row()
    payload["expected_output"]["ecog_ps"]["evidence"] = "ECOG 2"  # not in note_text
    assert any("ecog_ps.evidence" in e for e in validate_row(payload))


def test_ambiguous_tnm_must_not_be_resolved():
    payload = _row()
    payload["ground_truth"]["tnm"]["ambiguous"] = True
    payload["ground_truth"]["tnm"]["complete"] = False
    # leaving the resolved value in place must be rejected
    errors = validate_row(payload)
    assert any("ambiguous TNM" in e for e in errors)


def test_planned_mdt_is_not_completed():
    payload = _row()
    payload["ground_truth"]["mdt_status"] = "planned"
    # mdt_discussed still True -> incompatible
    assert any("mdt_status" in e for e in validate_row(payload))


def test_missing_ecog_value_must_be_null():
    payload = _row()
    payload["quality_labels"]["has_missing_ecog"] = True
    # expected ecog value still 1 -> must be null
    assert any("ECOG" in e for e in validate_row(payload))


def test_requires_review_incompatible_with_registry_ready():
    payload = _row()
    payload["quality_labels"]["requires_review"] = True
    payload["quality_labels"]["registry_ready"] = True
    assert any("registry_ready" in e for e in validate_row(payload))


def test_null_tnm_prefix_is_allowed():
    payload = _row()
    payload["ground_truth"]["tnm"] = {
        "prefix": None,
        "t": None,
        "n": None,
        "m": None,
        "full": None,
        "complete": False,
        "ambiguous": True,
        "edition": "unknown",
    }
    payload["expected_output"]["tnm"] = {
        "value": None,
        "components": {"prefix": None, "t": None, "n": None, "m": None},
        "evidence": "cT2aN1M0",
        "requires_review": True,
    }
    assert validate_row(payload) == []


def test_case_category_enum_is_checked():
    payload = _row()
    payload["case_category"] = "clear_explicit"
    assert validate_row(payload) == []
    payload["case_category"] = "totally_made_up"
    assert any("case_category" in e for e in validate_row(payload))


def test_from_dict_raises_on_invalid():
    with pytest.raises(ValueError):
        SyntheticRow.from_dict({"case_id": "x"})


def test_schema_and_model_vocabularies_agree():
    """The JSON Schema enums must match the Python model's frozensets, so they cannot drift."""
    schema = json.loads((_SCHEMA_DIR / "synthetic_case.schema.json").read_text(encoding="utf-8"))
    props = schema["properties"]
    gt = props["ground_truth"]["properties"]
    tnm = gt["tnm"]["properties"]

    assert set(props["language"]["enum"]) == LANGUAGES
    assert set(props["case_category"]["enum"]) == CASE_CATEGORIES
    assert set(props["documentation_format"]["enum"]) == DOC_FORMATS
    assert set(props["messiness"]["enum"]) == MESSINESS
    assert set(props["split_hint"]["enum"]) == SPLITS
    assert set(gt["mdt_status"]["enum"]) == MDT_STATUSES
    assert set(gt["ecog_status"]["enum"]) == ECOG_STATUSES
    assert set(gt["treatment_intent"]["enum"]) == TREATMENT_INTENTS
    assert set(tnm["prefix"]["enum"]) - {None} == TNM_PREFIXES  # schema also allows null


def test_schema_required_matches_model_required_keys():
    schema = json.loads((_SCHEMA_DIR / "synthetic_case.schema.json").read_text(encoding="utf-8"))
    reported = {e.split(":")[0] for e in validate_row({"quality_labels": {}})}
    assert set(schema["required"]) <= reported
