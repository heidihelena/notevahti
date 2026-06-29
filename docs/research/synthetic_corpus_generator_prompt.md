# Agent prompt — synthetic Nordic lung-cancer MDT dataset generator

**Purpose of this file.** A saved, self-contained task prompt for an agent that will *write a
deterministic Python generator* for the synthetic Stage-1 corpus and then validate its own output.
It is a specification, not runnable code.

> **Schema status: aligned.** This prompt's per-row schema is now the canonical model. The committed
> contract — [`corpus/schema/synthetic_case.schema.json`](../../corpus/schema/synthetic_case.schema.json)
> and [`notevahti.corpus.synthetic`](../../src/notevahti/corpus/synthetic.py) (`SyntheticRow`,
> `validate_row`) — matches it: `ground_truth`, `note_text`, `record_id`, `split_hint`, `mdt_status`,
> `ecog_status`, the `ntrk` biomarker, the secondary fields, `tnm.complete`/`tnm.ambiguous`/`tnm.full`,
> and `quality_labels` are all modelled. `validate_row` additionally enforces the QC invariants below
> (evidence is an exact span of `note_text`; ambiguous TNM is not resolved; a planned MDT is not
> completed; missing/indirect ECOG is not numericised; `record_id` = `{case_id}_{documentation_format}`).
> The generator should call `validate_row` on every row and fail on any error. Norwegian Bokmål is
> `nb` repo-wide.

---

## Prompt

Create a Python generator script instead of manually writing all rows. Use deterministic seeds.
Generate the JSONL files, then run validation checks and fail if any invariant is broken. You are
generating a fully synthetic Nordic lung-cancer MDT dataset for a methods study.

This dataset contains no real patients, no copied clinical notes, no identifiable persons, no
hospital-specific real cases and no real-world rare case combinations copied from memory. Every case
must be fictional but clinically plausible.

### Goal

Generate 300 synthetic lung-cancer MDT cases per language for:

- Finnish: `fi`
- Swedish: `sv`
- Norwegian Bokmål: `nb`
- Danish: `da`
- Icelandic: `is`
- English: `en`

Total:

- 1800 unique clinical cases
- Each case must be rendered in 3 documentation formats:
  1. `free_text`
  2. `structured_mini`
  3. `structured_v3_1`
- Total text records: 5400

Primary extraction fields:

1. `mdt_discussed`
2. `ecog_ps`
3. `tnm`

Secondary fields for realism:

- `histology`
- `stage_group`
- `biomarkers`
- `treatment_intent`
- `mdt_recommendation`
- `imaging_summary`
- `pathology_summary`
- `diagnostic_uncertainty`
- `review_required`

The dataset is for evaluating:

- a rule-based NoteVahti extractor
- a small LLM extractor
- a fine-tuned LLM extractor
- NoteVahti validation and review routing

### Critical rule

The ground truth must be created first. The note text must then faithfully express the ground truth,
except where the case is intentionally designed to contain missing, partial, ambiguous,
future-planned or conflicting documentation. In those cases, the ambiguity must be encoded
explicitly in the labels.

### Output format

Write JSONL. One JSON object per text record. Because each clinical case has 3 documentation
formats, each `case_id` will appear exactly 3 times with different `documentation_format` values.

Do not include markdown. Do not include explanations. Output only valid JSONL.

Schema for every JSONL row:

```json
{
  "dataset_version": "notevahti_lung_mdt_synthetic_v1",
  "case_id": "fi_0001",
  "record_id": "fi_0001_free_text",
  "language": "fi",
  "source_type": "synthetic",
  "documentation_format": "free_text",
  "messiness": "clean",
  "split_hint": "train",
  "ground_truth": {
    "mdt_discussed": true,
    "mdt_status": "completed",
    "ecog_ps": 1,
    "ecog_status": "explicit",
    "tnm": {
      "prefix": "c",
      "t": "T2a",
      "n": "N1",
      "m": "M0",
      "full": "cT2aN1M0",
      "complete": true,
      "ambiguous": false,
      "edition": "unknown"
    },
    "stage_group": "IIB",
    "histology": "adenocarcinoma",
    "biomarkers": {
      "egfr": "negative",
      "alk": "negative",
      "ros1": "negative",
      "braf": "not_reported",
      "met": "not_reported",
      "ret": "not_reported",
      "ntrk": "not_reported",
      "kras": "not_reported",
      "pdl1": "TPS 60%"
    },
    "treatment_intent": "curative",
    "mdt_recommendation": "thoracic surgery evaluation"
  },
  "note_text": "The actual MDT note text in the specified language and documentation format.",
  "expected_output": {
    "mdt_discussed": {
      "value": true,
      "evidence": "exact supporting phrase from note_text",
      "requires_review": false
    },
    "ecog_ps": {
      "value": 1,
      "evidence": "exact supporting phrase from note_text",
      "requires_review": false
    },
    "tnm": {
      "value": "cT2aN1M0",
      "components": { "prefix": "c", "t": "T2a", "n": "N1", "m": "M0" },
      "evidence": "exact supporting phrase from note_text",
      "requires_review": false
    }
  },
  "quality_labels": {
    "has_negation": false,
    "has_conflict": false,
    "has_missing_ecog": false,
    "has_partial_tnm": false,
    "has_old_staging": false,
    "has_future_mdt": false,
    "has_indirect_ecog": false,
    "requires_review": false,
    "registry_ready": true
  }
}
```

### Allowed values

`language`: `fi`, `sv`, `nb`, `da`, `is`, `en`

`documentation_format`: `free_text`, `structured_mini`, `structured_v3_1`

`messiness`: `clean`, `semistructured`, `messy`

`split_hint` — assign by `case_id`, not by `record_id`:

- `train`: 70%
- `dev`: 15%
- `test`: 15%

**Important leakage rule:** all three `documentation_format` records for the same `case_id` must
have the same `split_hint`. Never place `free_text` in train and `structured_mini` or
`structured_v3_1` in dev/test for the same case.

### Case distribution per language, n = 300

1. **Clear explicit MDT + ECOG + complete TNM** — 30%, 90 cases/language. `mdt_discussed` true;
   `ecog_ps` explicit; complete TNM.
2. **Missing ECOG** — 10%, 30 cases/language. ECOG not documented; `expected_output.ecog_ps.value`
   must be null; `requires_review` true or `registry_ready` false for ECOG.
3. **Partial TNM** — 10%, 30 cases/language. One or more TNM components missing; TNM `complete`
   false; do not infer missing components.
4. **Conflicting TNM** — 10%, 30 cases/language. Two different TNM values appear in the note; mark
   `tnm.ambiguous` true; `expected_output.tnm.value` must be null; `requires_review` true.
5. **Old versus current staging** — 10%, 30 cases/language. Old and current staging both appear;
   current staging may be identifiable only if explicitly stated; otherwise mark ambiguous and
   `requires_review` true.
6. **MDT planned but not completed** — 5%, 15 cases/language. Phrases such as "will be discussed",
   "planned for MDT", "to be presented"; `mdt_discussed` false or unknown depending on wording; do
   not mark completed MDT.
7. **MDT explicitly not yet discussed** — 5%, 15 cases/language. `mdt_status` not_completed;
   `expected_output.mdt_discussed.value` false; evidence must support negation.
8. **Indirect functional status without explicit ECOG** — 10%, 30 cases/language. Examples:
   independent in ADL, bedbound, walks short distances, needs help with self-care; do not convert
   automatically to ECOG unless ECOG/WHO PS number is explicitly present;
   `expected_output.ecog_ps.value` null; `has_indirect_ecog` true; `requires_review` true.
9. **Biomarker and treatment-plan complexity** — 10%, 30 cases/language. Distracting but plausible
   details about EGFR, ALK, ROS1, KRAS, BRAF, MET, RET, NTRK, PD-L1; primary extraction fields must
   still be clear or intentionally ambiguous according to labels.

### Clinical realism constraints

Histology distribution per language (roughly): adenocarcinoma 45%, squamous cell carcinoma 25%,
NSCLC NOS 10%, small-cell lung cancer 10%, other or uncertain 10%.

Stage distribution (roughly): I 15%, II 15%, III 25%, IV 35%, unclear or incomplete 10%.

Treatment-intent distribution: curative 35%, palliative 45%, diagnostic/additional workup 15%, best
supportive care or uncertain 5%.

ECOG distribution among explicit ECOG cases: ECOG 0 15%, ECOG 1 35%, ECOG 2 25%, ECOG 3 20%,
ECOG 4 5%.

### TNM rules

- Use lung-cancer-plausible TNM values.
- Prefer clinical TNM prefix `c` for MDT baseline cases.
- Use `p` or `yp` only when the note clearly describes post-surgical or post-neoadjuvant pathology.
- Do not infer stage group from incomplete TNM unless ground truth explicitly permits it.
- If multiple distinct TNM values occur and current status is not explicit,
  `expected_output.tnm.value` must be null and `requires_review` true.
- Always keep T, N and M components separate in `expected_output`.
- If full TNM is absent but partial components are present, preserve partial components but set
  `complete` false.

### MDT rules

- Completed MDT counts as true.
- Planned future MDT does not count as completed.
- "Not yet discussed at MDT" counts as false.
- Ambiguous mentions require review.
- Do not infer MDT discussion from treatment recommendation alone.

### ECOG rules

- Explicit ECOG/WHO PS numeric value can be extracted.
- Indirect functional description alone must not be converted into a numeric ECOG value.
- If old and current ECOG both appear, accept current only if clearly marked as current.
- Otherwise `expected_output.ecog_ps.value` must be null and `requires_review` true.

### Evidence rules

- Every non-null `expected_output` value must include an exact evidence string copied from
  `note_text`.
- Evidence must be a short span, not a paragraph.
- If value is null because missing or ambiguous, evidence can be null or the ambiguity span.
- Do not invent evidence that is not in the `note_text`.

### Documentation format definitions

1. **free_text** — a realistic MDT paragraph or short prose note. May include abbreviations,
   incomplete sentences, clinical shorthand and mixed ordering. Must not be a labelled form.
2. **structured_mini** — a compact structured MDT summary with headings. Use a small number of
   fields: MDT status; Imaging; Pathology; Stage/TNM; ECOG/WHO PS; Recommendation. Should resemble a
   lightweight clinical structured summary.
3. **structured_v3_1** — a more detailed structured MDT form with explicit sections: Patient context
   (fictional and non-identifiable); Diagnostic status; Imaging; Pathology; Molecular markers; TNM;
   ECOG/WHO PS; Treatment intent; MDT recommendation; Review flags or missing data. Do not include
   real identifiers.

### Language requirements

**Finnish.** Finnish clinical language and common abbreviations/phrases: MDT, moniammatillinen
kokous, keuhkotiimi; ECOG, WHO PS, toimintakyky; levinneisyys, cTNM, TNM; adenokarsinooma,
levyepiteelikarsinooma; suositellaan, lisäselvittely, leikkausarvio, sädehoito, systeeminen hoito.

**Swedish.** Clinical Swedish appropriate for Finland/Sweden: MDT, multidisciplinär konferens,
lungteam; ECOG, WHO PS, funktionsstatus; stadieindelning, TNM; adenokarcinom, skivepitelcancer;
rekommenderas, kirurgbedömning, strålbehandling, systemisk behandling.

**Norwegian Bokmål.** MDT, tverrfaglig møte, lungekreftmøte; ECOG, WHO PS, funksjonsstatus;
stadieinndeling, TNM; adenokarsinom, plateepitelkarsinom; anbefales, kirurgisk vurdering,
strålebehandling, systemisk behandling.

**Danish.** MDT, multidisciplinær konference, lungekonference; ECOG, WHO PS, funktionsniveau;
stadieinddeling, TNM; adenokarcinom, planocellulært karcinom; anbefales, kirurgisk vurdering,
strålebehandling, systemisk behandling.

**Icelandic.** Use Icelandic clinical language where possible, but standard international
abbreviations such as MDT, ECOG, WHO PS, TNM and PD-L1 are allowed. If unsure, use clear Icelandic
clinical phrasing and preserve internationally recognized oncology terms.

**English.** Concise clinical English: MDT, tumour board, multidisciplinary team; ECOG, WHO PS,
performance status; staging, TNM; adenocarcinoma, squamous cell carcinoma; recommended, surgical
evaluation, radiotherapy, systemic therapy.

Do not over-polish the notes. Real MDT notes are often compressed, but they must remain
understandable.

### Output batching

Generate the dataset in language-specific files:

- `synthetic_mdt_fi.jsonl`
- `synthetic_mdt_sv.jsonl`
- `synthetic_mdt_nb.jsonl`
- `synthetic_mdt_da.jsonl`
- `synthetic_mdt_is.jsonl`
- `synthetic_mdt_en.jsonl`

Each file must contain 300 unique `case_id`s and 900 JSONL rows (each case has 3 documentation
formats).

Also generate `manifest.json` and `README.md`.

`manifest.json` must include:

```json
{
  "dataset_version": "notevahti_lung_mdt_synthetic_v1",
  "synthetic_only": true,
  "no_real_patients": true,
  "languages": ["fi", "sv", "nb", "da", "is", "en"],
  "cases_per_language": 300,
  "documentation_formats": ["free_text", "structured_mini", "structured_v3_1"],
  "records_per_language": 900,
  "total_cases": 1800,
  "total_records": 5400,
  "primary_fields": ["mdt_discussed", "ecog_ps", "tnm"],
  "split_policy": "case_level",
  "leakage_prevention": "All documentation formats for a case_id share the same split_hint.",
  "intended_use": "Research, extractor benchmarking, validation-layer testing and registry-readiness simulation.",
  "not_for_clinical_use": true
}
```

`README.md` must include: dataset purpose; synthetic-only statement; schema; field definitions; case
distribution; leakage prevention; limitations; not for clinical use; and recommended evaluation
metrics: exact match, sensitivity, specificity, PPV, NPV, F1, coverage, parse failure, falsely
auto-accepted rate, review flag sensitivity, registry-ready yield.

### Quality control before final output

1. Validate every JSONL row as valid JSON.
2. Check each language file has exactly 900 rows.
3. Check each language has exactly 300 unique `case_id`s.
4. Check each `case_id` has exactly 3 rows.
5. Check all 3 rows for a `case_id` share the same `split_hint`.
6. Check every non-null `expected_output` value has evidence present in `note_text`.
7. Check no real names, addresses, exact dates of birth, personal IDs, hospital numbers or real
   patient identifiers appear.
8. Check that planned MDT is not labelled as completed MDT.
9. Check indirect ECOG descriptions are not converted to numeric ECOG without explicit ECOG/WHO PS.
10. Check conflicting TNM is not silently resolved unless current TNM is explicitly stated.
