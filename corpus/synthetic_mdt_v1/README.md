# NoteVahti Synthetic Nordic Lung-Cancer MDT Dataset v1

This package generates a fully synthetic Nordic lung-cancer multidisciplinary team (MDT) dataset for extractor and validation-layer methods research.

The dataset contains no real patients, no copied clinical notes, no real identifiers, no hospital-specific cases, and no rare real-world case combinations copied from memory. It is not for clinical use.

> Integrated into NoteVahti. The canonical row contract is `../schema/synthetic_case.schema.json`
> and `notevahti.corpus.synthetic` (typed model + `validate_row`); `validate_dataset.py` delegates
> row-level checks to it and adds corpus-level checks (distributions, case-level split, PII, note
> conventions). Committed rows are guarded by `tests/test_synthetic_corpus_dataset.py`.

## Contents

- `manifest.json`: dataset-level metadata.
- `data/synthetic_mdt_<language>.jsonl`: generated language-specific JSONL files.
- `scripts/generate_dataset.py`: deterministic generator (writes `data/`, then self-validates).
- `scripts/validate_dataset.py`: validation (row contract via `notevahti.corpus.validate_row`
  + corpus-level distributions, split, PII and note conventions).
- `docs/field_definitions.md`: field-level definitions.
- `docs/annotation_rules.md`: extraction and review-label rules.
- Row JSON Schema: `../schema/synthetic_case.schema.json` (repo-canonical).

## Generation

Run from the package root:

```bash
python3 scripts/generate_dataset.py
```

The generator uses fixed deterministic seeds, writes all six JSONL files, and then runs `scripts/validate_dataset.py`. Generation fails if validation fails.

To validate existing files:

```bash
python3 scripts/validate_dataset.py .
```

## Scope

- Languages: Finnish (`fi`), Swedish (`sv`), Norwegian Bokmal (`nb`), Danish (`da`), Icelandic (`is`), English (`en`).
- Cases per language: 300.
- Total unique cases: 1800.
- Documentation formats per case: `free_text`, `structured_mini`, `structured_v3_1`.
- Records per language: 900.
- Total records: 5400.

Each `case_id` appears exactly three times, once per documentation format. The three records for a case share the same `split_hint`.

## Row Schema

Each JSONL row contains:

- `dataset_version`
- `case_id`
- `case_category`
- `record_id`
- `language`
- `source_type`
- `documentation_format`
- `messiness`
- `split_hint`
- `ground_truth`
- `note_text`
- `expected_output`
- `quality_labels`

The primary extraction targets are:

- `mdt_discussed`
- `ecog_ps`
- `tnm`

Secondary fields add clinical realism: histology, stage group, biomarkers, treatment intent, MDT recommendation, imaging summary, pathology summary, diagnostic uncertainty, and review status.

## Case Distribution Per Language

The generator creates exactly:

- 90 clear explicit MDT + ECOG + complete TNM cases.
- 30 missing ECOG cases.
- 30 partial TNM cases.
- 30 conflicting TNM cases.
- 30 old-versus-current staging cases.
- 15 planned future MDT cases.
- 15 explicitly not-yet-discussed MDT cases.
- 30 indirect functional-status cases without numeric ECOG.
- 30 biomarker and treatment-plan complexity cases.

The histology, treatment-intent, and explicit-ECOG distributions are also deterministic and validated.

## Leakage Prevention

Splits are assigned by `case_id`, not by `record_id`. All three documentation formats for a case have the same `split_hint`, preventing the same clinical case from appearing across train/dev/test through a different note format.

## Validation

The validator checks:

- All JSONL rows parse as JSON.
- Each language file has 900 rows.
- Each language has 300 unique `case_id` values.
- Each case has exactly three documentation formats.
- All three rows for a case share the same split.
- Every non-null expected value has exact evidence present in `note_text`.
- Synthetic identifier hygiene.
- Planned MDT is not labelled as completed.
- Indirect functional descriptions are not converted to numeric ECOG.
- Conflicting TNM is not silently resolved unless a current TNM is explicitly marked.
- Case-category, histology, treatment-intent, explicit-ECOG, and split counts match the manifest.

## Recommended Metrics

- Exact match.
- Sensitivity.
- Specificity.
- Positive predictive value (PPV).
- Negative predictive value (NPV).
- F1.
- Coverage.
- Parse failure rate.
- Falsely auto-accepted rate.
- Review flag sensitivity.
- Registry-ready yield.

## Limitations

This is synthetic benchmark data. It is designed to test extraction and validation behavior, not to estimate real-world clinical prevalence, workflow quality, clinical outcomes, or treatment appropriateness. Nordic language phrasing is intentionally plausible and varied but cannot cover all local abbreviations, dialects, hospital templates, or specialty-specific documentation habits.

## Not For Clinical Use

This dataset must not be used for patient care, clinical decision-making, diagnosis, treatment selection, or registry submission. It is intended only for research, software testing, validation-layer simulation, and extractor benchmarking.
