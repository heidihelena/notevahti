"""Stage-1 ordinal agreement: hand-verified weighted kappa / Gwet AC2, and the kappa paradox."""

import pytest

from notevahti.analytics.agreement import ordinal_agreement


def _expand(matrix, cats):
    """Expand a confusion matrix into paired rater lists (row=A, col=B)."""
    a, b = [], []
    for i, row in enumerate(matrix):
        for j, count in enumerate(row):
            a.extend([cats[i]] * count)
            b.extend([cats[j]] * count)
    return a, b


def test_hand_computed_3x3_quadratic():
    # O = [[10,2,0],[1,8,1],[0,3,5]], n=30, cats ordered 0<1<2.
    cats = ["0", "1", "2"]
    a, b = _expand([[10, 2, 0], [1, 8, 1], [0, 3, 5]], cats)
    r = ordinal_agreement(a, b, cats, weighting="quadratic")
    assert r.n == 30
    # hand-computed values (see module/test derivation)
    assert r.observed_agreement == pytest.approx(0.766667, abs=1e-5)
    assert r.cohen_kappa == pytest.approx(0.644068, abs=1e-5)
    assert r.weighted_kappa == pytest.approx(0.803738, abs=1e-5)
    assert r.gwet_ac2 == pytest.approx(0.832536, abs=1e-5)
    # ordinal weighting raises agreement above unweighted kappa
    assert r.weighted_kappa > r.cohen_kappa
    assert r.paradox_suspected is False


def test_kappa_paradox_detected_and_ac2_resists():
    # 90% observed agreement but skewed marginals -> negative Cohen kappa, high AC2.
    cats = ["neg", "pos"]
    a, b = _expand([[45, 3], [2, 0]], cats)
    r = ordinal_agreement(a, b, cats)
    assert r.observed_agreement == pytest.approx(0.90, abs=1e-6)
    assert r.cohen_kappa < 0.0          # the paradox: high agreement, negative kappa
    assert r.gwet_ac2 == pytest.approx(0.889503, abs=1e-5)  # paradox-resistant
    assert r.paradox_suspected is True


def test_perfect_and_identity_equivalence():
    cats = ["I", "II", "III", "IV"]
    a = ["I", "II", "III", "IV", "II"]
    r = ordinal_agreement(a, list(a), cats)
    assert r.observed_agreement == 1.0
    assert r.cohen_kappa == 1.0 and r.weighted_kappa == 1.0 and r.gwet_ac2 == 1.0
    # identity weighting reproduces unweighted Cohen kappa
    a2 = ["I", "II", "III", "IV", "I", "III"]
    b2 = ["I", "III", "III", "IV", "II", "III"]
    ident = ordinal_agreement(a2, b2, cats, weighting="identity")
    assert ident.weighted_kappa == pytest.approx(ident.cohen_kappa, abs=1e-9)


def test_bootstrap_is_deterministic_and_requires_seed():
    cats = ["0", "1", "2"]
    a, b = _expand([[10, 2, 0], [1, 8, 1], [0, 3, 5]], cats)
    r1 = ordinal_agreement(a, b, cats, bootstrap=200, seed=42)
    r2 = ordinal_agreement(a, b, cats, bootstrap=200, seed=42)
    assert r1.ci == r2.ci
    assert r1.ci is not None
    lo, hi = r1.ci["weighted_kappa"]
    assert lo <= r1.weighted_kappa <= hi
    with pytest.raises(ValueError):
        ordinal_agreement(a, b, cats, bootstrap=10)  # no seed


def test_input_validation():
    with pytest.raises(ValueError):
        ordinal_agreement(["a"], ["a", "b"], ["a", "b"])      # length mismatch
    with pytest.raises(ValueError):
        ordinal_agreement([], [], ["a"])                       # empty
    with pytest.raises(ValueError):
        ordinal_agreement(["x"], ["a"], ["a", "b"])            # value not in categories
