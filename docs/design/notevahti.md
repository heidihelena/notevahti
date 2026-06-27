# NoteVahti — design note (v0.1)

Status: revised 2026-06 after a deep-research evidence pass; the **Stage 0 harness is now
implemented** against this note (56 tests, deterministic, offline — see [CHANGELOG.md] and
[SKILL.md]). Evidence base: [docs/research/notevahti-research-2026-06.md].
Primary source NoteVahti targets: **MDT (multidisciplinary team) meeting free-text notes**, for
**research use first, clinical validation later** (see [docs/design/pathway.md]).

## What the research changed (read this first)

The deep-research pass confirmed the core bet and forced four adjustments:

1. **The trust layer is the right product, with evidence.** Hallucination is unsolved and frequent;
   raw extraction accuracy did not translate into workflow time savings in a registry user study; and
   flat citations are too coarse and themselves hallucinated. The unmet need is validation, not
   another extractor.
2. **Provenance must be span/claim-level — but more provenance can backfire.** A controlled study
   found granular provenance *lowered* user trust and *raised* cognitive load without changing
   reliance. So the default output is a **verdict + flag**, with the supporting evidence available on
   demand, not an always-on wall of spans. Cognitive load is a first-class design constraint.
3. **Do not claim calibrated risk control.** Conformal-prediction coverage guarantees for clinical
   extraction were *refuted* in the evidence, and miscalibration direction reverses across domains.
   The validity score is a **documented, monitorable heuristic**, fit per field-type, never a
   guaranteed error rate. This is the honest-novelty boundary made concrete.
4. **The independent-anchor rule is vindicated.** "Agreement is not validity" is the canonical
   reliability-vs-validity result; high κ can come from biased guidelines. The refusal to let a source
   validate itself is the load-bearing idea, not a nice-to-have.

Local-first is not just our preference: Finnish secondary-use law (552/2019, Findata) *requires*
individual-level data to be processed in a secure environment without internet access. The
architecture is aligned with the regulation, not merely tolerated by it.

## What it is

NoteVahti is a transparent, local-first **extraction-validation** toolkit for clinical registry
data. It does not extract values from notes. It validates values that *something else* extracted —
a human abstractor, a regex, a clinical NLP pipeline, an LLM — by asking a single question of each
field, deterministically and offline:

> Given this extracted value and the source note it claims to come from, is there independent
> evidence that the value is correct, and how confident should a human be before trusting it?

NoteVahti is the **trust/validation layer around extraction**, not another extractor. The market
already has black-box LLM clinical extractors; a registry of record cannot accept un-auditable
values. The deliverable is the harness that sits between extraction and the registry and produces
an auditable verdict per field.

## What it is not (the boundary, stated plainly)

- Not a medical device. Not clinical advice. Not a diagnostic.
- Not a guarantee of correctness. NoteVahti produces *validation evidence* — a provenance record,
  a calibrated validity score, agreement metrics, an independence check, and an audit record. It
  does not certify that a value is true.
- Not a better NLP engine. The novelty is representation and auditability, not extraction accuracy.
- Not a statistics contribution. The agreement metrics (κ, accuracy) are standard; the contribution
  is binding them to provenance and an independence constraint in one auditable record.

## The principle (non-negotiable)

The AI orchestrates and validates; it never *is* the source of truth. Every consequence below
follows from that one rule:

- **Bring-your-own extractor.** Any model, regex, or LLM is pluggable behind one interface. We never
  marry a vendor.
- **Provenance or it didn't happen.** Every extracted field must bind to its exact source span. A
  field with no supporting span is flagged as a likely hallucination — not silently accepted.
- **A calibrated validity score** per field, plus a flag-for-human-review threshold.
- **Independent-anchor validation.** The extractor must not grade itself. Agreement is not accuracy:
  a κ of 0.95 between an extractor and a reference derived from the same source, the same model, or
  the same human is circular. NoteVahti requires a second, *independent* signal and refuses to
  report a validation that lacks one.
- **Audit trail** in an ALCOA++ spirit: attributable, contemporaneous, traceable, tamper-evident.
- **Local-first.** PHI never leaves the institution. No upload, no external calls in the core path.

## Architecture — the layers

```
            ┌──────────────────────────────────────────────────────────┐
  INPUT     │  (extracted field value, source note text [, reference])  │
            └──────────────────────────────────────────────────────────┘
                                      │
        ┌─────────────────────────────┴─────────────────────────────┐
        ▼                                                             ▼
  ┌───────────────┐                                          ┌────────────────┐
  │ Extractor      │  pluggable, BYO. NoteVahti never        │ Anchor sources │
  │ interface      │  requires a specific one. Used only      │ (independent)  │
  │ (optional)     │  to (re)produce candidate fields.        │                │
  └───────────────┘                                          └────────────────┘
        │                                                             │
        ▼                                                             ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  VALIDATION CORE  (deterministic, no model inference, fast, offline)        │
  │                                                                            │
  │  1. Provenance         value ↔ source span, or "no span found"             │
  │  2. Validity score     calibrated score + review flag                      │
  │  3. Agreement          κ / accuracy vs a reference set, when supplied      │
  │  4. Independence check refuse to let one source validate itself            │
  │  5. Audit record       deterministic, local, tamper-evident chain         │
  └──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
            ┌──────────────────────────────────────────────────────────┐
  OUTPUT    │  one ValidationRecord per field (the five outputs, bound)  │
            └──────────────────────────────────────────────────────────┘
```

The validation core is the moat: it is deterministic (no model inference inside it), so it is
transparent, fast, and reproducible. The same inputs always produce the same record. Anything that
*requires* a model (extraction, optional semantic anchoring) lives outside the core and behind an
interface.

## The pluggable-extractor interface

The extractor is optional and never trusted as truth. It exists so NoteVahti can (a) accept fields
a caller already extracted, or (b) re-run an extractor to compare. The contract is intentionally
thin:

```python
class Extractor(Protocol):
    def extract(self, note: str, field: FieldSpec) -> ExtractionResult: ...
    # ExtractionResult carries: value, source_span (char offsets) | None, extractor_id, version
```

NoteVahti supplies adapters as examples (a trivial regex extractor, a "pass-through" for
already-extracted values) but ships no production extractor and binds to no vendor. The point of the
interface is that swapping the extractor never changes the validation contract.

## The five v0.1 outputs (one ValidationRecord per field)

1. **Provenance record** — the value, and the exact source span (character offsets into the note)
   that supports it, or an explicit `no_span_found`. No span → the field is flagged as a likely
   hallucination. Provenance is verified by NoteVahti, not taken on the extractor's word: the claimed
   span must actually contain text consistent with the value.

2. **Validity score + review flag** — a score in [0, 1] with a documented, deterministic derivation
   (e.g. span presence and quality, value/span consistency, anchor agreement). A threshold maps the
   score to `flag_for_human_review`. The score is a *prediction of trustworthiness*, not a
   probability of truth, and is labelled as such — and explicitly **not** a calibrated/conformal error
   rate (the research refuted distribution-free guarantees for clinical extraction; miscalibration
   even reverses direction across field types). v0.1 ships the score as a transparent, rule-based,
   per-field-type heuristic whose weights you can see and change; calibration against a reference set
   is a later, evidence-driven step that is *monitored*, not *promised*. The review flag — not the
   raw score — is the primary output, to keep cognitive load down. Whether the score actually
   predicts true abstraction errors is the open empirical question (see "Honest novelty boundary").

3. **Agreement-vs-gold metrics** — when a reference (gold) set is supplied, standard κ and accuracy,
   computed deterministically, with the n and the confusion detail retained for audit. Absent a
   reference, this output is `not_available` rather than fabricated.

4. **Independent-anchor check** — the validation is rejected as *circular* unless the validating
   signal is independent of the extracted value's source. Each signal declares its lineage
   (`source_id`, `model_id`, `human_id` as applicable); if the anchor shares lineage with the value
   under test, NoteVahti refuses to certify and emits `independence: violated` with the reason. This
   is a refusal, not a warning: a non-independent validation is not reported as a pass.

5. **Audit record** — a deterministic, local, append-only record per field and per adjudication:
   inputs (hashed where PHI-sensitive), the four outputs above, the NoteVahti version, and any human
   adjudication (who, when, what changed, why). Records are chained (each carries the hash of the
   prior) so tampering is detectable. Attributable, contemporaneous, traceable.

## The independent-anchor rule (why it is the core of the design)

The failure mode NoteVahti exists to prevent is **shared-reference bias**: an extractor graded
against a reference that is not truly independent of it will look excellent and be wrong. Examples
that NoteVahti must catch and refuse:

- An LLM extractor "validated" by the same LLM (or family) acting as judge.
- An extractor compared to a gold set that was itself produced by that extractor and lightly edited.
- A second human reviewer who saw the first reviewer's answer before recording their own.

The rule: a validation signal may only count toward the validity score if its declared lineage is
disjoint from the value-under-test's lineage. NoteVahti does not infer independence; the caller
declares lineage, and NoteVahti enforces disjointness and records the declaration. If lineage is
undeclared, independence is treated as `unknown` and cannot satisfy the check. This keeps the
guarantee honest: NoteVahti can prove it *required* independence, even though it trusts the caller's
lineage declarations.

## Local-first guarantee

The core path makes **no network calls**. PHI (note text) stays in process and on the institution's
disk. Where the audit record needs to reference note content, it stores a hash, not the text, unless
the caller explicitly opts into retaining text locally. Any component that would need a network call
(e.g. an LLM-based extractor or semantic anchor) is outside the core, behind the interface, and
off by default. This is a testable property: the test suite asserts the core makes no outbound
connections.

## Honest novelty boundary

- **What is novel:** the *representation* and *auditability* — provenance binding + calibrated
  validity + a non-circular (independence-enforced) validation + local-first + tamper-evident audit,
  combined in one deterministic record.
- **What is not novel:** the NLP, the extraction, and the statistics (κ/accuracy are standard).
- **What is unproven:** whether the validity score actually predicts true abstraction errors. This
  is an open empirical question. NoteVahti states this in its documentation and does not claim the
  score is validated until there is evidence from a reference cohort. The tool is built so that this
  question *can* be answered (the audit trail captures the data needed to test it).
- **What the evidence refuted (so we will not claim it):** distribution-free conformal coverage
  guarantees for clinical extraction. We will not market a "guaranteed error rate." We will report a
  monitored heuristic and its agreement-vs-reference performance, nothing stronger.

### MDT notes as the primary source

NoteVahti's first-class input is the **MDT meeting free-text note**: terse, abbreviation-heavy,
multi-author, often the authoritative summary of the staging/treatment decision for a registry. This
is harder than pathology reports (less templated) and is exactly where a validation layer earns its
keep — the value an abstractor records (e.g. clinical stage, planned treatment) must be bound to the
sentence in the MDT note that decided it, or flagged. The synthetic development corpus (below) is
MDT-note-shaped for this reason.

## v0.1 API surface (proposed, for review)

A single, small, deterministic entry point. Sketch — names and shapes are what I'm asking you to
react to, not final:

```python
from notevahti import validate_field, ValidationRecord, Signal, Lineage

record: ValidationRecord = validate_field(
    value="cT2aN0M0",                    # the extracted value under test
    note=note_text,                      # the source note (stays local)
    claimed_span=(412, 420),             # extractor's claimed source span, or None
    value_lineage=Lineage(source_id="note_417", model_id="regex_v1"),
    anchors=[                            # independent validation signals
        Signal(value="cT2aN0M0",
               lineage=Lineage(human_id="abstractor_B"),
               kind="independent_human"),
    ],
    reference=None,                      # optional gold value for κ/accuracy
    review_threshold=0.80,
)

record.provenance        # span found / no_span_found, verified
record.validity          # score in [0,1] + flag_for_human_review
record.agreement         # κ/accuracy or not_available
record.independence      # satisfied / violated / unknown (+ reason)
record.audit             # the chained, local audit entry
```

Batch and CLI wrappers (`notevahti validate ...`) come after the single-field core is right.
Everything above the `validate_field` core is convenience; the core is the contract.

## Packaging & conventions

- Dedicated public repo `github.com/heidihelena/notevahti`. Python first: hatchling, src layout,
  package `notevahti`. An R sibling is possible later (`notevahti` is a valid name in R too).
- License: Apache-2.0 (permissive + explicit patent grant), since transparency is the point.
- Tests are the gate; no CI assumed — a local test runner. One small, verified PR per step.
- Brand voice: understated, exact, honest-to-refusal. State the boundary every time.

## Synthetic corpus and the (optional) local model — design decisions

- **Synthetic MDT corpus, not real PHI, for development.** The harness is built and tested against a
  synthetic lung-cancer MDT-note corpus with a *known ground truth* (the case was generated from a
  schema, so the correct registry value is known by construction). This is the ideal fixture for a
  validation harness, and it keeps development outside the Findata secure-environment constraint.
  Generated by a capable general LLM with structured prompting from TNM/staging schemas (the research
  found no advantage for medical-specific generators), seeded where possible from ntog.org simulation
  tooling. Fidelity and re-identification risk are measured, not assumed.
- **The local model is a plug-in, never the validation core.** Evidence shows a LoRA/QLoRA-finetuned
  open model (e.g. Llama-3.1 8B) can reach human-level extraction and run on a single hospital
  workstation — so a local extractor is viable and is the right default *when an extractor is wanted*.
  But the validation core stays deterministic and model-free, so NoteVahti runs with any extractor or
  none. Local serving (llama.cpp/Ollama/vLLM) and span models (GLiNER, clinical-BERT family) are
  documented in SKILL.md as adapters, not dependencies.

## Decisions made in the Stage 0 build (were open questions — confirm or revise)

These were the open questions; the harness implements the recommended answer for each. They are
reversible — flag any you want changed.

1. **Validity score derivation.** Implemented fully rule-based and documented: components
   `span_presence` (.45), `span_quality` (.20), `independence` (.15), `anchor_agreement` (.20),
   weights visible in `validity.DEFAULT_WEIGHTS`, plus a hard ceiling (≤0.10) when no span is found.
   Calibration deferred to an evidence-driven step. — `src/notevahti/validity.py`.
2. **Independence by declaration, not inference.** Enforced on declared lineage; UNKNOWN when
   undeclared; VIOLATED (refused) when all anchors share lineage. Inference is out of scope.
   — `src/notevahti/independence.py`.
3. **Audit storage.** Append-only JSONL, per-record SHA-256 hash chaining, local file, no DB.
   — `src/notevahti/audit.py`.
4. **PHI in the audit record.** Note text and matched snippets hashed by default; raw text only on
   explicit `retain_text=True`. The registry value and span offsets are retained (the attributable
   subject of the audit). — `audit.audit_payload`.
5. **Scope.** Stage 0 ships the validation harness only: `validate_field` + the five outputs + a
   pass-through and a trivial regex example adapter + batch + CLI. No production extractor.

Still genuinely open (need your input, not yet built):
- The exact validity weights/threshold are first-draft guesses — they should be tuned against a
  reference cohort in Stage 1, not now.
- Batch-level agreement currently assumes a homogeneous field type; per-field grouping is a later
  refinement.
