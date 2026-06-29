# NoteVahti — research framing (for funding and review)

A concise scientific framing for reviewers and funders. NoteVahti is a research/quality tool, **not a
medical device**; it produces validation evidence for human review, not a guarantee of correctness.

## Background and problem

Clinical quality registries depend on data abstracted from unstructured notes — for thoracic
oncology, the multidisciplinary team (MDT) meeting note is the authoritative source for stage and
treatment decisions. Manual abstraction is the registry bottleneck. Automated clinical NLP and LLM
extractors are increasingly accurate but **opaque**: a registry of record cannot accept values it
cannot audit. LLM hallucination is unsolved and frequent; raw extraction accuracy alone has not
translated into registry workflow benefit; and flat source citations are too coarse for verification
and are themselves often hallucinated. (Evidence base with citations:
[research/notevahti-research-2026-06.md](research/notevahti-research-2026-06.md).)

## Gap and hypothesis

The unmet need is a **transparent, local-first, validity-scored, auditable trust layer** around
extraction — independent of any extractor. Central testable hypothesis (Stage 1): *a deterministic
validation layer that binds each value to its source span, enforces non-circular corroboration, and
flags low-confidence fields concentrates true abstraction errors into the review set far above
chance*, and does so consistently across Nordic languages.

## Approach (what is built)

A deterministic, offline, dependency-free core producing one auditable record per field:
provenance (verified span or hallucination flag), a transparent validity heuristic + review flag,
agreement vs a reference (κ/accuracy; ordinal weighted-κ and Gwet's AC2 for staging), a
**non-circular independent-anchor** check, and a tamper-evident hash-chained audit entry. An optional
trigger-gated **review router** turns the evidence into an auditable route (accept / review /
specialist_review / blocked). The honest-novelty boundary is the *representation and auditability*,
not the NLP or the statistics.

## Evaluation design

Stage-1 is **preregistered with the configuration frozen** before any tuning. Primary endpoints:
review-flag error enrichment and validity-score AUROC, each with bootstrap CIs; secondary:
sensitivity/specificity, PPV/NPV at the deployment prevalence, calibration (slope/intercept, Brier;
reported, not guaranteed), and decision-curve net benefit. **Mandatory subgroup reporting by
language** (fi/sv/nb/da/is/en) and field. Reference values are adjudicated **independently** of
NoteVahti and of the extractor under test. Reporting follows TRIPOD+AI (and STARD-AI / DECIDE-AI at
later stages). An explicit **kill criterion**: if the flag does not enrich errors above chance, the
negative result is published and the design revised — scope is not expanded and weights are not tuned
to recover a result. Tooling: `notevahti.analytics.{evidence_pack,preregistration}` and
`scripts/stage1_report.py`.

## Preliminary (synthetic) signal

On a synthetic clinical-note set (gold never fed to the validator) the flag shows ~66× error
enrichment (95% CI ~48–101), specificity 1.0, sensitivity ~0.60, and validity-score AUROC ~0.80
(CI ~0.74–0.86), with the failure modes it cannot yet catch characterised explicitly. **This is a
methodology demonstration on synthetic data, not validation evidence.**

## Data protection and reproducibility

Local-first by design: the core makes no network calls (enforced by test), has no runtime
dependencies, and hashes PHI in the audit record by default — it can run unchanged inside a
secure-environment secondary-use regime (e.g. Finland's Findata; GDPR-aligned). Fully deterministic
and seeded; Apache-2.0; `CITATION.cff`; `ruff` + `mypy --strict` + socket-disabled tests in CI; a
reproducible, committed multilingual synthetic corpus and generator.

## Impact

If the Stage-1 hypothesis holds, NoteVahti gives Nordic registries a transparent way to safely adopt
faster (including AI) abstraction without surrendering auditability — concentrating scarce expert
review where it changes the record. If it does not hold, the preregistered negative result is itself a
useful, publishable contribution to the clinical-NLP trust literature.

## Stage gates and indicative milestones

1. **Stage 0 (done):** deterministic harness + routing + analytics + synthetic corpus.
2. **Stage 1 (next; needs data):** retrospective silent validation on an independent Nordic
   reference cohort; preregistration filed; TRIPOD+AI evidence pack emitted.
3. **Stage 2:** prospective silent validation; drift/calibration monitoring.
4. **Stage 3 (boundary):** early, small-scale human-in-the-loop evaluation (DECIDE-AI) — does it help
   abstractors without harm or excess cognitive load.
5. **Stage 4 (out of current scope):** comparative evaluation / certification only if a clinical
   claim is ever chosen, with legal review of the EU MDR/AI-Act intended-purpose boundary.

## What funding would support

The next step is not engineering but **an independent reference cohort and the preregistered Stage-1
study** (data access/permits, adjudication of an independent reference standard, prospective
follow-up), plus native clinical-language review of the multilingual material.
