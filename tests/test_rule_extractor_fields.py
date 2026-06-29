"""Stage-1 field strengthening: TNM structure, ECOG, and MDT-discussion extraction."""

from notevahti.extractors import RuleBasedExtractor, parse_tnm
from notevahti.types import FieldSpec, FieldType

EX = RuleBasedExtractor()


def _stage(note: str) -> object:
    return EX.extract(note, FieldSpec(name="clinical_stage", field_type=FieldType.STAGING)).value


# --------------------------------------------------------------------------- TNM (task 5)


def test_tnm_complete_no_space():
    p = parse_tnm("cT2aN0M0")
    assert (p.prefix, p.t, p.n, p.m) == ("c", "T2a", "N0", "M0")
    assert p.completeness == "complete"
    assert p.edition == "unknown" and p.review_recommended is False


def test_tnm_complete_spaced():
    p = parse_tnm("Stage cT2a N0 M0 confirmed.")
    assert (p.t, p.n, p.m, p.completeness) == ("T2a", "N0", "M0", "complete")


def test_tnm_no_prefix_unknown():
    p = parse_tnm("T2aN0M0")
    assert p.prefix == "unknown" and p.completeness == "complete"


def test_tnm_pathological_prefix_partial():
    p = parse_tnm("Resection ypT1bN0.")
    assert p.prefix == "yp" and p.t == "T1b" and p.n == "N0"
    assert p.m is None and p.completeness == "partial"


def test_tnm_isolated_n2_partial():
    p = parse_tnm("Mediastinal nodes consistent with N2.")
    assert p.n == "N2" and p.t is None and p.m is None
    assert p.completeness == "partial"


def test_tnm_partial_t3_n1():
    p = parse_tnm("Bulky T3 N1 disease.")
    assert p.t == "T3" and p.n == "N1" and p.m is None
    assert p.completeness == "partial"


def test_tnm_conflicting_is_ambiguous():
    p = parse_tnm("Initially cT2N0M0, restaged as cT4N2M1.")
    assert p.completeness == "ambiguous"
    assert p.t is None and p.review_recommended is True
    # the single-valued stage field also refuses to guess
    assert _stage("Initially cT2N0M0, restaged as cT4N2M1.") == ""


def test_tnm_old_vs_current_edition_triggers_review():
    p = parse_tnm("Staged T2 N0 (7th edition); now cT2a N1 M0 (8th edition).")
    assert p.completeness == "ambiguous"  # conflicting values + editions
    assert p.edition == "ambiguous" and p.review_recommended is True


# --------------------------------------------------------------------------- ECOG (task 6)


def _ps(note: str) -> str:
    return EX.extract(
        note, FieldSpec(name="performance_status", field_type=FieldType.CATEGORICAL)
    ).value


def test_ecog_variants():
    assert {c.value for c in EX.candidates("ECOG 0.", "performance_status")} == {"ECOG 0"}
    assert {c.value for c in EX.candidates("ECOG PS 1.", "performance_status")} == {"ECOG 1"}
    assert {c.value for c in EX.candidates("WHO PS 2.", "performance_status")} == {"ECOG 2"}
    assert {c.value for c in EX.candidates("PS 3 today.", "performance_status")} == {"ECOG 3"}


def test_ecog_finnish_and_swedish():
    assert {c.value for c in EX.candidates("Toimintakyky 1.", "performance_status")} == {"ECOG 1"}
    assert {c.value for c in EX.candidates("Funktionsstatus 2.", "performance_status")} == {
        "ECOG 2"
    }


def test_ecog_missing_is_no_value():
    assert _ps("Patient comfortable at home.") == ""


def test_ecog_temporal_change_not_silently_accepted():
    # "previous ECOG 1, now ECOG 3" -> two distinct values -> no auto-accept
    note = "Previous ECOG 1, now ECOG 3."
    assert _ps(note) == ""
    assert {c.value for c in EX.candidates(note, "performance_status")} == {"ECOG 1", "ECOG 3"}


def test_ecog_indirect_description_not_converted():
    # free-text functional descriptions are NOT canonically converted to an ECOG number
    assert EX.candidates("Fully active, no restrictions.", "performance_status") == []
    assert EX.candidates("Bedridden most of the day.", "performance_status") == []


# --------------------------------------------------------------------------- MDT discussion (task 7)


def _mdt(note: str) -> str:
    return EX.extract(note, FieldSpec(name="mdt_discussed", field_type=FieldType.CATEGORICAL)).value


def test_mdt_positive():
    assert _mdt("Discussed at MDT on 2026-06-03.") == "MDT"  # surface span text
    assert {c.value for c in EX.candidates("Reviewed by the tumour board.", "mdt_discussed")} == {
        "MDT discussed"
    }
    assert {
        c.value for c in EX.candidates("Käsitelty moniammatillisessa kokouksessa.", "mdt_discussed")
    } == {"MDT discussed"}


def test_mdt_planned_or_future_not_accepted():
    assert EX.candidates("Will be discussed at MDT next week.", "mdt_discussed") == []
    assert EX.candidates("MDT planned.", "mdt_discussed") == []
    assert EX.candidates("Referral pending; tumour board scheduled.", "mdt_discussed") == []


def test_mdt_negated_not_accepted():
    assert EX.candidates("Not yet discussed at MDT.", "mdt_discussed") == []
    assert (
        EX.candidates("Ei vielä käsitelty moniammatillisessa kokouksessa.", "mdt_discussed") == []
    )
