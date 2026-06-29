# Rule-based lung-cancer MDT extractor

`notevahti.extractors.rules.RuleBasedExtractor` — an **optional reference extractor** for
benchmarking and end-to-end validation. It is **not a clinical NLP model and not a truth source**;
it proposes candidate values bound to source spans, and the validation core decides whether to trust
them.

## Purpose

- Provide the deterministic, non-hallucinating "rule" persona for Stage-0.5/Stage-1 evaluation.
- Serve as a transparent, Findata-deployable baseline extractor (no model, no network, no deps).
- Produce span-bound candidates so NoteVahti's provenance can verify them byte-for-byte.

## Fields covered

`mdt_discussed`, `clinical_stage`, `pathological_stage`, `stage_group`, `histology`, `location`,
`laterality`, `biomarker`, `performance_status`, `treatment_intent`, `treatment_plan`.

## Supported languages (currently)

Finnish, Swedish, English — surface forms and common abbreviations; canonical values are
English/universal. Finnish/Swedish morphology is only partially covered (stem + `\w*`); rare
inflections may be missed (a miss is preferred to a wrong value).

## No-guess policy

If a field is absent, the extractor returns the explicit no-value result — never a default or filler.
For single-valued fields, if the note yields more than one *distinct* value, `extract` returns no
value (the conflict is visible via `candidates`). Genuinely multi-valued fields (`biomarker`,
`treatment_plan`) return every finding via `candidates`.

## Negation handling

A negation cue (fi/sv/en) in the short window before a match suppresses a positive finding; biomarker
positives flip to the explicit negative value. Examples: "EGFR negatiivinen" → `EGFR negative` (not
positive); "no adenocarcinoma" → nothing; "PD-L1 < 1 %" → no high-TPS positive. `mdt_discussed`
additionally suppresses **future/planned** intent ("will be discussed", "MDT planned", "scheduled",
"suunniteltu", "not yet").

## Ambiguity handling

Conflicting candidates are returned (and, for single-valued fields, surfaced as ambiguity → no
auto-value) rather than silently resolved. For TNM, `parse_tnm` returns
`completeness="ambiguous"` when components or editions conflict.

## Span fidelity requirement

Each candidate's `span` indexes its `matched_text` exactly (`note[span] == matched_text`). The
Protocol `extract` returns the value as that surface text, so provenance verifies it byte-for-byte.
The registry-facing canonical value is `RuleCandidate.value`.

## Versioning

The catalogue is the data-driven `_RULES` table, versioned by `MODEL_ID` (currently `rules_v1`). Bump
`MODEL_ID` whenever patterns change so a frozen Stage-1 study can pin the extractor version (it is
recorded in the evidence-pack heuristic card).

## Usage

```python
from notevahti.extractors import RuleBasedExtractor, rules_lineage, parse_tnm
from notevahti.types import FieldSpec, FieldType
from notevahti.validate import validate_field

ex = RuleBasedExtractor()
note = "RUL adenocarcinoma, clinical stage cT2a N0 M0. ECOG 1. Discussed at MDT. Plan: SABR."

# all candidates for a field (canonical value, exact surface, span)
ex.candidates(note, "performance_status")   # -> [RuleCandidate(value='ECOG 1', matched_text='1', ...)]

# pass an extracted value into validate_field (lineage = rules_v1, independent of any LLM)
res = ex.extract(note, FieldSpec(name="clinical_stage", field_type=FieldType.STAGING))
record = validate_field(
    res.value, note, field_type=FieldType.STAGING, field_name="clinical_stage",
    claimed_span=res.source_span, value_lineage=rules_lineage(source_id="note_1"),
)

# structured TNM read (no inference)
parse_tnm("cT2a N0 M0")  # prefix='c', t='T2a', n='N0', m='M0', completeness='complete'
```

End-to-end on a batch: `notevahti extract-validate input.json --out out.json --audit audit.jsonl`.

## Examples

| Note (excerpt) | Field | Candidate value |
|---|---|---|
| `ECOG PS 1` / `Toimintakyky 1` / `Funktionsstatus 1` | performance_status | `ECOG 1` |
| `cT2aN0M0` / `cT2a N0 M0` | clinical_stage | `cT2a N0 M0` (surface) |
| `Discussed at MDT` / `tumour board` / `moniammatillisessa kokouksessa` | mdt_discussed | `MDT discussed` |
| `EGFR exon 19 deletion` | biomarker | `EGFR exon 19 deletion` |
| `EGFR negatiivinen` | biomarker | `EGFR negative` |
| `PD-L1 TPS 80%` | biomarker | `PD-L1 TPS 80%` |
| `Plan: SABR` / `lobektomia` / `konkomitantti kemosädehoito` | treatment_plan | `SABR` / `lobectomy` / `chemoradiotherapy` |

## Limitations

- Implicit staging (size/nodal prose without an explicit TNM token) is **not** inferred — that is an
  extractor inference, not string matching; such a value has no span and NoteVahti routes it to
  review.
- Partial Nordic morphology coverage; the catalogue is a baseline, not exhaustive.
- Not a clinical NLP model and not a truth source; extraction only, no clinical claim.
