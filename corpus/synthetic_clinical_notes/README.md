# NoteVahti synthetic clinical note database

Synthetic dataset for validator testing. Contains no real patient data. All identifiers, dates, notes, molecular results, and clinical scenarios are generated.

## Files

- `notes.csv`: one synthetic note per row.
- `gold_labels.csv`: gold-standard field values.
- `extractions.csv`: simulated extractor output and expected NoteVahti-style validity/flag fields.
- `test_cases.csv`: seeded failure mode per note.
- `notes.jsonl`: notes in JSONL format.
- `notevahti_synthetic.sqlite`: same data as SQLite tables.

## Intended use

Use this as a Stage-0/Stage-1 harness for provenance, agreement, independence, and review-flag enrichment tests. Do not use it as clinical truth. It is deliberately stylized and should be expanded with institution-specific fixtures before real validation.

## Seeded failure modes

- unsupported_value
- negation_trap
- temporal_trap
- copy_forward_old_stage
- synonym_miss
- multilingual_variant
- unit_format
- source_conflict
- independence_fail

## Minimal expected test

The `expected_flag=review` rows should be enriched for `is_correct_against_gold=False` compared with accepted rows. That is the kill/scale test for the flag.
