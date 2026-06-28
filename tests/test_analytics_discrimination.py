"""Discrimination metrics: hand-verified AUROC/AUPRC, PPV/NPV at deployment prevalence, enrichment."""

import math

import pytest

from notevahti.analytics.discrimination import (
    flag_discrimination,
    npv_at_prevalence,
    ppv_at_prevalence,
    score_discrimination,
)


def test_score_discrimination_hand_computed():
    # risk scores (higher = more likely error), labels error=True/False
    scores = [0.9, 0.6, 0.7, 0.1]
    errors = [True, True, False, False]
    r = score_discrimination(scores, errors, higher_is_error=True)
    # sorted asc 0.1(F),0.6(T),0.7(F),0.9(T) -> pos ranks 2,4 -> AUROC=(6-3)/4=0.75
    assert r.auroc == pytest.approx(0.75, abs=1e-6)
    # AP: 0.5 + (0.5)*(2/3) = 0.8333
    assert r.auprc == pytest.approx(0.8333, abs=1e-3)
    assert r.auprc_baseline == 0.5


def test_validity_score_orientation():
    # validity: HIGHER = better = less likely error. A perfectly inverse validity must give AUROC 1.
    validity = [0.95, 0.90, 0.20, 0.10]
    errors = [False, False, True, True]
    r = score_discrimination(validity, errors, higher_is_error=False)
    assert r.auroc == 1.0
    assert r.auprc == 1.0


def test_flag_discrimination_and_deployment_prevalence():
    flags = [True, True, False, False]
    errors = [True, False, True, False]
    r = flag_discrimination(flags, errors, deployment_prevalence=0.1)
    assert (r.tp, r.fp, r.tn, r.fn) == (1, 1, 1, 1)
    assert r.sensitivity == 0.5 and r.specificity == 0.5
    assert r.ppv_sample == 0.5
    # PPV at low prevalence collapses: 0.5*0.1/(0.5*0.1+0.5*0.9)=0.1
    assert r.ppv_at_deployment == pytest.approx(0.1, abs=1e-6)


def test_ppv_npv_formulas():
    assert ppv_at_prevalence(1.0, 1.0, 0.3) == 1.0
    assert npv_at_prevalence(1.0, 1.0, 0.3) == 1.0
    # perfect sensitivity, imperfect specificity, rare disease -> low PPV
    assert ppv_at_prevalence(1.0, 0.9, 0.01) == pytest.approx(0.0917, abs=1e-3)


def test_enrichment_perfect_precision():
    # everything flagged is an error, nothing accepted is -> infinite enrichment
    flags = [True, True, False, False, False]
    errors = [True, True, False, False, False]
    r = flag_discrimination(flags, errors)
    assert r.fp == 0 and r.fn == 0
    assert r.enrichment == float("inf")
    assert r.sensitivity == 1.0 and r.specificity == 1.0


def test_bootstrap_deterministic():
    scores = [0.9, 0.6, 0.7, 0.1, 0.8, 0.2]
    errors = [True, True, False, False, True, False]
    a = score_discrimination(scores, errors, bootstrap=200, seed=1)
    b = score_discrimination(scores, errors, bootstrap=200, seed=1)
    assert a.auroc_ci == b.auroc_ci and a.auroc_ci is not None
    f1 = flag_discrimination(
        [True, False] * 3, [True, False, True, False, False, False], bootstrap=100, seed=3
    )
    f2 = flag_discrimination(
        [True, False] * 3, [True, False, True, False, False, False], bootstrap=100, seed=3
    )
    assert f1.enrichment_ci == f2.enrichment_ci


def test_input_validation():
    with pytest.raises(ValueError):
        flag_discrimination([True], [True, False])
    with pytest.raises(ValueError):
        score_discrimination([], [])
    with pytest.raises(ValueError):
        score_discrimination([0.5], [True], bootstrap=10)  # no seed


def test_single_class_auroc_is_nan():
    r = score_discrimination([0.1, 0.2, 0.3], [False, False, False])
    assert math.isnan(r.auroc)
