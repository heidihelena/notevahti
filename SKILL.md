---
name: build-notevahti
description: >
  How to build NoteVahti — a transparent, local-first extraction-VALIDATION toolkit for clinical
  registry data (primary source: MDT meeting notes). Use when implementing or extending the
  validation harness. Encodes the architecture, the non-negotiable principles, the build order
  (one small verified PR per step), the synthetic-data and local-model decisions, and the
  testing-as-gate discipline. Grounded in docs/research/notevahti-research-2026-06.md.
---

# Building NoteVahti

NoteVahti is **not an extractor**. It is the deterministic trust/validation layer that sits between
*any* extractor (human, regex, NLP, LLM) and a clinical registry, and produces an auditable verdict
per field. If you are about to add a model to the *core*, stop — the core is model-free by design.

Read first: [docs/design/notevahti.md] (architecture), [docs/design/pathway.md] (research→validated),
[docs/research/notevahti-research-2026-06.md] (the evidence). This file is the *how*.

## Non-negotiables (every PR is checked against these)

1. **AI orchestrates and validates; it never IS the source of truth.**
2. **Provenance or it didn't happen.** Every field binds to an exact source span, or is flagged as a
   likely hallucination. NoteVahti *verifies* the claimed span; it does not take the extractor's word.
3. **The validation core is deterministic — no model inference inside it.** Same inputs → same record.
4. **Independent-anchor rule.** A signal counts toward validity only if its declared lineage is
   disjoint from the value-under-test's lineage. Unknown lineage cannot satisfy the check. A
   non-independent validation is *refused*, not warned.
5. **Validity is a documented heuristic, never a guaranteed error rate.** Do not implement or claim
   conformal/distribution-free coverage guarantees — the research refuted them for this setting.
6. **Local-first.** No network calls in the core path. A test asserts this. PHI (note text) is
   hashed in the audit record by default; retaining text is an explicit local opt-in.
7. **Verdict + flag is the primary output; evidence is on-demand.** More provenance can raise
   cognitive load and lower trust (PaperTrail). Don't dump spans by default.
8. **State the boundary every time.** Not a medical device; not clinical advice; validation evidence,
   not a guarantee of correctness.

## Architecture in one screen

```
(value, note[, claimed_span][, anchors][, reference]) 
        │
        ▼
  VALIDATION CORE  (deterministic, offline, fast)
   1 provenance     value ↔ verified span | no_span_found→hallucination flag
   2 validity       rule-based score [0,1] + review flag (per field-type)
   3 agreement      κ/accuracy vs reference, else not_available
   4 independence   satisfied | violated | unknown  (refuse if not satisfied)
   5 audit          append-only, hash-chained, local, PHI hashed
        │
        ▼
  ValidationRecord   (the five outputs, bound together)
```

Extractors and any model live *outside* the core, behind an interface. The core must run with no
extractor at all (pass-through of already-extracted values).

## Build order — one small, verified, draft PR per step

> Status: **Steps 0–9 are implemented** (Stage 0 harness complete; 56 tests, deterministic, offline).
> This section now doubles as the map of what exists and how to extend it.

Tests are the gate; no CI assumed (local runner). Each step is mergeable on its own.

- **Step 0 — Scaffold.** hatchling, src layout, package `notevahti`, Apache-2.0 LICENSE, `NOTICE`,
  README with the boundary statement, `pytest`. PR adds nothing but structure + a passing trivial
  test. *(Repo decisions: dedicated public repo, Apache-2.0 — confirmed.)*
- **Step 1 — Types.** `ValidationRecord`, `Provenance`, `Validity`, `Agreement`, `Independence`,
  `Lineage`, `Signal`, `FieldSpec`, `ExtractionResult`. Pure dataclasses/pydantic, no logic. Tests:
  construction + serialization round-trip.
- **Step 2 — Provenance.** `verify_span(value, note, claimed_span) -> Provenance`. Confirms the span
  exists and its text is consistent with the value (normalised match); `no_span_found` otherwise.
  Tests: exact match, normalised match (case/whitespace/synonyms via a small rule table), wrong span,
  missing span → hallucination flag.
- **Step 3 — Independence.** `check_independence(value_lineage, anchors) -> Independence`. Enforces
  disjoint lineage; `unknown` when undeclared; `violated` with reason when shared. Tests: the three
  outcomes, plus the refusal path (violated → not reported as a pass).
- **Step 4 — Validity score.** `score_validity(provenance, anchors, independence, field_type) ->
  Validity`. Transparent weighted rule (span presence/quality + value/span consistency + independent
  anchor agreement), weights in a visible config, per field-type. Maps to `flag_for_human_review`.
  Tests: monotonicity (more support → higher score), flag threshold, no-span → low score + flag.
- **Step 5 — Agreement.** `agreement(values, reference) -> Agreement` (Cohen's κ, accuracy, per-field
  F1) or `not_available` with no reference. Tests against hand-computed κ; never fabricates when
  reference is absent.
- **Step 6 — Audit.** Append-only JSONL, each record carrying the prior record's hash (chain). PHI
  hashed by default. Tests: chain verifies, tamper → detected, attribution + timestamp present.
- **Step 7 — Orchestrator.** `validate_field(...) -> ValidationRecord` wiring 2–6 together. Tests:
  end-to-end on the synthetic MDT corpus with known ground truth.
- **Step 8 — Extractor interface + example adapters.** `Extractor` Protocol; a pass-through adapter
  (already-extracted values) and a trivial regex adapter. *No production extractor.* Tests: adapters
  satisfy the Protocol; swapping the extractor does not change the validation contract.
- **Step 9 — Batch + CLI.** `notevahti validate ...` over a file of fields/notes; JSON out. Thin
  wrapper over the core. Tests: CLI smoke + JSON shape.

Only after Step 9 is the harness "Stage 0 complete" per the pathway. Stage 1 (does the flag predict
real errors?) is a *study*, not code — see [docs/design/pathway.md].

## Synthetic MDT corpus (the test fixture)

Generator: `scripts/gen_corpus.py` (deterministic, offline, seeded). It mirrors the three NTOG MDT
tools — `mdt.html` (free text), `mdt-structured-mini.html` (semistructured), `mdt-structured-v3_1.html`
(fully structured) — across six languages for the free-text modality (fi, sv, nb, da, is, en) and
English for the two structured tools, at 500 cases/group by default (4000 total). Regenerate with:

```
PYTHONPATH=src python3 scripts/gen_corpus.py --n 500 --out corpus   # corpus/ is git-ignored
```

The harness is developed against synthetic lung-cancer MDT notes with a **known ground truth** — the
case is generated from a clinical schema, so the correct registry value is known by construction.
This is the ideal fixture for a validation harness and keeps development outside the Findata
secure-environment constraint (no real PHI).

Each case ships six gold fields with exact spans (histology, clinical_stage/cTNM, treatment intent,
treatment, PD-L1 TPS, driver alteration). `tests/test_gen_corpus.py` asserts every gold span resolves
through NoteVahti's own provenance check — fixture and tool must agree.

Each case also carries a `challenges` block with two adversarial extraction targets that test the
*validity heuristic*, not just provenance:
- **surface_variant** — a correct value whose surface differs from the note (spacing/case), found
  only via normalized/compact matching. Should validate as correct (it does: 100% pass).
- **present_but_wrong** — a wrong value that nonetheless appears in the note (the pre-MDT cTNM, which
  the tools record), so provenance returns SPAN_FOUND (not a hallucination). Only an independent
  anchor / the validity heuristic can catch it.

Finding from the present-but-wrong cases (n=2600): with a *disagreeing* independent anchor, only
**13%** are flagged — a wrong-but-present value scores ~0.74–0.80 and clears the 0.80 threshold
because a single disagreeing anchor (anchor_agreement→0, weight 0.20) cannot pull a
strong-provenance value below threshold. This is the kind of weighting/threshold issue Stage-1
calibration must fix; a principled candidate is to flag whenever an independent anchor disagrees,
regardless of score. Recorded here, not silently changed.

- Generate with a capable **general** LLM and structured prompting from TNM/staging schemas — the
  research found no advantage for medical-specific generators for *generation*. Seed from ntog.org
  simulation tooling where possible.
- Each synthetic case ships as `(note_text, {field: gold_value, gold_span})` so provenance,
  agreement, and the validity flag can all be tested against truth.
- Include adversarial cases on purpose: value present but in the wrong span; value absent (forces
  hallucination flag); near-synonyms; conflicting statements across MDT authors.
- **Measure, don't assume, synthetic realism and re-identification risk** before publishing the
  corpus. Keep generation prompts and schema in-repo; keep any real-data-derived seeds out.

## The local model — adapter, never core

Evidence: a LoRA/QLoRA-finetuned open model (e.g. Llama-3.1 8B) reaches human-level extraction and
runs on a single hospital workstation (~48 GB GPU). So a local extractor is viable and is the right
default *when an extractor is wanted* — but it is plugged in behind `Extractor`, never inside the
validation core.

- Span extraction: **GLiNER** or clinical-BERT-family models.
- Generative extraction: **Llama/Mistral** LoRA/QLoRA finetunes.
- Local serving: **llama.cpp / Ollama / vLLM**.
- Rule: the model is an optional dependency in an `extras` group; `pip install notevahti` (core) pulls
  no model. The core test suite runs with zero models installed.

## Definition of done (per PR)

- Tests added and passing locally; the no-network-in-core test still passes.
- Boundary statement present where user-facing.
- Determinism preserved in the core (no clock/RNG/model in core logic; inject them at the edge).
- Draft PR, small, one step, with a description that names the principle it upholds.
- Commit trailer: `Co-Authored-By: Claude <noreply@anthropic.com>`.

## Do not

- Put a model, network call, clock, or RNG inside the validation core.
- Let an extractor grade itself, or count an anchor with unknown/shared lineage.
- Claim a calibrated/guaranteed error rate, or any diagnostic/therapeutic purpose.
- Default to dumping all spans/evidence at the user — verdict + flag first.
- Store raw PHI in the audit record unless the caller explicitly opts in locally.
