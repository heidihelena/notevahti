# Rule-based extractor (`notevahti.extractors.rules`)

A deterministic, offline, **stdlib-only** rule-based extractor for lung-cancer MDT notes. It is the
non-hallucinating "rule" persona for Stage-0.5 validation and a transparent, Findata-deployable
baseline extractor for Stage 1. **Extraction only** — it makes no diagnostic or therapeutic claim and
no correctness guarantee; whether to trust a value is NoteVahti's job.

## Interface

It satisfies the existing `Extractor` protocol (`base.py`), so it is a drop-in for `validate_field`:

```python
from notevahti.extractors import RuleBasedExtractor, rules_lineage
from notevahti.types import FieldSpec, FieldType
from notevahti.validate import validate_field

ex = RuleBasedExtractor()
note = "MDT: RUL adenocarcinoma, clinical stage cT2a N0 M0. ECOG 1. Plan: SABR."
res = ex.extract(note, FieldSpec(name="clinical_stage", field_type=FieldType.STAGING))
# res.value == "cT2a N0 M0"  (surface text exactly at res.source_span)
record = validate_field(
    res.value, note, field_type=FieldType.STAGING, field_name="clinical_stage",
    claimed_span=res.source_span, value_lineage=rules_lineage(source_id="note_1"),
)
```

- `extract(note, field) -> ExtractionResult` — one proposed value as the **surface text at the
  span** (provenance-verifiable), or no value. Single-valued field with conflicting candidates →
  **no value** (no-guess).
- `candidates(note, field_name) -> list[RuleCandidate]` — every match, with `value` (canonical,
  registry-facing), `matched_text` (= `note[span]`), `span`, `field_type`, `negated`. Span-subsumed
  matches are dropped (the maximal match wins). This is where multi-valued fields (biomarker,
  treatment_plan) and ambiguity are exposed.
- `extract_all(note)`, `fields()`, and `rules_lineage(source_id=None) -> Lineage(model_id="rules_v1")`.

## Field catalogue (versioned: `MODEL_ID = "rules_v1"`)

| Field | `FieldType` | Captured |
|---|---|---|
| `clinical_stage` | staging | cTNM (combined or lone components, c/none prefix), UICC 8th |
| `pathological_stage` | staging | pTNM / ypTNM (p/yp prefix) |
| `stage_group` | staging | IA1–IVB (requires a stage keyword nearby) |
| `histology` | categorical | adeno, squamous, small cell, NSCLC-NOS, large cell, carcinoid |
| `location` | categorical | RUL/RML/RLL/LUL/LLL |
| `laterality` | categorical | right / left |
| `biomarker` | categorical | EGFR (ex19del/L858R/±), ALK, ROS1, BRAF V600E, KRAS G12C, MET ex14, RET, PD-L1 TPS % |
| `performance_status` | categorical | ECOG/WHO 0–4, Karnofsky % |
| `treatment_intent` | categorical | curative / palliative |
| `treatment_plan` | categorical | SABR, lobectomy, segmentectomy, chemoradiotherapy, chemotherapy, immunotherapy, targeted therapy, best supportive care |

Surface forms are matched in **Finnish, Swedish and English** with common abbreviations and some
inflection (`\w*` stems); canonical values are English/universal. The catalogue is the data-driven
`_RULES` table — bump `MODEL_ID` when patterns change so a frozen Stage-1 study can pin the version.

## Behaviour guarantees

- **Deterministic & offline:** same input → identical output; `re` only; no network, clock, or RNG.
- **No-guess:** absent field → explicit no-value; never a default or filler.
- **Negation-aware:** a negation cue (fi/sv/en) in the ~30-char window before a match suppresses a
  positive finding; biomarker positives flip to the explicit negative value. So "EGFR negatiivinen"
  → `EGFR negative` (not positive), "no adenocarcinoma" → nothing, "PD-L1 < 1 %" → no high-TPS
  positive.
- **Provenance-friendly:** offsets index the value exactly; multiple non-equivalent candidates are
  returned (and flagged as ambiguity for single-valued fields) rather than silently picked.
- **Independent:** imports only `re` and `..types`; reuses none of NoteVahti's validation/anchor
  logic; lineage `model_id="rules_v1"`.

## Known limitations

- Finnish/Swedish morphology is only partially covered (stem + `\w*`); rare inflections may be
  missed (prefers a miss over a wrong value).
- Implicit staging (size/nodal prose without an explicit TNM token) is **not** inferred — that is an
  extractor inference, not string matching; such a value would have no source span and NoteVahti
  would correctly route it to review.
- The catalogue is a baseline, not exhaustive; extend `_RULES` and bump `MODEL_ID`.
