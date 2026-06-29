# Synthetic Nordic lung-cancer MDT corpus — sizing and design

**Status: design document.** This describes the planned synthetic development corpus and its target
size. It is not a validation claim. Real patient data is held out as a separate external validation
set (see [lung_mdt_stage1_protocol.md](lung_mdt_stage1_protocol.md)).

The machine-checkable contract for one case lives in
[`corpus/schema/synthetic_case.schema.json`](../../corpus/schema/synthetic_case.schema.json); the
matching typed model and a dependency-free validator are in
[`notevahti.corpus.synthetic`](../../src/notevahti/corpus/synthetic.py). A test asserts the two
agree so they cannot drift.

## What the dataset is for

The goal is **not** "teach a model medicine." It is **teach a model to return the same structured
JSON reliably across different Nordic MDT texts**, with each field bound to its in-note evidence and
an explicit `requires_review` when the note does not support a value. Because the schema is strict
and the ground truth is machine-checkable, a moderate *n* can be credible.

This corpus is a **controlled development and stress-test set**, not a substitute for validation on
real registry data.

## How much data (target *n*)

| Use | n per language | Six languages | Purpose |
| --- | --- | --- | --- |
| Pilot | 50 | 300 | Shake out the prompt, the JSON schema, and the error types |
| Fine-tuning minimum | 150 | 900 | Enough for a first small fine-tune |
| Research version | **300** | **1800** | Recommended level for a grant and a methods paper |
| Extended | 500 | 3000 | Better per-language and subgroup analysis |

**Recommendation: 300 per language (1800 total).** It is credible without inflating the project.
Below ~150/language reads as a toy; above ~500/language looks oversized for a small grant.

> Sizing rationale. Vendor fine-tuning guides (OpenAI; Azure OpenAI) suggest starting from a few
> dozen well-formed examples and scaling up as performance improves, and note that in practice
> hundreds-to-thousands of examples are a better target than tens. Clinical information-extraction
> literature reports that synthetic data can improve extraction models and reduce reliance on
> manually annotated data — while still requiring real patient data for external validation.
> **Confirm the exact figures and citations before submission;** they are paraphrased here, not
> quoted.

## One case, three documentation formats

Each case is authored once at the **case level** (one patient, one ground truth) and rendered in
three documentation formats, mirroring the ntog.org tools:

1. free MDT text,
2. structured-mini summary,
3. structured v3.1 form.

So 300 cases/language yields 300 clinical ground truths but 900 text variants per language, i.e.
**5400 text variants across six languages**.

## Train / dev / test split — at the case level

| Split | Share | Example at 300 cases/language |
| --- | --- | --- |
| Train | 70 % | 210 |
| Dev | 15 % | 45 |
| Test | 15 % | 45 |

**The split is assigned per case, never per rendered variant.** The same patient must not appear as
free text in train and as structured v3.1 in test — that is leakage. The `split` field is recorded
on the case (see the schema), and every rendered variant inherits it.

## Case-type distribution — do not generate 300 clean cases

A corpus of only tidy cases teaches nothing and cannot validate the hard behaviour (no-guess,
ambiguity, negation, temporality). Target distribution:

| Case type | Share | n at 300/language | Difficulty tag |
| --- | --- | --- | --- |
| Explicit MDT + ECOG + TNM | 30 % | 90 | `explicit` |
| Missing ECOG | 10 % | 30 | `missing_ecog` |
| Partial TNM | 10 % | 30 | `partial_tnm` |
| Conflicting TNM | 10 % | 30 | `conflicting_tnm` |
| Old vs current staging | 10 % | 30 | `old_staging` |
| MDT planned but not done | 5 % | 15 | `future_mdt` |
| MDT negated ("not yet discussed") | 5 % | 15 | `negated_mdt` |
| Indirect performance status, no explicit ECOG | 10 % | 30 | `indirect_ecog` |
| Biomarkers + recommendation as distractors | 10 % | 30 | `distractor_biomarkers` |

These map directly to the behaviours NoteVahti's deterministic core and reference extractor already
encode (negation, future-intent suppression, conservative TNM, no-guess on conflict).

## Case model

The canonical on-disk shape is one JSON object per case. Required: `case_id`, `language`,
`documentation_format`, `messiness`, `truth`, `note`. The `truth` block is the machine-checkable
ground truth; `expected_output` is the supervised target (value + verbatim evidence +
`requires_review`); `difficulty_tags` records the case type. TNM uses the same vocabulary as
`parse_tnm` (`prefix`, `t`, `n`, `m`, `completeness`, `edition`).

A worked example is committed at
[`corpus/schema/example_case.fi.json`](../../corpus/schema/example_case.fi.json). The full field
list, enums and defaults are in the JSON Schema.

## Fine-tuning format

Fine-tuning examples should be boring and identical every time: a fixed instruction, the note, and
the JSON target. A provider-agnostic chat-format example (one supported case, one
not-yet-supported case) is committed at
[`corpus/schema/finetuning_record.example.jsonl`](../../corpus/schema/finetuning_record.example.jsonl).
The instruction states: extract the named fields, return only valid JSON, and where the note does
not explicitly support a value, return `null` and set `requires_review=true`.

Fine-tuning records are derived deterministically from a case's `expected_output`; they are not a
second source of truth.

## Ready-to-paste grant paragraph (FI)

> Synteettisen pohjoismaisen MDT-aineiston tavoitteena ei ole korvata oikean rekisteriaineiston
> validointia, vaan luoda kontrolloitu kehitys- ja stressitestiaineisto. Aineisto tuotetaan
> tapaustasolla niin, että jokaisella tapauksella on koneellisesti tarkistettava ground truth ja
> kolme dokumentaatiomuotoa: vapaa teksti, suppea rakenteinen MDT-yhteenveto ja laaja rakenteinen
> MDT-lomake. Tavoitekoko on 300 tapausta per kieli, yhteensä 1800 synteettistä tapausta. Jokainen
> tapaus tuotetaan kolmessa dokumentaatiomuodossa, jolloin analysoitavia tekstivariantteja syntyy
> 5400. Fine-tuning- ja evaluointijako tehdään tapaustasolla data leakage -riskin välttämiseksi.
> Oikea vuoden 2024 rekisteriaineisto pidetään erillisenä ulkoisena validointiaineistona.
