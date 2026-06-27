# NoteVahti

Transparent, local-first extraction-**validation** toolkit for clinical registry data.

NoteVahti is **not an extractor.** It is the deterministic trust/validation layer that sits between
*any* extractor (a human abstractor, a regex, a clinical NLP pipeline, an LLM) and a clinical
registry. Given an extracted field value and the source note it claims to come from — primarily an
**MDT (multidisciplinary team) meeting note** — NoteVahti answers one question, deterministically and
offline:

> Is there independent evidence that this value is correct, and how confident should a human be
> before trusting it?

For each field it produces one auditable `ValidationRecord` with five outputs:

1. **Provenance** — the value bound to a *verified* source span, or an explicit `no_span_found`
   (flagged as a likely hallucination).
2. **Validity score + review flag** — a transparent, rule-based heuristic, not a guaranteed error
   rate.
3. **Agreement** — κ / accuracy versus a reference set when one is supplied, else `not_available`.
4. **Independent-anchor check** — refuses to certify a validation where the validating signal is not
   independent of the value under test (no source grades itself).
5. **Audit record** — a local, append-only, tamper-evident entry (ALCOA++ in spirit).

## Principles

- **Bring your own extractor.** Any model/regex/LLM is pluggable; the core marries no vendor.
- **The validation core is deterministic** — no model inference, no network calls. Same inputs → same
  record.
- **Local-first.** PHI never leaves the institution; note text is hashed in the audit record by
  default.

## Status

Pre-alpha. The **Stage 0 validation harness is implemented**: the deterministic core
(`validate_field`), the five outputs, the audit chain, example extractor adapters, a batch helper,
and a CLI — all offline, with a test asserting the core makes no network calls. See
[SKILL.md](SKILL.md) for the build plan, [docs/design/notevahti.md](docs/design/notevahti.md) for the
design, and [docs/design/pathway.md](docs/design/pathway.md) for the research → validated-tool
pathway. Stage 1 (does the validity flag predict real abstraction errors?) is a study, not code.

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

record.provenance.status        # SPAN_FOUND  (the value is verifiably in the note)
record.independence.status      # SATISFIED   (the anchor's lineage is disjoint)
record.validity.flag_for_human_review  # False
record.to_dict()                # JSON-serializable full record
```

A value that is not in the note is flagged as a likely hallucination; an anchor that shares lineage
with the value is refused as circular. Run a batch from the command line:

```
notevahti validate items.json --field-type staging --audit audit.jsonl
```

where `items.json` is a JSON array of field inputs (see `tests/fixtures/synthetic_mdt.json` and
`tests/test_cli.py` for the shape).

## Development

```
pip install -e ".[dev]"   # core has no runtime dependencies
pytest                    # 56 tests; deterministic, offline
```

## Boundary

NoteVahti is **not a medical device** and **not clinical advice**. It provides *validation evidence*
for human review; it does **not** guarantee the correctness of any value. Whether the validity score
predicts true abstraction errors is an open empirical question to be answered by validation studies,
not asserted.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
