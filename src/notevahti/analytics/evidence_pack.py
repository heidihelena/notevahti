"""Stage-1 evidence pack (TRIPOD+AI-aligned) — assemble the machine-computable report sections.

Given a reference run as a list of :class:`Observation` (per field: was it a true against-gold
error, did the flag fire, what was the validity score, and which subgroups it belongs to), this
builds the parts of a TRIPOD+AI report that can be computed automatically: a dataset summary,
overall and per-subgroup discrimination, and a heuristic/version card pinning exactly which
NoteVahti configuration produced the numbers. Narrative sections (background, intended use,
limitations, clinical interpretation) are deliberately left to a human (see ``human_sections``).

Standard statistics, not a NoteVahti contribution. Evidence, not a guarantee. Deterministic: the
bootstrap takes an explicit integer seed. This reports a run; it does not make data trustworthy, and
synthetic inputs produce a synthetic-only report (say so in the narrative).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field

from .. import __version__
from ..routing import ROUTES
from ..validity import DEFAULT_THRESHOLD, DEFAULT_WEIGHTS
from .discrimination import (
    FlagDiscrimination,
    ScoreDiscrimination,
    flag_discrimination,
    score_discrimination,
)

HUMAN_SECTIONS = (
    "background and objectives",
    "intended use and the research/quality boundary",
    "data source and how the reference standard was established (and its independence)",
    "limitations and risks of bias",
    "clinical interpretation",
)


@dataclass(frozen=True)
class Observation:
    """One validated field in a reference run."""

    error: bool  # true against-gold error (the outcome being predicted)
    flagged: bool  # did the review flag fire
    validity_score: float
    subgroups: dict[str, str] = field(
        default_factory=dict
    )  # e.g. {"language": "fi", "field": "stage"}


@dataclass(frozen=True)
class HeuristicCard:
    """Which NoteVahti configuration produced the metrics (TRIPOD+AI model specification)."""

    notevahti_version: str
    validity_weights: dict[str, float]
    review_threshold: float
    routes: tuple[str, ...]
    config_hash: str


@dataclass(frozen=True)
class SubgroupReport:
    dimension: str
    value: str
    n: int
    n_errors: int
    flag: FlagDiscrimination
    score: ScoreDiscrimination


@dataclass(frozen=True)
class EvidencePack:
    n: int
    n_errors: int
    error_prevalence: float
    deployment_prevalence: float
    overall_flag: FlagDiscrimination
    overall_score: ScoreDiscrimination
    subgroups: list[SubgroupReport]
    card: HeuristicCard
    human_sections: tuple[str, ...]
    caveats: list[str]


def default_heuristic_card() -> HeuristicCard:
    """Card describing the live default validity/routing configuration."""
    material = json.dumps(
        {
            "version": __version__,
            "validity_weights": DEFAULT_WEIGHTS,
            "review_threshold": DEFAULT_THRESHOLD,
            "routes": list(ROUTES),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return HeuristicCard(
        notevahti_version=__version__,
        validity_weights=dict(DEFAULT_WEIGHTS),
        review_threshold=DEFAULT_THRESHOLD,
        routes=ROUTES,
        config_hash=digest,
    )


def _discriminate(
    obs: Sequence[Observation], *, deployment_prevalence: float, seed: int, bootstrap: int
) -> tuple[FlagDiscrimination, ScoreDiscrimination]:
    flags = [o.flagged for o in obs]
    errors = [o.error for o in obs]
    scores = [o.validity_score for o in obs]
    fd = flag_discrimination(
        flags, errors, deployment_prevalence=deployment_prevalence, bootstrap=bootstrap, seed=seed
    )
    sd = score_discrimination(scores, errors, higher_is_error=False, bootstrap=bootstrap, seed=seed)
    return fd, sd


def build_evidence_pack(
    observations: Sequence[Observation],
    *,
    subgroup_dims: Sequence[str] = (),
    deployment_prevalence: float = 0.05,
    seed: int = 0,
    bootstrap: int = 1000,
    card: HeuristicCard | None = None,
) -> EvidencePack:
    """Assemble the machine-computable evidence pack from a reference run.

    Subgroup reporting (one section per value of each ``subgroup_dims`` key, e.g. ``"language"`` and
    ``"field"``) is mandatory honesty: pooled numbers hide where the flag fails (Simpson's paradox).
    """
    if len(observations) == 0:
        raise ValueError("no observations supplied")
    card = card or default_heuristic_card()
    overall_flag, overall_score = _discriminate(
        observations, deployment_prevalence=deployment_prevalence, seed=seed, bootstrap=bootstrap
    )

    subgroups: list[SubgroupReport] = []
    for dim in subgroup_dims:
        groups: dict[str, list[Observation]] = {}
        for o in observations:
            if dim in o.subgroups:
                groups.setdefault(o.subgroups[dim], []).append(o)
        for value in sorted(groups):
            grp = groups[value]
            fd, sd = _discriminate(
                grp, deployment_prevalence=deployment_prevalence, seed=seed, bootstrap=bootstrap
            )
            subgroups.append(
                SubgroupReport(
                    dimension=dim,
                    value=value,
                    n=len(grp),
                    n_errors=sum(1 for o in grp if o.error),
                    flag=fd,
                    score=sd,
                )
            )

    n = len(observations)
    n_err = sum(1 for o in observations if o.error)
    caveats = [
        "AUPRC must be read against its baseline (the error prevalence).",
        "PPV/NPV are at the stated deployment prevalence; a pilot's PPV does not transfer.",
        "Discrimination is not calibration and not a guarantee of correctness.",
        "Synthetic inputs give a synthetic-only report; that is not validation evidence.",
    ]
    return EvidencePack(
        n=n,
        n_errors=n_err,
        error_prevalence=round(n_err / n, 4),
        deployment_prevalence=deployment_prevalence,
        overall_flag=overall_flag,
        overall_score=overall_score,
        subgroups=subgroups,
        card=card,
        human_sections=HUMAN_SECTIONS,
        caveats=caveats,
    )


def to_markdown(pack: EvidencePack) -> str:
    """Render the pack as a TRIPOD+AI-aligned report skeleton (machine sections filled)."""
    fd, sd = pack.overall_flag, pack.overall_score
    lines = [
        "# NoteVahti Stage-1 evidence pack (TRIPOD+AI-aligned, machine sections)",
        "",
        "> Machine-computable sections only. The *Narrative (human)* sections must be written",
        "> by a person; this tool does not generate them.",
        "",
        "## Heuristic / model specification",
        f"- NoteVahti version: `{pack.card.notevahti_version}`",
        f"- config hash: `{pack.card.config_hash}`",
        f"- validity weights: {pack.card.validity_weights}",
        f"- review threshold: {pack.card.review_threshold}",
        f"- routes: {', '.join(pack.card.routes)}",
        "",
        "## Data summary",
        f"- fields validated (n): {pack.n}",
        f"- true errors: {pack.n_errors}  (error prevalence {pack.error_prevalence})",
        f"- deployment prevalence used for PPV/NPV: {pack.deployment_prevalence}",
        "",
        "## Discrimination (overall)",
        f"- flag: sensitivity {fd.sensitivity}, specificity {fd.specificity}, "
        f"PPV(sample) {fd.ppv_sample}, NPV(sample) {fd.npv_sample}",
        f"- flag at deployment prevalence: PPV {fd.ppv_at_deployment}, NPV {fd.npv_at_deployment}",
        f"- flag enrichment: {fd.enrichment}  (95% CI {fd.enrichment_ci})",
        f"- validity score: AUROC {sd.auroc} (95% CI {sd.auroc_ci}), "
        f"AUPRC {sd.auprc} (baseline {sd.auprc_baseline})",
        "",
        "## Discrimination (subgroups)",
    ]
    if pack.subgroups:
        lines.append("| dimension | value | n | errors | sensitivity | specificity | AUROC |")
        lines.append("|---|---|---|---|---|---|---|")
        for s in pack.subgroups:
            lines.append(
                f"| {s.dimension} | {s.value} | {s.n} | {s.n_errors} | "
                f"{s.flag.sensitivity} | {s.flag.specificity} | {s.score.auroc} |"
            )
    else:
        lines.append("_no subgroup dimensions requested_")
    lines += ["", "## Caveats"]
    lines += [f"- {c}" for c in pack.caveats]
    lines += ["", "## Narrative (human) — required, not generated"]
    lines += [f"- {s}" for s in pack.human_sections]
    return "\n".join(lines) + "\n"
