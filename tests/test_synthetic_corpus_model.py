"""Synthetic-corpus case model: validation, round-trip, and schema/model agreement."""

import json
from pathlib import Path

import pytest

from notevahti.corpus import (
    DIFFICULTY_TAGS,
    DOC_FORMATS,
    LANGUAGES,
    MESSINESS,
    TNM_COMPLETENESS,
    TNM_PREFIXES,
    TREATMENT_INTENTS,
    SyntheticCase,
    validate_case,
)

_SCHEMA_DIR = Path(__file__).resolve().parents[1] / "corpus" / "schema"


def _minimal() -> dict:
    return {
        "case_id": "fi_0001",
        "language": "fi",
        "documentation_format": "free_text",
        "messiness": "clean",
        "note": "MDT. ECOG 1. cT2aN1M0.",
        "truth": {
            "tnm": {"prefix": "c", "t": "T2a", "n": "N1", "m": "M0", "completeness": "complete"},
            "treatment_intent": "curative",
        },
    }


def test_minimal_case_is_valid_and_round_trips():
    payload = _minimal()
    assert validate_case(payload) == []
    case = SyntheticCase.from_dict(payload)
    assert case.case_id == "fi_0001"
    assert case.truth.tnm.t == "T2a"
    assert case.truth.tnm.edition == "unknown"  # defaulted
    assert case.source_type == "synthetic"


def test_committed_example_validates():
    payload = json.loads((_SCHEMA_DIR / "example_case.fi.json").read_text(encoding="utf-8"))
    assert validate_case(payload) == []
    case = SyntheticCase.from_dict(payload)
    assert case.truth.ecog_ps == 1
    assert case.truth.biomarkers and case.truth.biomarkers["pdl1"] == "TPS 60%"
    assert "explicit" in case.difficulty_tags


def test_missing_required_field_is_reported():
    payload = _minimal()
    del payload["note"]
    errors = validate_case(payload)
    assert any("note" in e for e in errors)


def test_bad_enums_are_reported():
    payload = _minimal()
    payload["language"] = "no"  # repo uses 'nb' for Norwegian, not 'no'
    payload["truth"]["tnm"]["completeness"] = "mostly"
    payload["truth"]["treatment_intent"] = "experimental"
    errors = validate_case(payload)
    assert any("language" in e for e in errors)
    assert any("completeness" in e for e in errors)
    assert any("treatment_intent" in e for e in errors)


def test_ecog_out_of_range_is_reported():
    payload = _minimal()
    payload["truth"]["ecog_ps"] = 5
    assert any("ecog_ps" in e for e in validate_case(payload))


def test_null_ground_truth_is_allowed():
    payload = _minimal()
    payload["truth"]["mdt_discussed"] = None
    payload["truth"]["ecog_ps"] = None
    payload["truth"]["tnm"] = {"prefix": "unknown", "completeness": "absent"}
    assert validate_case(payload) == []


def test_from_dict_raises_on_invalid():
    with pytest.raises(ValueError):
        SyntheticCase.from_dict({"case_id": "x"})


def test_schema_and_model_vocabularies_agree():
    """The JSON Schema enums must match the Python model's frozensets, so they cannot drift."""
    schema = json.loads((_SCHEMA_DIR / "synthetic_case.schema.json").read_text(encoding="utf-8"))
    props = schema["properties"]
    truth = props["truth"]["properties"]
    tnm = truth["tnm"]["properties"]

    assert set(props["language"]["enum"]) == LANGUAGES
    assert set(props["documentation_format"]["enum"]) == DOC_FORMATS
    assert set(props["messiness"]["enum"]) == MESSINESS
    assert set(tnm["prefix"]["enum"]) == TNM_PREFIXES
    assert set(tnm["completeness"]["enum"]) == TNM_COMPLETENESS
    assert set(truth["treatment_intent"]["enum"]) == TREATMENT_INTENTS
    assert set(props["difficulty_tags"]["items"]["enum"]) == DIFFICULTY_TAGS


def test_schema_required_matches_model_required_keys():
    schema = json.loads((_SCHEMA_DIR / "synthetic_case.schema.json").read_text(encoding="utf-8"))
    # The keys validate_case() insists on must be exactly the schema's required list.
    incomplete = {"difficulty_tags": []}
    reported = {e.split(":")[0] for e in validate_case(incomplete)}
    assert set(schema["required"]) <= reported
