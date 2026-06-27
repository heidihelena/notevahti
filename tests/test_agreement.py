"""Step 5: agreement vs reference (Cohen's kappa, accuracy)."""

import pytest

from notevahti.agreement import agreement
from notevahti.types import AgreementStatus, FieldType


def test_no_reference_is_not_available():
    a = agreement(["x", "y"], None)
    assert a.status is AgreementStatus.NOT_AVAILABLE
    assert a.accuracy is None and a.kappa is None


def test_perfect_agreement():
    a = agreement(["1", "2", "3", "1"], ["1", "2", "3", "1"], FieldType.CATEGORICAL)
    assert a.status is AgreementStatus.AVAILABLE
    assert a.accuracy == 1.0
    assert a.kappa == 1.0
    assert a.n == 4


def test_known_kappa_value():
    # Classic 2x2 example: po=0.85, pe=0.5 -> kappa=0.70
    pred = ["yes"] * 45 + ["yes"] * 15 + ["no"] * 10 + ["no"] * 30
    ref = ["yes"] * 45 + ["no"] * 15 + ["yes"] * 10 + ["no"] * 30
    a = agreement(pred, ref, FieldType.CATEGORICAL)
    assert a.n == 100
    assert a.accuracy == 0.75
    # marginals: pred yes=60/no=40, ref yes=55/no=45
    # po=0.75, pe = 0.60*0.55 + 0.40*0.45 = 0.51 -> kappa = (0.75-0.51)/0.49 = 0.4898
    assert a.kappa == pytest.approx(0.4898, abs=1e-3)


def test_normalization_applied_to_agreement():
    # staging values differing only by whitespace agree
    a = agreement(["cT2a N0 M0"], ["cT2aN0M0"], FieldType.STAGING)
    assert a.accuracy == 1.0


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        agreement(["a"], ["a", "b"])


def test_zero_accuracy_distinct_categories():
    a = agreement(["a", "b"], ["b", "a"], FieldType.CATEGORICAL)
    assert a.accuracy == 0.0
    # po=0, pe=0.5 -> kappa=(0-0.5)/0.5=-1.0
    assert a.kappa == -1.0
