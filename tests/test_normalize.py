"""TNM / stage-group surface normalisation."""

import pytest

from notevahti.normalize import canonical_stage, normalize_stage_group, normalize_tnm


@pytest.mark.parametrize(
    "raw,compact",
    [
        ("cT2a N0 M0", "cT2aN0M0"),
        ("cT2aN0M0", "cT2aN0M0"),
        ("ct2a n0 m0", "cT2aN0M0"),
        ("cT2a  N0   M0", "cT2aN0M0"),
        ("T2aN0M0", "T2aN0M0"),  # prefix preserved as written (absent stays absent)
        ("pT3 N1 M0", "pT3N1M0"),
        ("Tis N0 M0", "TisN0M0"),
        ("cTX NX M0", "cTXNXM0"),
        ("cT2a N2b M0", "cT2aN2bM0"),  # 9th-ed sub-N preserved, not translated
        ("cT4 N3 M1c", "cT4N3M1c"),
    ],
)
def test_normalize_tnm_compact(raw, compact):
    r = normalize_tnm(raw)
    assert r is not None
    assert r.compact == compact


def test_normalize_tnm_components_and_canonical():
    r = normalize_tnm("ct2a n0 m0")
    assert (r.prefix, r.t, r.n, r.m) == ("c", "T2a", "N0", "M0")
    assert r.canonical == "cT2a N0 M0"


def test_formatting_variants_share_canonical():
    assert normalize_tnm("cT2a N0 M0").compact == normalize_tnm("cT2aN0M0").compact
    assert normalize_tnm("ct2a   n0 m0").compact == normalize_tnm("cT2aN0M0").compact


def test_normalize_tnm_rejects_unparseable():
    assert normalize_tnm("adenocarcinoma") is None
    assert normalize_tnm("cT2a N0") is None  # missing M
    assert normalize_tnm("") is None


@pytest.mark.parametrize(
    "raw,canon",
    [
        ("IIIA", "IIIA"),
        ("iiia", "IIIA"),
        ("Stage IIIA", "IIIA"),
        ("stage 3a", "IIIA"),
        ("3A", "IIIA"),
        ("IV", "IV"),
        ("4b", "IVB"),
        ("II", "II"),
        ("0", "0"),
        ("group IVB", "IVB"),
    ],
)
def test_normalize_stage_group(raw, canon):
    assert normalize_stage_group(raw) == canon


def test_stage_group_rejects_unparseable():
    assert normalize_stage_group("V") is None
    assert normalize_stage_group("lobectomy") is None
    assert normalize_stage_group("") is None


def test_canonical_stage_prefers_tnm_then_group():
    assert canonical_stage("cT2a N0 M0") == "cT2aN0M0"
    assert canonical_stage("Stage IIIA") == "IIIA"
    assert canonical_stage("not a stage") is None
