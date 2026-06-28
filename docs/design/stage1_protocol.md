# Stage-1 protocol — preregistration + evidence pack

Status: tooling implemented (`notevahti.analytics.preregistration`, `notevahti.analytics.evidence_pack`),
2026-06. This is the audit-#5 gate: a frozen, preregistered analysis and a machine-assembled report
**before** any weight tuning. It does not change the validation core.

## The open question (Stage 1)

Does NoteVahti's review flag predict *true* abstraction errors on real MDT notes? Until a Stage-1
study answers this, NoteVahti claims mechanism, not predictive value. See
[docs/design/pathway.md](pathway.md).

## Order of operations (non-negotiable)

1. **Freeze the configuration.** The validity weights, review threshold and routing policy are fixed
   and recorded as a heuristic card (version + `config_hash`) in the evidence pack. No tuning after
   this point for the study.
2. **Preregister.** `preregistration_markdown()` emits an OSF-style analysis-plan skeleton — primary
   metrics (flag error-enrichment, validity-score AUROC), hypotheses with CI conditions, mandatory
   subgroups, the **reference-standard independence** requirement, calibration/DCA plan, and an
   explicit **kill criterion**. Register it before unblinding.
3. **Run silently** against a reference cohort whose gold values were adjudicated *without* NoteVahti
   and *without* the extractor under test (independence applies to the study, not just the code).
4. **Emit the evidence pack.** `build_evidence_pack(observations, subgroup_dims=...)` →
   `to_markdown(pack)` assembles the machine-computable TRIPOD+AI sections.

## What the evidence pack computes (and does not)

Machine sections (filled): heuristic/model card (version, weights, threshold, routes, config hash);
data summary (n, errors, prevalence); overall discrimination (sensitivity, specificity, PPV/NPV at a
stated **deployment** prevalence, enrichment with CI; AUROC, AUPRC with its baseline); **subgroup**
discrimination (by language, field, …) because pooled numbers hide failures.

Human sections (NOT generated — listed in `human_sections`): background and objectives; intended use
and the research/quality boundary; data source and how the reference standard was established;
limitations and risks of bias; clinical interpretation.

## Demonstration (synthetic only)

`scripts/stage1_report.py` runs the whole pipeline over `corpus/synthetic_clinical_notes` (gold never
fed to the validator) and prints the pack + preregistration. On that synthetic set the flag shows
specificity 1.0, sensitivity ~0.60, enrichment ~66× (CI ~48–101), validity-score AUROC ~0.80
(CI ~0.74–0.86). **This is a methodology demonstration on synthetic data — not validation evidence.**
A real result requires a real, independent reference cohort (e.g. via Findata).

## Boundaries carried through

- Not a medical device; not clinical advice; evidence, not a guarantee.
- Discrimination is not calibration; no distribution-free / conformal coverage is claimed.
- A negative result (the flag does not enrich above chance) is publishable, not buried — that is the
  kill criterion, written into the preregistration.
