# Corpus manifest

**Synthetic only — no real patients.** Every note, identifier, date, molecular result and scenario is
generated. **Leakage prevention:** during validation runs the gold values are **never** fed to the
validator; NoteVahti sees only the note text and the (extractor-proposed) value.

Corpus version: tracks the repository (`notevahti 0.1.0.dev0`).
Generated: regenerate deterministically from the seeded generator (see below); the committed copy was
produced on the repository's build date.

## Datasets

### 1. `corpus/` generator output (multilingual MDT) — 4000 cases
- Generator: `scripts/gen_corpus.py` (deterministic, seeded via `zlib.adler32("notevahti::{group}::{i}")`).
- Languages: free text in **fi, sv, nb, da, is, en**; structured groups in **en**.
- Documentation formats: free text (`mdt.html`), semistructured (`mdt-structured-mini.html`), full
  structured v3.1 (`mdt-structured-v3_1.html`).
- Size: 500 cases/group × 8 groups = **4000**.
- Messiness: clean (verbatim gold) plus a `challenges` block per case (surface-variant;
  present-but-wrong pre-MDT cTNM). Optional opt-in error injection (`--errors RATE`).
- Fields with ground truth (exact spans): histology, clinical_stage (cTNM), treatment intent,
  treatment, PD-L1 TPS, driver alteration.
- Rebuild: `PYTHONPATH=src python3 scripts/gen_corpus.py --n 500 --out corpus`.

### 2. `corpus/synthetic_clinical_notes/` — 150 notes
- External synthetic dataset; languages **en, fi, sv**; seeded failure modes (unsupported_value,
  negation_trap, temporal_trap, copy_forward_old_stage, synonym_miss, unit_format, source_conflict,
  independence_fail). Files: notes.csv, gold_labels.csv, extractions.csv, test_cases.csv, notes.jsonl,
  sqlite. Used for Stage-1 enrichment evaluation (`scripts/eval_clinical_notes.py`).

### 3. `corpus/messy_mdt/cases.jsonl` — 5 boundary cases
- Deliberately hard English MDT notes (implicit staging, abbreviation, copy-forward, distractor,
  typo) with structured ground truth, for the provenance-binding boundary eval (`scripts/eval_messy_mdt.py`).

## Case schema (planned Stage-1 corpus)

The target sizing, case-level split, case-type distribution and on-disk shape for the planned
1800-case Nordic corpus are specified in
[`docs/research/synthetic_corpus_design.md`](../docs/research/synthetic_corpus_design.md). The
machine-checkable contract for one case is
[`corpus/schema/synthetic_case.schema.json`](schema/synthetic_case.schema.json) (validating example:
[`schema/example_case.fi.json`](schema/example_case.fi.json); fine-tuning example:
[`schema/finetuning_record.example.jsonl`](schema/finetuning_record.example.jsonl)). The typed model
and a dependency-free validator are in `notevahti.corpus.synthetic`; a test keeps the schema and the
model vocabularies in sync.

## Messiness levels (overall)

- **clean** — gold values appear verbatim (generator default).
- **surface-variant / abbreviated** — correct value in a non-verbatim surface form.
- **present-but-wrong / seeded-error** — a wrong value that may appear in the note (challenges block;
  error-injection; external dataset failure modes).
- **messy** — implicit/abbreviated/distractor-laden free text (messy_mdt).

## Boundary

Synthetic data is a methodology and CI instrument, **not validation evidence**. Real-world predictive
value requires an independent reference cohort (see `docs/research/lung_mdt_stage1_protocol.md`).
