"""Stage-1 preregistration skeleton (OSF-style) for the validity-flag study.

Preregistration is rare (~1% of studies); NoteVahti makes it the default. This emits an
analysis-plan skeleton -- primary metric and threshold, hypotheses, mandatory subgroups, the
reference-standard independence requirement, the calibration/DCA plan, and an explicit kill
criterion -- to be committed *before* unblinding and *before* any weight tuning (the frozen-weights
discipline). It is a template: the human fills cohort specifics (source, size justification,
ethics/permits). It generates no data and asserts no result.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PreregSpec:
    title: str = "Does the NoteVahti review flag predict true abstraction errors? (Stage-1, silent)"
    primary_question: str = (
        "Among fields routed to review by NoteVahti, is the rate of true against-gold errors "
        "higher than among accepted fields (error enrichment), and does the validity score "
        "discriminate errors (AUROC)?"
    )
    primary_metrics: tuple[str, ...] = (
        "review-flag error enrichment (review error rate / accept error rate) with 95% CI",
        "validity-score AUROC with 95% CI",
    )
    frozen_config_threshold: float = 0.80
    subgroups: tuple[str, ...] = ("language", "field type", "field name")
    deployment_prevalence_note: str = (
        "Report PPV/NPV at the registry's expected error prevalence, not the study's."
    )
    hypotheses: tuple[str, ...] = (
        "H1: error enrichment (review vs accept) > 1 with the 95% CI excluding 1.",
        "H2: validity-score AUROC > 0.5 with the 95% CI excluding 0.5.",
    )
    kill_criterion: str = (
        "If the flag does not concentrate errors above chance (H1/H2 not met), redesign or publish "
        "the negative result; do not expand scope and do not tune weights to recover a result."
    )
    notes: tuple[str, ...] = field(default_factory=tuple)


def preregistration_markdown(spec: PreregSpec | None = None) -> str:
    """Render the preregistration skeleton as markdown (placeholders for human-supplied parts)."""
    s = spec or PreregSpec()
    todo = "_TODO (human): _"
    lines = [
        f"# Preregistration — {s.title}",
        "",
        "Status: DRAFT to be registered (e.g. OSF) BEFORE unblinding and BEFORE any weight tuning.",
        "NoteVahti config is frozen for this study (see the heuristic card / config hash in the",
        "evidence pack). This document asserts no result.",
        "",
        "## 1. Study question",
        s.primary_question,
        "",
        "## 2. Design",
        "- Retrospective, **silent** (NoteVahti output does not influence the registry entry).",
        "- Unit of analysis: one extracted field per case.",
        "- Inputs: extracted value + source note. NoteVahti runs unchanged, offline, in the secure",
        "  environment; gold is never fed to the validator.",
        "",
        "## 3. Reference standard and independence (load-bearing)",
        "- The gold (reference) values are adjudicated **without** NoteVahti and **without** the",
        "  extractor under test — the independence rule applies to the *study*, not just the code.",
        f"- {todo} who adjudicates, adjudication procedure, disagreement handling.",
        "",
        "## 4. Primary metrics and hypotheses",
        *[f"- primary metric: {m}" for m in s.primary_metrics],
        *[f"- {h}" for h in s.hypotheses],
        f"- frozen review threshold (validity): {s.frozen_config_threshold}",
        "",
        "## 5. Secondary / supporting",
        "- sensitivity, specificity, PPV/NPV. " + s.deployment_prevalence_note,
        "- calibration of the validity score (calibration slope & intercept, Brier) — reported,",
        "  not guaranteed; no claim of distribution-free coverage.",
        "- decision-curve analysis (net benefit) for acting on the flag.",
        "",
        "## 6. Mandatory subgroups (pooled numbers hide failures)",
        *[f"- by {g}" for g in s.subgroups],
        "",
        "## 7. Sample size",
        f"- {todo} target n and justification (precision of enrichment/AUROC CI at the expected",
        "  error prevalence).",
        "",
        "## 8. Kill / scale criterion",
        s.kill_criterion,
        "",
        "## 9. Data governance",
        f"- {todo} permit (e.g. Findata), pseudonymisation, secure-environment confirmation.",
        "",
        "## 10. Boundary",
        "- Not a medical device; not clinical advice. Validation evidence for human review, not a",
        "  guarantee of correctness.",
    ]
    if s.notes:
        lines += ["", "## Notes", *[f"- {n}" for n in s.notes]]
    return "\n".join(lines) + "\n"
