# NoteVahti — pathway: research tool → validated tool → (optional) certified device

Status: draft for review, 2026-06. Grounded in [docs/research/notevahti-research-2026-06.md].
This document is the map from "useful research artefact" to "clinically validated tool" and, only if
ever deliberately chosen, to "regulated medical device software." Each stage states its purpose, the
evidence it must produce, the reporting standard that governs it, and the regulatory line it must not
cross by accident.

## The one principle that controls regulatory status

Under EU MDR, **what makes software a medical device is the manufacturer's declared intended
purpose, not the technology** (MDCG 2019-11). NoteVahti can stay a research/quality tool *for as long
as it makes no diagnostic or therapeutic claim* and presents validation evidence for human
verification rather than a clinical recommendation. The moment its stated purpose is to inform a
diagnostic/therapeutic decision, it falls under **MDR Rule 11 → class IIa or higher**. The pathway is
therefore designed so that crossing that line is a *decision*, never an accident. Every stage below
keeps the intended-purpose statement explicit.

## Stage gates (overview)

| Stage | Purpose | Primary evidence | Reporting standard | Regulatory status |
|---|---|---|---|---|
| 0. Research harness | Deterministic validation works, offline | Unit/property tests, audit chain | (engineering) | Not a device |
| 1. Retrospective silent | Does the validity flag predict real abstraction errors? | Agreement vs reference cohort, calibration curve | TRIPOD+AI | Not a device (research use only) |
| 2. Prospective silent | Holds on unseen, contemporaneous cases, no influence on registry | Prospective agreement + error-detection metrics | TRIPOD+AI / STARD-AI | Not a device |
| 3. Early live evaluation | Does it help a human abstractor without harm? | Small-scale human-in-loop study, usability, cognitive load | DECIDE-AI | Boundary — decision point |
| 4. Comparative / certified | Only if a clinical claim is chosen | Comparative study; QMS; clinical evaluation | CONSORT-AI / MI-CLAIM + MDR | Class IIa+ MDSW |

NoteVahti's stated near-term destination is **Stage 2–3**: a validated research/quality tool. Stage 4
is out of scope unless and until you decide to make a clinical claim.

## Stage 0 — Research harness (the v0.1 build)

- **Purpose:** prove the deterministic validation core does what it says — provenance binding,
  rule-based validity score, independent-anchor refusal, agreement metrics, tamper-evident audit —
  fast, offline, reproducible.
- **Evidence:** test suite is the gate. Property tests for the audit chain (tamper → detected),
  golden tests on the synthetic MDT corpus, a test asserting the core makes no network calls.
- **Intended-purpose statement:** "research and data-quality tooling; not a medical device; provides
  validation evidence for human review; makes no diagnostic or therapeutic recommendation."
- **Exit criterion:** harness runs end-to-end on synthetic MDT notes with a known ground truth and
  produces one auditable `ValidationRecord` per field.

## Stage 1 — Retrospective silent validation (the first real claim)

- **Question that must be answered:** *does the validity flag actually predict true abstraction
  errors?* This is the open empirical question named in the design note. Until Stage 1, NoteVahti
  claims only mechanism, not predictive value.
- **Design:** apply NoteVahti to a retrospective set of real MDT notes with an **independent
  reference standard** (adjudicated registry values produced *without* NoteVahti and *without* the
  extractor under test — the independence rule applies to the study, not just the code). Compute:
  agreement vs reference (κ, accuracy, F1 per field), and the validity score's discrimination
  (does flag=review concentrate the true errors? sensitivity/specificity of the flag, AUROC, and a
  calibration curve — reported, not guaranteed).
- **Reporting standard:** **TRIPOD+AI** (prediction-model reporting; the validity score is a
  prediction of error). Pre-register the analysis.
- **Data governance:** real PHI → processed under Findata secure-environment rules (no internet),
  pseudonymised. Local-first means the tool can run *inside* that environment unchanged.
- **Honest-failure clause:** if the flag does not concentrate errors better than chance, that is a
  publishable negative result and a redesign trigger — not something to bury.

## Stage 2 — Prospective silent validation

- **Purpose:** show Stage 1 holds on contemporaneous, unseen cases while NoteVahti runs *silently*
  (its output does not change what enters the registry).
- **Evidence:** prospective agreement and error-detection metrics; drift check across sites/time;
  per-field-type calibration monitoring (because miscalibration direction varies by field type).
- **Reporting standard:** TRIPOD+AI; STARD-AI if framed as diagnostic accuracy of the error-flag.
- **Still not a device:** silent operation with no clinical claim keeps it research-use.

## Stage 3 — Early live evaluation (the boundary)

- **Purpose:** the question that the DeepPhe-CR study left open — does surfacing validation evidence
  actually *help a human abstractor* (faster, fewer errors) without raising cognitive load to the
  point of harm? Recall the PaperTrail caution: more provenance lowered trust and raised load. This
  stage tests the *human-tool system*, not the model.
- **Design:** small-scale, controlled, human-in-the-loop with registry abstractors; measure
  abstraction error rate, time, trust, and cognitive load; A/B the verdict+flag default vs full-span
  display.
- **Reporting standard:** **DECIDE-AI** (early small-scale live clinical evaluation — exactly this
  stage).
- **Decision point:** if the tool only ever *informs a human who makes the registry entry*, it can
  remain a quality tool. If the intended purpose shifts to *driving* a clinical/diagnostic decision,
  Stage 4 and MDR apply. This must be a written decision with legal review.

## Stage 4 — Comparative evaluation / certification (only if a clinical claim is chosen)

- **Purpose:** support a clinical claim (out of current scope). Requires a comparative study, an
  ISO 13485 quality management system, MDR technical documentation, clinical evaluation, and a
  notified body for class IIa+.
- **Reporting standards:** **CONSORT-AI** (trial reporting), **SPIRIT-AI** (protocol), **MI-CLAIM**
  (model documentation: data provenance, pre-deployment docs, post-deployment monitoring).
- **EU AI Act:** confirm the risk tier with counsel — a tool co-deployed as MDSW under MDR is liable
  to inherit high-risk obligations; a research-only, no-claim tool generally is not. This is an
  unverified gap in the research pass and must be resolved by legal review before any clinical claim.

## Data-integrity expectations throughout (ALCOA++)

Registries are held to data-integrity principles in the **ALCOA++** spirit: Attributable, Legible,
Contemporaneous, Original, Accurate — plus Complete, Consistent, Enduring, Available. NoteVahti's
audit record is designed to meet these (attributable adjudications, contemporaneous timestamps,
tamper-evident chaining, local durability). *Caveat: ALCOA++ specifics for registry audits are
asserted from domain knowledge; the research pass did not verify a citable registry-specific
mapping. Confirm against your registry's SOPs.*

## What we will never claim (carried from the research)

- No "guaranteed error rate" / distribution-free conformal coverage (refuted in evidence).
- No diagnostic/therapeutic recommendation while in research use.
- No validated predictive value for the score until Stage 1 produces it.

## Immediate next milestones

1. Stage 0 harness (`validate_field` + five outputs + synthetic MDT corpus) — the current build.
2. Pre-register the Stage 1 retrospective protocol (TRIPOD+AI) against an NTOG lung-cancer reference
   set, run inside the Findata secure environment.
3. Decide explicitly whether Stage 3 is the intended ceiling (recommended) or whether a Stage 4
   clinical claim is ever in scope (requires legal review first).
