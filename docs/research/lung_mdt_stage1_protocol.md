# Stage-1 validation protocol — lung-cancer MDT notes (preregisterable)

Status: draft analysis plan for a preregisterable study (e.g. OSF). NoteVahti is a research/quality
tool, **not a medical device**; it produces validation evidence for human review, not a guarantee of
correctness. The machine-computable parts are emitted by `notevahti.analytics`
(`preregistration_markdown`, `build_evidence_pack`); this document is the human narrative.

## Question

Across Nordic-language lung-cancer MDT notes, does NoteVahti's validation layer (provenance, validity
flag, independence, routing) concentrate true extraction errors into the review set and let
genuinely-correct values through — for a registry workflow, and consistently across languages and
documentation formats?

## Primary fields

- **MDT discussion documented** (`mdt_discussed`)
- **ECOG/WHO performance status**
- **TNM staging** (clinical/pathological)

## Study phases

**A. Synthetic Nordic corpus (methodology only).** Run the whole pipeline on the committed synthetic
corpora (`corpus/`) across fi/sv/nb/da/is/en and the three documentation formats. Purpose: pin the
frozen configuration, exercise the analytics, and check operating characteristics. **Synthetic
results are not validation evidence.**

**B. Real 2024 national lung-cancer registry validation cohort.** Retrospective, **silent**
(NoteVahti does not influence the registry entry). Gold values are adjudicated **independently** of
NoteVahti and of the extractor under test, inside the national secure-environment secondary-use
regime (e.g. Findata; equivalents in SE/NO/DK/IS). Gold is never fed to the validator. This phase
answers the question.

**C. Quality-indicator readiness analysis.** Using the validated outputs, estimate the registry-ready
yield and the residual review burden for the primary fields, and whether NoteVahti could support
quality-indicator reporting (e.g. documented MDT discussion rate, PS completeness) without
surrendering auditability. Readiness analysis, not a deployment claim.

## Comparators

Each extractor is evaluated **with and without** NoteVahti validation + routing:

- **rule-based NoteVahti extractor** (`notevahti.extractors.rules`, `rules_v2`)
- **small LLM extractor** — described as an **external, optional adapter only** (not in this repo; no
  cloud calls in the core path)
- **fine-tuned LLM extractor** — described as an **external, optional adapter only**

The point is not which extractor wins, but whether NoteVahti's validation/routing safely separates
auto-acceptable from review-needed values regardless of the extractor.

## Primary outcomes

- **Correctly auto-accepted extraction rate** — of values NoteVahti auto-accepts (not flagged, not
  blocked, span present, score ≥ threshold), the fraction that match expert annotation.
- **Falsely auto-accepted extraction rate** — of auto-accepted values, the fraction that are wrong
  (the key safety metric).
- **Registry-ready yield** — fraction of attempted fields auto-acceptable (`registry_ready_yield`).
- **Review-flag sensitivity for true extraction errors** — of truly wrong extractions, the fraction
  routed to review/blocked.
- **Field-level exact match** against expert annotation (with the field's normalisation; ordinal
  weighted-κ / AC2 for stage).

## Secondary outcomes

- coverage; parse-failure rate; ambiguity rate; blocked rate; specialist-review rate
- **per-language** performance (fi/sv/nb/da/is/en) — reported separately, never only pooled
- **per-documentation-format** performance: free text, mini structured MDT, full structured MDT v3.1

## Analysis and reporting

Configuration frozen and preregistered before unblinding (no weight tuning afterwards). Discrimination
(AUROC/AUPRC with CIs), PPV/NPV at the registry's deployment prevalence, calibration (slope/intercept,
Brier — reported, not guaranteed), and decision-curve net benefit. Reporting follows TRIPOD+AI (and
STARD-AI / DECIDE-AI at later stages). All metrics reported per language and per format. Evidence
pack via `scripts/stage1_report.py` / `build_evidence_pack`.

## Negative-result policy (explicit)

If the review flag or validity score does **not** predict true abstraction errors — i.e. the
falsely-auto-accepted rate is not acceptably low and review-flag sensitivity is not above chance —
this is reported as the **main finding**, and **no deployment readiness is claimed**. The design is
revised or the negative result is published; scope is not expanded and weights are not tuned to
recover a result.

## Boundaries

Not a medical device; not clinical advice. No conformal coverage or guaranteed error rate is claimed.
PHI never leaves the secure environment; the validation core is local-first and offline.
