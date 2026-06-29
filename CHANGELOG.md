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
  example adapters (now in the `notevahti.extractors` package; imports unchanged via re-export). No
  production extractor; the core runs with any extractor or none.
- **Deterministic rule-based extractor** (`notevahti.extractors.rules.RuleBasedExtractor`, catalogue
  `rules_v1`): stdlib-only (`re`), offline, negation-aware extractor for lung-cancer MDT notes in
  Finnish/Swedish/English — clinical/pathological TNM, stage group, histology, location/laterality,
  biomarkers (EGFR/ALK/ROS1/BRAF/KRAS/MET/RET, PD-L1 TPS), performance status, treatment intent/plan.
  Returns values bound to exact source spans (surface text = `note[span]`), prefers explicit no-value
  over guessing, flags ambiguity for single-valued fields, and returns all findings for multi-valued
  fields via `candidates()`. Lineage `model_id="rules_v1"` (`rules_lineage()`), independent of any LLM
  and of NoteVahti's logic. Golden (fi/sv/en) + negation + determinism + offline + span-fidelity +
  end-to-end tests. See `docs/design/extractor_rules.md`.
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
  Opt-in **error-injection mode** (`--errors RATE`, default 0.0): emits, per gold field, a labelled
  `extractions` list (gold or a seeded corruption — `unsupported_value` absent-type, or
  `copy_forward_old_stage` present-but-wrong) at a controllable rate, on a separate rng stream so the
  notes stay byte-identical regardless of rate. A dev/CI/methodology instrument to scale the
  analytics — **not** validation evidence; the committed corpus is unaffected.

### Added / Changed (Stage-1 lung-MDT alignment)
- **Rule extractor strengthened:** `parse_tnm` (structural TNM: prefix c/yc/p/yp/unknown, T/N/M,
  completeness complete/partial/absent/ambiguous, edition, review flag; conflicts → ambiguous, no
  guess); ECOG/WHO/PS incl. Finnish/Swedish and temporal/indirect handling; new **`mdt_discussed`**
  field that accepts only a *documented* MDT (future/planned/negated suppressed).
- **`notevahti.analytics.registry_yield.registry_ready_yield`** — fraction of records NoteVahti would
  auto-accept (not flagged, span present, not blocked, score ≥ threshold) with diagnostic counts; an
  operational readiness number, not a correctness claim.
- **CLI `extract-validate`** — run the reference extractor, then validate + route each value
  end-to-end, with optional audit; the existing `validate` command is unchanged.
- **Docs:** README now says *the validation core* is not an extractor and adds an "Optional reference
  extractor" section; `docs/extractors/rule_based_lung_mdt.md`; `docs/research/lung_mdt_stage1_protocol.md`
  (phases A synthetic / B real 2024 registry cohort / C quality-indicator readiness; primary &
  secondary outcomes; explicit negative-result policy); `corpus/MANIFEST.md`; `docs/release.md`.
- pyproject description/keywords updated for release presentation. Validation core unchanged: still
  deterministic, offline, model-free, no runtime deps.
- **Synthetic-corpus row model** (`notevahti.corpus.synthetic`): a stdlib-only, offline typed model
  (`SyntheticRow`/`GroundTruth`/`Tnm`/`ExpectedField`/`QualityLabels`) and dependency-free
  `validate_row` for the generator's per-record JSONL shape, plus the published JSON Schema
  `corpus/schema/synthetic_case.schema.json` (with a validating example and a fine-tuning example).
  `validate_row` enforces the generator's QC invariants (evidence is an exact span of `note_text`;
  ambiguous TNM is not resolved; planned MDT ≠ completed; missing/indirect ECOG is not numericised;
  `record_id` = `{case_id}_{documentation_format}`). TNM `completeness` matches `parse_tnm`; a test
  keeps the schema and model vocabularies in sync. The agent prompt that produces this shape is saved
  at `docs/research/synthetic_corpus_generator_prompt.md`; sizing/split/distribution design in
  `docs/research/synthetic_corpus_design.md` (target 300 cases/language, 1800 total; case-level
  train/dev/test split to prevent leakage). Corpus tooling, not part of the validation core.
- **Stage-1 synthetic dataset committed** (`corpus/synthetic_mdt_v1/`, `dataset_version`
  `notevahti_lung_mdt_synthetic_v1`): 1800 cases / 5400 records across fi/sv/nb/da/is/en, three
  documentation formats per case, nine case categories, case-level train/dev/test split (no leakage).
  A minority of clear, complete, non-metastatic (M0) cases are now **pathological** (post-resection
  `p` / post-neoadjuvant `yp`) with a coherent localized staging-context phrase, instead of every
  case being baseline clinical `c`. Deterministic generator + validator brought in-repo;
  `validate_dataset.py` delegates row-level
  validation to `notevahti.corpus.validate_row` (single contract) and adds corpus-level checks
  (distributions, split, PII, the "current TNM" note convention). `validate_row` extended with the
  row-level semantic invariants (value==components, explicit-ECOG==ground-truth, has_negation,
  has_conflict, partial-TNM) and now accepts the generated vocabulary. Committed rows guarded by
  `tests/test_synthetic_corpus_dataset.py`. The generation tooling is ruff-excluded as imported
  tooling; the validation core is untouched.
- **Code-review follow-ups (no behaviour change):** single source of truth for the TNM token grammar
  (shared fragments compose both the extraction rules and `parse_tnm`); `_scan_tnm_runs`/`_resolve`
  helpers; `is_registry_ready` predicate shared by the single-record path and the aggregate;
  `_process_field` extracted in the CLI.

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
- **TNM / stage-group normaliser** (`notevahti.normalize`, audit priority #2): canonicalises stage
  *surface form* for agreement/eval — `normalize_tnm` ("cT2a N0 M0" / "cT2aN0M0" / "ct2a n0 m0" /
  "pT3N1M0" → canonical components + compact key), `normalize_stage_group` ("stage 3a" → "IIIA"), and
  `canonical_stage`. Deterministic, stdlib, offline; returns `None` rather than guessing. Explicit
  non-goals: no edition conversion (8th/9th sub-categories preserved), no staging inference. The
  deterministic validation core is unchanged.
- **Discrimination metrics** (`notevahti.analytics.discrimination`, §5.2 / TRIPOD+AI model
  performance): `flag_discrimination` (sensitivity, specificity, PPV/NPV at sample *and* a stated
  deployment prevalence, error enrichment) and `score_discrimination` (AUROC, AUPRC with its
  error-prevalence baseline), both with optional seeded bootstrap CIs. Applied in
  `scripts/eval_clinical_notes.py`: on the synthetic clinical-note dataset the flag reaches
  specificity 1.0, sensitivity 0.60, enrichment ~66× (95% CI ~48–101); the validity score scores
  AUROC 0.80 (CI 0.74–0.86) and AUPRC 0.62 vs a 0.037 baseline — gold never fed to the validator.
- **Stage-1 evidence pack + preregistration** (`notevahti.analytics.evidence_pack`,
  `notevahti.analytics.preregistration`, §5.6/§5.7 — the audit-#5 gate). `build_evidence_pack` →
  `to_markdown` assembles the machine-computable TRIPOD+AI sections from a reference run: a heuristic
  card (version, weights, threshold, routes, `config_hash`) pinning the frozen configuration, data
  summary, overall discrimination, and **mandatory subgroup** discrimination (e.g. by language and
  field); narrative sections are left to a human. `preregistration_markdown` emits an OSF-style
  analysis-plan skeleton (primary metrics, hypotheses with CI conditions, reference-standard
  independence, calibration/DCA plan, explicit kill criterion) to register **before** unblinding and
  **before** any weight tuning. `scripts/stage1_report.py` demonstrates the whole pipeline on the
  synthetic dataset — a synthetic-only methodology demo, explicitly not validation evidence. See
  `docs/design/stage1_protocol.md`.

### Fixed
- **Batch agreement is no longer pooled across fields** (audit priority #1): `validate_batch` now
  computes agreement **per `(field_name, field_type)` group**, each using its own field type. A new
  `BatchResult.agreements_by_field` holds the per-group results; the top-level `agreement` is reported
  only for a single group and is `not_available` (with a pointer) when fields are mixed — a pooled κ
  across staging/date/text was incorrect.

- **Messy MDT boundary cases** (`corpus/messy_mdt/cases.jsonl`, 5 deliberately hard notes:
  implicit staging, abbreviation, copy-forward, distractor, typo) plus a binding eval
  (`scripts/eval_messy_mdt.py`). Honest boundary result: search-based provenance binds **0/18**
  canonical staging values (cT/cN/cM/stage_group are inferred, never verbatim), misses abbreviated
  values ("neg"≠"negative", "adenoCa"≠"adenocarcinoma"), and can **spuriously** bind trivial
  single-token values (ECOG "1" → the "1" in "4.1 cm"). Lesson recorded in tests: NoteVahti validates
  spans an extractor supplies; it is not a re-locator, and inferred values correctly get no support.

### Added (review routing)
- **Trigger-gated validation routing** (`notevahti.routing.route_validation` → `ReviewRoute`): an
  optional, deterministic layer on top of `ValidationRecord` that integrates provenance, validity,
  independence, agreement and a declared `field_impact` into one auditable route — `accept`,
  `review`, `specialist_review`, or `blocked` — with active triggers, blocking flags and a
  human-readable rationale. The routes are **validation routes, not truth labels**: `accept` ≠
  correct, `blocked` ≠ wrong (`blocked` = the evidence cannot support auto-acceptance; advisory, not
  enforcement, not a clinical recommendation). The two blocking triggers (`no_source_span_found`,
  `independence_violated`) map to the existing non-negotiables. `validate_field` is unchanged; the
  routing rules are a transparent, configurable policy (frozen before Stage-1 calibration, like the
  validity weights), not calibrated thresholds. Named-regression + Hypothesis property tests; see
  `docs/design/validation_routing.md`.
- **The review route is recorded in the audit trail**: `ReviewRoute.to_dict()` plus a `routing=`
  argument to `audit_payload` embed the route, triggers, blocking flags and rationale in the
  tamper-evident, hash-chained entry (routing carries no PHI). `audit` stays decoupled from `routing`
  (it accepts a plain mapping). A tampered route now breaks the chain like any other edit.
### Added (opt-in provenance)
- **Word-boundary matching and a clinical synonym table** for `verify_span`, both **opt-in and
  default-off** so the deterministic default is unchanged. `word_boundary=True` rejects matches
  embedded inside a larger token (numbers are decimal-aware: "1" matches "ECOG 1." but not the "1"
  in "4.1"); `synonyms=` (e.g. `notevahti.synonyms.default_synonyms()`, a small documented
  abbreviation table) lets known surface variants count as support. On the messy MDT cases the two
  options together raise binding 30→43/67 — synonyms recover abbreviated biomarkers/histology
  (e.g. EGFR 1/4→4/4) and word-boundary *removes* spurious single-token binds (sex 5/5→1/5, the four
  dropped were false matches inside words). Inferred staging stays 0/18 (no surface to bind — that
  remains the extractor's job, with a span).

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
- **Grant-ready polish:** README expanded (significance, honest novelty boundary, evidence-so-far,
  validation pathway, Nordic/multilingual scope, data-protection & reproducibility, how-to-cite,
  funding note; stale test count fixed). New `docs/research-framing.md` — a concise scientific framing
  for funders/reviewers (background, gap/hypothesis, approach, evaluation design, impact, stage
  gates, what funding supports).
- **Preregistration reframed to Nordic-multilingual** (not single-registry): cohort and mandatory
  language subgroups cover fi/sv/nb/da/is/en; data-governance generalised from Findata to the
  applicable national secondary-use authority (SE/NO/DK/IS as well as FI).

### Repository / community (audit #6)
- `SECURITY.md` — private vulnerability reporting, the local-first/no-telemetry posture, the
  tamper-evident-not-tamper-proof audit note, and a prominent **no-PHI** rule for reports.
- `CITATION.cff` (FAIR4RS) — software citation metadata (author + ORCID, version, license, repo).
- GitHub issue templates (bug / feature / validation question) + `config.yml` routing vulnerabilities
  to private reporting, each carrying the no-PHI warning and the project's boundaries.
- README **validation-status badge** ("Stage 0: not clinically validated") plus status/license/Python
  badges and a status note.

### Boundary
- Not a medical device; not clinical advice. Produces validation evidence for human review, not a
  guarantee of correctness. No distribution-free / conformal coverage guarantee is claimed (the
  evidence refuted them for this setting).
