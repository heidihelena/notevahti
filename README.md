# NoteVahti

![Validation status](https://img.shields.io/badge/validation-Stage_0%3A_not_clinically_validated-orange)
![Status](https://img.shields.io/badge/status-pre--alpha-lightgrey)
![License](https://img.shields.io/badge/license-Apache--2.0-blue)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.12-blue)

Transparent, local-first extraction-**validation** toolkit for clinical registry data.

> **Validation status: Stage 0 (not clinically validated).** NoteVahti produces validation *evidence*
> for human review, not a guarantee of correctness. Whether the validity flag predicts true
> abstraction errors is an open empirical question (Stage 1) — see
> [docs/design/pathway.md](docs/design/pathway.md).

NoteVahti is **not an extractor.** It is the deterministic trust/validation layer that sits between
*any* extractor (a human abstractor, a regex, a clinical NLP pipeline, an LLM) and a clinical
registry. Given an extracted field value and the source note it claims to come from — primarily an
**MDT (multidisciplinary team) meeting note** — NoteVahti answers one question, deterministically and
offline:

> Is there independent evidence that this value is correct, and how confident should a human be
> before trusting it?

## Why it matters

Manual abstraction from unstructured notes is the registry bottleneck; automated clinical NLP and LLM
extractors are increasingly accurate but **opaque**, and a registry of record cannot accept
un-auditable values. The documented unmet need is not another extractor but a **transparent,
local-first, validity-scored, auditable trust layer** around extraction: LLM hallucination is
unsolved and frequent, raw extraction accuracy alone has not translated into registry workflow
benefit, and flat source citations are too coarse and themselves hallucinated. NoteVahti targets that
gap. Evidence base and citations: [docs/research/notevahti-research-2026-06.md](docs/research/notevahti-research-2026-06.md).

## What it produces

For each field, one auditable `ValidationRecord` with five outputs:

1. **Provenance** — the value bound to a *verified* source span, or an explicit `no_span_found`
   (flagged as a likely hallucination).
2. **Validity score + review flag** — a transparent, rule-based heuristic, **not** a guaranteed error
   rate.
3. **Agreement** — κ / accuracy versus a reference set when one is supplied, else `not_available`
   (ordinal/weighted κ and Gwet's AC2 for staging are in `notevahti.analytics`).
4. **Independent-anchor check** — refuses to certify a validation where the validating signal is not
   independent of the value under test (no source grades itself).
5. **Audit record** — a local, append-only, tamper-evident entry (ALCOA++ in spirit).

An optional sixth layer sits on top:

6. **Review routing** (`notevahti.routing`) — a deterministic, trigger-gated layer that integrates
   the five outputs and a declared field impact into one auditable route: `accept`, `review`,
   `specialist_review`, or `blocked`. The routes are *validation routes, not truth labels*: `accept`
   ≠ correct, `blocked` ≠ wrong (it means the evidence cannot support auto-acceptance). Advisory, not
   enforcement, not a clinical recommendation. See
   [docs/design/validation_routing.md](docs/design/validation_routing.md).

## What is novel (and what is not)

- **Novel:** the *representation and auditability* — provenance binding + a calibrated-later validity
  heuristic + a **non-circular (independence-enforced)** validation + local-first + a tamper-evident
  audit, combined in one deterministic record, with a trigger-gated review route on top.
- **Not novel:** the NLP, the extraction, and the statistics (κ/accuracy/AUROC are standard).
- **Unproven (the open question):** whether the validity flag predicts *true* abstraction errors.
  NoteVahti is built so this can be answered (Stage 1) and says so rather than asserting it.

## Evidence so far

- **Stage 0 (built):** the deterministic harness — five outputs, audit chain, routing — runs offline
  and is covered by a test asserting the core makes no network calls.
- **Stage-1 signal on synthetic data (methodology, not validation):** on a synthetic clinical-note
  set (gold never fed to the validator) the review flag concentrates true against-gold errors at
  **~66× enrichment** (95% CI ~48–101), specificity 1.0, sensitivity ~0.60; the validity score
  reaches **AUROC ~0.80** (CI ~0.74–0.86). It catches absence-type errors and, by design, misses
  *present-but-wrong* values that need temporality/independent-anchor signals — characterised
  honestly in the tests. **This is a synthetic methodology demonstration, not clinical validation.**

Reproduce: `PYTHONPATH=src python3 scripts/stage1_report.py` (TRIPOD+AI evidence pack + preregistration
skeleton). See [docs/design/stage1_protocol.md](docs/design/stage1_protocol.md).

## Validation pathway

NoteVahti is **research-use first, clinically validated later**. The stages and the reporting
standards expected at each (TRIPOD+AI, STARD-AI, DECIDE-AI) are in
[docs/design/pathway.md](docs/design/pathway.md). The Stage-1 analysis is **preregistered and the
configuration frozen** before any tuning (`notevahti.analytics.preregistration`); a negative result
is publishable, not buried.

## Nordic and multilingual

The primary target is Nordic-language MDT notes. The synthetic corpus and the Stage-1 plan cover
**Finnish, Swedish, Norwegian, Danish, Icelandic and English**, and every analysis is reported per
language (pooled numbers hide where a tool fails). NoteVahti binds no vendor and assumes no single
registry.

## Principles

- **Bring your own extractor.** Any model/regex/LLM is pluggable; the core marries no vendor.
- **The validation core is deterministic** — no model inference, no network calls. Same inputs → same
  record.
- **Local-first.** PHI never leaves the institution; note text is hashed in the audit record by
  default.

## Quickstart

```python
from notevahti import validate_field
from notevahti.types import FieldType, Lineage, Signal, SignalKind

note = "MDT 2026-06-20. RUL adenocarcinoma. Clinical stage cT2a N0 M0. Plan: SABR."

record = validate_field(
    "cT2aN0M0", note,
    field_type=FieldType.STAGING, field_name="clinical_stage",
    value_lineage=Lineage(source_id="note_417", model_id="regex_v1"),
    anchors=[Signal("cT2aN0M0", Lineage(human_id="abstractor_B"),
                    SignalKind.INDEPENDENT_HUMAN)],   # an INDEPENDENT second signal
    review_threshold=0.80,
)

record.provenance.status               # SPAN_FOUND
record.independence.status             # SATISFIED
record.validity.flag_for_human_review  # False
record.to_dict()                       # JSON-serializable full record
```

A value not in the note is flagged as a likely hallucination; an anchor sharing lineage with the
value is refused as circular. Batch from the command line:

```
notevahti validate items.json --field-type staging --audit audit.jsonl
```

## Data protection and reproducibility

- **Local-first / no telemetry:** the core makes no network calls (enforced by a test) and has **no
  runtime dependencies**; PHI does not leave the process. This aligns with secure-environment
  secondary-use regimes (e.g. Finland's Findata; GDPR). See [SECURITY.md](SECURITY.md).
- **Deterministic and reproducible:** same inputs → same record; all resampling is seeded; hashing is
  stdlib SHA-256.
- **FAIR / quality-gated:** Apache-2.0, [CITATION.cff](CITATION.cff), `ruff` + `mypy --strict` + a
  socket-disabled `pytest` suite (154 tests) on Python 3.10–3.12 in CI.

## Project status and roadmap

Pre-alpha (`0.1.0.dev0`). Built: the Stage-0 harness, review routing, the Stage-1 analytics
(agreement, discrimination, evidence pack, preregistration), and a deterministic multilingual
synthetic corpus. **Next is not code but data:** an independent reference cohort to run the
preregistered Stage-1 study and answer the open question. Design notes: [docs/design/notevahti.md](docs/design/notevahti.md),
build plan: [SKILL.md](SKILL.md).

## How to cite

See [CITATION.cff](CITATION.cff) (GitHub renders a “Cite this repository” button). No DOI yet.

## Development

```
pip install -e ".[dev]"   # core has no runtime dependencies
pytest                    # 154 tests; deterministic, offline
ruff check . && mypy --strict src/notevahti
```

## Boundary

NoteVahti is **not a medical device** and **not clinical advice**. It provides *validation evidence*
for human review; it does **not** guarantee the correctness of any value, and no distribution-free /
conformal coverage is claimed. Whether the validity score predicts true abstraction errors is an open
empirical question to be answered by validation studies, not asserted.

## License and funding

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE). NoteVahti is an open, non-commercial
research/quality tool in the Vahtian family; it is at the R&D and credibility stage and is seeking
support for the Stage-1 validation study (independent reference cohort).
