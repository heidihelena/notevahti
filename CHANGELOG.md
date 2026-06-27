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
- Test asserting the validation core makes no network calls. 56 tests, deterministic, offline.

### Project docs
- Design note, research → validated-tool pathway, deep-research evidence base, and SKILL.md build
  playbook under `docs/` and `SKILL.md`.

### Boundary
- Not a medical device; not clinical advice. Produces validation evidence for human review, not a
  guarantee of correctness. No distribution-free / conformal coverage guarantee is claimed (the
  evidence refuted them for this setting).
