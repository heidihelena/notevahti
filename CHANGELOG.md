# Changelog

All notable changes to NoteVahti are documented here. Format loosely follows Keep a Changelog.

## [Unreleased] — Stage 0 validation harness

### Added
- **Core types** (`notevahti.types`): `ValidationRecord` and the five output types, plus `Lineage`,
  `Signal`, `FieldSpec`, `ExtractionResult`. JSON-serializable via `to_dict()`.
- **Provenance** (`verify_span`): binds a value to a verified source span (exact → case-insensitive
  → whitespace-flexible → compact-for-staging), or flags a likely hallucination when absent.
- **Independence** (`check_independence`): enforces the independent-anchor rule — refuses circular
  validation; UNKNOWN when lineage is undeclared.
- **Validity** (`score_validity`): transparent, rule-based, per-field-type heuristic with visible
  weights and a review flag. Explicitly **not** a calibrated/guaranteed error rate.
- **Agreement** (`agreement`): Cohen's κ and accuracy vs a reference set; `not_available` otherwise.
- **Audit** (`AuditLog`): append-only, hash-chained JSONL; tamper-evident; PHI hashed by default.
- **Orchestrator** (`validate_field`): wires the five outputs into one `ValidationRecord`.
- **Extractor interface** (`Extractor` Protocol) with `PassThroughExtractor` and `RegexExtractor`
  example adapters. No production extractor; the core runs with any extractor or none.
- **Batch** (`validate_batch`) and **CLI** (`notevahti validate`).
- Synthetic lung-cancer MDT corpus fixture with known ground truth (incl. adversarial cases).
- **Synthetic MDT corpus generator** (`scripts/gen_corpus.py`): deterministic, offline, seeded.
  Three modalities mirroring the NTOG tools — free text (fi/sv/nb/da/is/en), semistructured (EN),
  fully structured (EN) — at 500 cases/group (4000 total). Six gold fields per case with exact source
  spans (histology, clinical_stage/cTNM, treatment intent, treatment, PD-L1 TPS, driver alteration).
  Every gold span verifies through NoteVahti's own provenance check (100%). The exact generated
  dataset is committed under `corpus/` (so the corpus is reproducible, not only regenerable from the
  seed); it can also be rebuilt deterministically with the generator.
  Each case also carries a `challenges` block: `surface_variant` (correct value, non-verbatim
  surface — 100% validate as correct) and `present_but_wrong` (wrong value that appears in the note
  as the pre-MDT cTNM — found by provenance, not a hallucination). The present-but-wrong cases
  surfaced a real weighting issue (a disagreeing independent anchor originally flagged only ~13% of
  them), now fixed by the validity rule below.

### Added (Stage-1 evidence machinery)
- **Ordinal agreement analytics** (`notevahti.analytics.agreement.ordinal_agreement`): for ordered
  categories (e.g. TNM stage groups) — observed agreement, unweighted Cohen's κ, quadratic-weighted
  κ, Gwet's AC2 (paradox-resistant), per-category prevalence, a kappa-paradox flag, and optional
  deterministic (seeded) percentile bootstrap CIs. Separate from the deterministic core. Hand-verified
  against worked examples (κ 0.644 → weighted 0.804 → AC2 0.833; paradox case κ −0.05 vs AC2 0.89).
- **External synthetic clinical-note dataset** (`corpus/synthetic_clinical_notes/`, 150 notes —
  en/fi/sv — with gold labels, simulated extractions and seeded failure modes) plus a Stage-1
  enrichment eval (`scripts/eval_clinical_notes.py`). Honest result (gold never fed to the validator):
  the review flag concentrates true against-gold errors at **~66× enrichment** with **100% review
  precision** and **60% sensitivity**. It catches absence-type errors (unsupported_value, unit_format,
  negation_trap: all caught) but — as a recorded limitation (audit #2/#3) — misses present-but-wrong
  errors (temporal_trap, copy_forward_old_stage, source_conflict: 0 caught), which need temporality
  and independent-anchor signals. Characterized by `tests/test_external_clinical_notes.py`.

### Changed (engineering)
- The codebase is now **`mypy --strict` clean** (13 modules); strict config added to `pyproject.toml`
  and `mypy` added to the dev extra. (Further WP-A tooling — ruff, Hypothesis, pytest-socket, CI —
  is pending network access to install/verify.)
- **Validity correctness rule:** a *disagreeing* independent anchor (anchor_agreement < 1 with ≥1
  independent anchor) now forces `flag_for_human_review` regardless of score — a disagreeing
  independent second source is the canonical adjudication trigger. Present-but-wrong flagging went
  from ~13% to 100% on the synthetic corpus; correct surface-variant pass rate stays at 100%.
- Test asserting the validation core makes no network calls. 60 tests, deterministic, offline.

### Project docs
- Design note, research → validated-tool pathway, deep-research evidence base, and SKILL.md build
  playbook under `docs/` and `SKILL.md`.

### Boundary
- Not a medical device; not clinical advice. Produces validation evidence for human review, not a
  guarantee of correctness. No distribution-free / conformal coverage guarantee is claimed (the
  evidence refuted them for this setting).
