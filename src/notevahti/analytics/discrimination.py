"""Discrimination metrics for the review flag / validity score (TRIPOD+AI: model performance).

The open Stage-1 question is whether NoteVahti's flag predicts true abstraction errors. This module
turns a run over a reference set into reportable discrimination:

- ``flag_discrimination`` — for the binary review flag: sensitivity, specificity, PPV/NPV at the
  SAMPLE prevalence and (crucially) recomputed at a stated DEPLOYMENT prevalence (a pilot's PPV does
  not transfer to a registry with a different error base-rate), plus error enrichment.
- ``score_discrimination`` — for a continuous validity score: AUROC (prevalence-independent) and
  AUPRC with its baseline (the error prevalence; AUPRC must be read against it, and AUPRC's
  superiority is debated, so both are reported).

Standard statistics, not a NoteVahti contribution. Evidence, not a guarantee. Deterministic; any
bootstrap takes an explicit integer seed.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class FlagDiscrimination:
    n: int
    errors: int
    flagged: int
    tp: int
    fp: int
    tn: int
    fn: int
    sensitivity: float
    specificity: float
    ppv_sample: float
    npv_sample: float
    sample_prevalence: float
    enrichment: float  # review error rate / accept error rate (inf if accept rate is 0)
    deployment_prevalence: float | None = None
    ppv_at_deployment: float | None = None
    npv_at_deployment: float | None = None
    enrichment_ci: tuple[float, float] | None = None


@dataclass(frozen=True)
class ScoreDiscrimination:
    n: int
    errors: int
    auroc: float
    auprc: float
    auprc_baseline: float  # = error prevalence; AUPRC is only meaningful against this
    auroc_ci: tuple[float, float] | None = None


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def ppv_at_prevalence(sensitivity: float, specificity: float, prevalence: float) -> float:
    num = sensitivity * prevalence
    den = num + (1.0 - specificity) * (1.0 - prevalence)
    return _safe_div(num, den)


def npv_at_prevalence(sensitivity: float, specificity: float, prevalence: float) -> float:
    num = specificity * (1.0 - prevalence)
    den = num + (1.0 - sensitivity) * prevalence
    return _safe_div(num, den)


def _confusion(flags: Sequence[bool], errors: Sequence[bool]) -> tuple[int, int, int, int]:
    tp = fp = tn = fn = 0
    for f, e in zip(flags, errors, strict=True):
        if e and f:
            tp += 1
        elif e and not f:
            fn += 1
        elif (not e) and f:
            fp += 1
        else:
            tn += 1
    return tp, fp, tn, fn


def flag_discrimination(
    flags: Sequence[bool],
    errors: Sequence[bool],
    *,
    deployment_prevalence: float | None = None,
    bootstrap: int = 0,
    seed: int | None = None,
    alpha: float = 0.05,
) -> FlagDiscrimination:
    if len(flags) != len(errors):
        raise ValueError(f"length mismatch: {len(flags)} flags vs {len(errors)} errors")
    if len(flags) == 0:
        raise ValueError("no observations supplied")
    tp, fp, tn, fn = _confusion(flags, errors)
    n = tp + fp + tn + fn
    sens = _safe_div(tp, tp + fn)
    spec = _safe_div(tn, tn + fp)
    ppv = _safe_div(tp, tp + fp)
    npv = _safe_div(tn, tn + fn)
    review_rate = _safe_div(tp, tp + fp)
    accept_rate = _safe_div(fn, tn + fn)
    enrichment = (review_rate / accept_rate) if accept_rate else float("inf")

    ppv_dep = npv_dep = None
    if deployment_prevalence is not None:
        if not 0.0 <= deployment_prevalence <= 1.0:
            raise ValueError("deployment_prevalence must be in [0, 1]")
        ppv_dep = ppv_at_prevalence(sens, spec, deployment_prevalence)
        npv_dep = npv_at_prevalence(sens, spec, deployment_prevalence)

    enrich_ci: tuple[float, float] | None = None
    if bootstrap > 0:
        if seed is None:
            raise ValueError("bootstrap requires an explicit integer seed")
        rng = random.Random(seed)
        vals: list[float] = []
        idx = range(n)
        for _ in range(bootstrap):
            pick = [rng.randrange(n) for _ in idx]
            bf = [flags[i] for i in pick]
            be = [errors[i] for i in pick]
            btp, bfp, btn, bfn = _confusion(bf, be)
            br = _safe_div(btp, btp + bfp)
            ba = _safe_div(bfn, btn + bfn)
            vals.append((br / ba) if ba else float("inf"))
        finite = sorted(v for v in vals if v != float("inf"))
        if finite:
            m = len(finite)
            lo = finite[max(0, int((alpha / 2) * m))]
            hi = finite[min(m - 1, int((1 - alpha / 2) * m))]
            enrich_ci = (round(lo, 4), round(hi, 4))

    return FlagDiscrimination(
        n=n,
        errors=tp + fn,
        flagged=tp + fp,
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
        sensitivity=round(sens, 4),
        specificity=round(spec, 4),
        ppv_sample=round(ppv, 4),
        npv_sample=round(npv, 4),
        sample_prevalence=round(_safe_div(tp + fn, n), 4),
        enrichment=round(enrichment, 4) if enrichment != float("inf") else enrichment,
        deployment_prevalence=deployment_prevalence,
        ppv_at_deployment=round(ppv_dep, 4) if ppv_dep is not None else None,
        npv_at_deployment=round(npv_dep, 4) if npv_dep is not None else None,
        enrichment_ci=enrich_ci,
    )


def _auroc(risk: Sequence[float], labels: Sequence[bool]) -> float:
    """AUROC via the rank (Mann-Whitney) estimator with average ranks for ties."""
    order = sorted(range(len(risk)), key=lambda i: risk[i])
    ranks = [0.0] * len(risk)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and risk[order[j + 1]] == risk[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    n_pos = sum(1 for x in labels if x)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    sum_ranks_pos = sum(ranks[i] for i, x in enumerate(labels) if x)
    return (sum_ranks_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def _auprc(risk: Sequence[float], labels: Sequence[bool]) -> float:
    """Average precision (step), processing tied risks together."""
    total_pos = sum(1 for x in labels if x)
    if total_pos == 0:
        return float("nan")
    order = sorted(range(len(risk)), key=lambda i: -risk[i])
    tp = fp = 0
    ap = 0.0
    prev_recall = 0.0
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and risk[order[j + 1]] == risk[order[i]]:
            j += 1
        for k in range(i, j + 1):
            if labels[order[k]]:
                tp += 1
            else:
                fp += 1
        recall = tp / total_pos
        precision = tp / (tp + fp)
        ap += (recall - prev_recall) * precision
        prev_recall = recall
        i = j + 1
    return ap


def score_discrimination(
    scores: Sequence[float],
    errors: Sequence[bool],
    *,
    higher_is_error: bool = True,
    bootstrap: int = 0,
    seed: int | None = None,
    alpha: float = 0.05,
) -> ScoreDiscrimination:
    """AUROC and AUPRC of ``scores`` predicting ``errors``.

    Set ``higher_is_error=False`` for a validity score (where a HIGHER score means LESS likely an
    error); the metric then ranks by error risk = -score.
    """
    if len(scores) != len(errors):
        raise ValueError(f"length mismatch: {len(scores)} scores vs {len(errors)} errors")
    if len(scores) == 0:
        raise ValueError("no observations supplied")
    risk = [s if higher_is_error else -s for s in scores]
    auroc = _auroc(risk, errors)
    auprc = _auprc(risk, errors)
    n = len(scores)
    n_pos = sum(1 for x in errors if x)

    auroc_ci: tuple[float, float] | None = None
    if bootstrap > 0:
        if seed is None:
            raise ValueError("bootstrap requires an explicit integer seed")
        rng = random.Random(seed)
        vals: list[float] = []
        for _ in range(bootstrap):
            pick = [rng.randrange(n) for _ in range(n)]
            br = [risk[i] for i in pick]
            be = [errors[i] for i in pick]
            a = _auroc(br, be)
            if a == a:  # not NaN
                vals.append(a)
        if vals:
            vals.sort()
            m = len(vals)
            lo = vals[max(0, int((alpha / 2) * m))]
            hi = vals[min(m - 1, int((1 - alpha / 2) * m))]
            auroc_ci = (round(lo, 4), round(hi, 4))

    return ScoreDiscrimination(
        n=n,
        errors=n_pos,
        auroc=round(auroc, 4) if auroc == auroc else auroc,
        auprc=round(auprc, 4) if auprc == auprc else auprc,
        auprc_baseline=round(n_pos / n, 4),
        auroc_ci=auroc_ci,
    )
