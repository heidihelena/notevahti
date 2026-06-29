# Field Definitions

## Top-Level Fields

- `dataset_version`: Fixed dataset identifier, `notevahti_lung_mdt_synthetic_v1`.
- `case_id`: Synthetic case identifier, formatted as `<language>_<0001-0300>`.
- `case_category`: Generator stratum used to validate the requested case distribution.
- `record_id`: Unique text-record identifier, formatted as `<case_id>_<documentation_format>`.
- `language`: One of `fi`, `sv`, `nb`, `da`, `is`, `en`.
- `source_type`: Always `synthetic`.
- `documentation_format`: One of `free_text`, `structured_mini`, `structured_v3_1`.
- `messiness`: Broad note complexity label: `clean`, `semistructured`, or `messy`.
- `split_hint`: Case-level split assignment: `train`, `dev`, or `test`.
- `ground_truth`: Case-level labels created before note rendering.
- `note_text`: Synthetic MDT note text in the row language and documentation format.
- `expected_output`: Expected extractor output for the three primary fields.
- `quality_labels`: Review-routing and registry-readiness flags.

## Ground Truth

- `mdt_discussed`: Whether a completed MDT discussion is documented.
- `mdt_status`: `completed`, `planned`, or `not_completed`.
- `ecog_ps`: Explicit numeric ECOG/WHO performance status, or `null`.
- `ecog_status`: `explicit`, `missing`, or `indirect`.
- `tnm`: Structured TNM object with `prefix`, `t`, `n`, `m`, `full`, `complete`, `ambiguous`, and `edition`.
- `stage_group`: Stage group when documented or safely represented; otherwise `unclear`.
- `histology`: Canonical histology class.
- `biomarkers`: Canonical biomarker status dictionary.
- `treatment_intent`: Canonical treatment-intent label.
- `mdt_recommendation`: Canonical recommendation label.
- `imaging_summary`: Compact synthetic imaging summary.
- `pathology_summary`: Compact synthetic pathology summary.
- `diagnostic_uncertainty`: Human-readable uncertainty reason, or `none`.
- `review_required`: Case-level review flag.

## Expected Output

`expected_output.mdt_discussed` contains:

- `value`: `true`, `false`, or `null`.
- `evidence`: Exact supporting span from `note_text`, or `null`.
- `requires_review`: Field-level review flag.

`expected_output.ecog_ps` contains:

- `value`: integer 0-4 when explicitly documented, otherwise `null`.
- `evidence`: Exact supporting span from `note_text`, or an exact missing/ambiguous span.
- `requires_review`: Field-level review flag.

`expected_output.tnm` contains:

- `value`: Complete TNM string when safely extractable, otherwise `null`.
- `components`: Separate `prefix`, `t`, `n`, and `m` values. Partial TNM preserves available components.
- `evidence`: Exact supporting or ambiguity span from `note_text`.
- `requires_review`: Field-level review flag.

## Quality Labels

- `has_negation`: The note explicitly negates completed MDT discussion.
- `has_conflict`: Conflicting staging information requires review.
- `has_missing_ecog`: Numeric ECOG/WHO PS is not documented.
- `has_partial_tnm`: One or more TNM components are missing.
- `has_old_staging`: Old and current staging information both appear.
- `has_future_mdt`: MDT is planned but not completed.
- `has_indirect_ecog`: Functional status is described without explicit numeric ECOG.
- `requires_review`: Any case-level review issue is present.
- `registry_ready`: The record is suitable for automatic registry-style extraction without review.
