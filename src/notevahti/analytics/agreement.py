"""Ordinal agreement for registry fields (TNM stage etc.) — weighted κ, Gwet's AC2, paradox-aware.

Why this exists: agreement against a reference is one of NoteVahti's five outputs, but the core
``notevahti.agreement`` reports only unweighted Cohen's κ and accuracy. Staging is an *ordinal*
scale, where a one-step disagreement is not as bad as a four-step one, so unweighted κ understates
agreement and is prone to the *kappa paradox* (high observed agreement, low κ under skewed
marginals). This module adds, for an ORDERED category set:

- observed agreement (accuracy),
- unweighted Cohen's κ,
- quadratic-weighted Cohen's κ (ordinal),
- Gwet's AC2 (quadratic-weighted; paradox-resistant chance correction),
- per-category prevalence (to expose skew), and a paradox flag,
- optional percentile bootstrap CIs (deterministic: an explicit integer seed is required).

Standard statistics, not a NoteVahti contribution. Evidence, not a guarantee. References:
weighted κ — PSU STAT509 L18.7; kappa paradox — Zec et al. 2017 (PMC5712640);
Gwet AC1/AC2 — Wongpakaran 2013 (BMC Med Res Methodol 13:61).
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

Weighting = Literal["quadratic", "identity"]


@dataclass(frozen=True)
class OrdinalAgreement:
    n: int
    categories: tuple[str, ...]
    observed_agreement: float
    cohen_kappa: float
    weighted_kappa: float
    gwet_ac2: float
    prevalence: dict[str, float]
    paradox_suspected: bool
    weighting: Weighting
    ci: dict[str, tuple[float, float]] | None = None


def _weight(i: int, j: int, k: int, weighting: Weighting) -> float:
    if i == j:
        return 1.0
    if k <= 1:
        return 1.0
    if weighting == "identity":
        return 0.0
    return 1.0 - ((i - j) ** 2) / ((k - 1) ** 2)  # quadratic agreement weight


def _coefficients(
    a_idx: Sequence[int], b_idx: Sequence[int], k: int, weighting: Weighting
) -> tuple[float, float, float, float, list[float]]:
    """Return (observed, cohen_kappa, weighted_kappa, gwet_ac2, prevalence) for index-coded
    ratings."""
    n = len(a_idx)
    # confusion matrix and marginals
    obs = [[0 for _ in range(k)] for _ in range(k)]
    a_marg = [0] * k
    b_marg = [0] * k
    for ai, bi in zip(a_idx, b_idx, strict=True):
        obs[ai][bi] += 1
        a_marg[ai] += 1
        b_marg[bi] += 1

    w = [[_weight(i, j, k, weighting) for j in range(k)] for i in range(k)]

    # observed (accuracy) and weighted observed agreement
    po = sum(obs[i][i] for i in range(k)) / n
    p_a_w = sum(w[i][j] * obs[i][j] for i in range(k) for j in range(k)) / n

    # Cohen's kappa (unweighted)
    pe_u = sum(a_marg[i] * b_marg[i] for i in range(k)) / (n * n)
    cohen = _ratio(po, pe_u)

    # weighted Cohen's kappa
    pe_w = sum(w[i][j] * a_marg[i] * b_marg[j] for i in range(k) for j in range(k)) / (n * n)
    wkappa = _ratio(p_a_w, pe_w)

    # Gwet's AC2 (weighted, paradox-resistant chance term)
    pi = [(a_marg[i] + b_marg[i]) / (2 * n) for i in range(k)]
    if k > 1:
        tw = sum(w[i][j] for i in range(k) for j in range(k))
        pe_g = (tw / (k * (k - 1))) * sum(p * (1 - p) for p in pi)
    else:
        pe_g = 0.0
    ac2 = _ratio(p_a_w, pe_g)

    return po, cohen, wkappa, ac2, pi


def _ratio(p_a: float, p_e: float) -> float:
    """(p_a - p_e) / (1 - p_e), with the standard degenerate handling when 1 - p_e == 0."""
    denom = 1.0 - p_e
    if abs(denom) < 1e-12:
        return 1.0 if p_a >= 1.0 - 1e-12 else 0.0
    return (p_a - p_e) / denom


def ordinal_agreement(
    rater_a: Sequence[str],
    rater_b: Sequence[str],
    categories: Sequence[str],
    *,
    weighting: Weighting = "quadratic",
    bootstrap: int = 0,
    seed: int | None = None,
    alpha: float = 0.05,
) -> OrdinalAgreement:
    """Ordinal agreement between two raters over an ORDERED ``categories`` list.

    ``categories`` must list every label in ordinal order (e.g. stage groups I..IV); the quadratic
    weights use each label's position. Bootstrap CIs are computed only when ``bootstrap > 0`` and a
    ``seed`` is given (so the result is reproducible).
    """
    if len(rater_a) != len(rater_b):
        raise ValueError(f"rater lengths differ: {len(rater_a)} vs {len(rater_b)}")
    if len(rater_a) == 0:
        raise ValueError("no ratings supplied")
    index = {c: i for i, c in enumerate(categories)}
    if len(index) != len(categories):
        raise ValueError("categories must be unique")
    try:
        a_idx = [index[v] for v in rater_a]
        b_idx = [index[v] for v in rater_b]
    except KeyError as exc:
        raise ValueError(f"value {exc.args[0]!r} not in categories") from exc

    k = len(categories)
    n = len(a_idx)
    po, cohen, wkappa, ac2, pi = _coefficients(a_idx, b_idx, k, weighting)
    prevalence = {c: round(pi[i], 6) for i, c in enumerate(categories)}
    # Kappa paradox: high observed agreement but a low unweighted kappa from skewed marginals.
    paradox = po >= 0.80 and cohen < 0.50

    ci: dict[str, tuple[float, float]] | None = None
    if bootstrap > 0:
        if seed is None:
            raise ValueError("bootstrap requires an explicit integer seed for reproducibility")
        rng = random.Random(seed)
        cols: dict[str, list[float]] = {
            "observed": [],
            "cohen_kappa": [],
            "weighted_kappa": [],
            "gwet_ac2": [],
        }
        for _ in range(bootstrap):
            pick = [rng.randrange(n) for _ in range(n)]
            ra = [a_idx[i] for i in pick]
            rb = [b_idx[i] for i in pick]
            bpo, bc, bw, bac2, _ = _coefficients(ra, rb, k, weighting)
            cols["observed"].append(bpo)
            cols["cohen_kappa"].append(bc)
            cols["weighted_kappa"].append(bw)
            cols["gwet_ac2"].append(bac2)
        ci = {name: _percentile_ci(vals, alpha) for name, vals in cols.items()}

    return OrdinalAgreement(
        n=n,
        categories=tuple(categories),
        observed_agreement=round(po, 6),
        cohen_kappa=round(cohen, 6),
        weighted_kappa=round(wkappa, 6),
        gwet_ac2=round(ac2, 6),
        prevalence=prevalence,
        paradox_suspected=paradox,
        weighting=weighting,
        ci=ci,
    )


def _percentile_ci(values: list[float], alpha: float) -> tuple[float, float]:
    s = sorted(values)
    m = len(s)
    lo = s[max(0, int((alpha / 2) * m))]
    hi = s[min(m - 1, int((1 - alpha / 2) * m))]
    return (round(lo, 6), round(hi, 6))
