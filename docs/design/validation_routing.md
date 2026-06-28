# Validation routing (trigger-gated) — design note

Status: implemented (`notevahti.routing`), 2026-06. An **optional** layer on top of the five
`ValidationRecord` outputs. It does not change `validate_field`.

## What it is

```
extractor output → validate_field() → ValidationRecord → route_validation() → ReviewRoute
```

`route_validation(record, *, field_impact=...)` reads a finished `ValidationRecord` and returns a
`ReviewRoute`: a single auditable **route** plus the triggers and rationale behind it. It answers a
question the record itself does not — *given this evidence, what should happen before a human trusts
the value?* — by integrating several signals rather than thresholding one score.

It is deterministic and pure (a function of the record + a declared `field_impact`), model-free, and
offline, like the rest of the validation layer.

## What the words mean (read this before using)

The routes are **validation routes, not truth labels**. There is deliberately no
`correct`/`incorrect`, no `true`/`false`, no diagnosis.

| route | meaning |
|---|---|
| `accept` | no trigger fired; routine path. **Not** a claim the value is correct — only that nothing demanded attention. |
| `review` | ≥1 trigger fired; a human should review before trusting it. |
| `specialist_review` | a high-impact field with ≥2 triggers; route to a domain specialist. |
| `blocked` | a *blocking* failure (no supporting span, or circular validation); must not be auto-accepted, needs human adjudication. |

`blocked` is **advice to the pipeline, not enforcement** — NoteVahti does not control the registry —
and it is **not a verdict that the value is wrong**. It means the evidence cannot support
auto-acceptance. This framing keeps routing inside the research/quality intended purpose (it does not
make a diagnostic or therapeutic recommendation).

## Triggers (validation triggers, not clinical triggers)

Derived only from signals already in the record, plus the declared field impact:

| trigger | source | blocking? |
|---|---|---|
| `no_source_span_found` | `provenance.hallucination_flag` | yes (`source_span_missing`) |
| `independence_violated` | `independence.status == violated` | yes (`circular_validation`) |
| `independence_unknown` | `independence.status == unknown` | no |
| `low_validity_score` | `validity.flag_for_human_review` (incl. a disagreeing independent anchor) | no |
| `agreement_not_available` | `agreement.status == not_available` | no |
| `high_impact_field` | caller declares `field_impact="high"` | no |

The two **blocking** triggers map straight to the README's non-negotiables: a value with no
supporting span is a likely hallucination, and an anchor that shares lineage with the value is
circular and refused. Routing surfaces these as hard stops.

### Deliberately deferred (need data the record does not carry)

- `numeric_outlier` — needs a reference distribution/range (domain data + a statistical claim).
- `conflicting_anchor` as a *distinct* trigger — a disagreeing independent anchor already forces
  `validity.flag_for_human_review`, so it currently surfaces as `low_validity_score`; a separate
  trigger waits until the record exposes anchor agreement explicitly.

## The "integral" property

The route is not a function of the validity score alone: the same score can route differently.

```
validity 0.76, span found, independent anchor present, low-impact field   → review
validity 0.76, no span, staging field, independence violated              → blocked
```

This is the intended contribution: **same validity score ≠ same decision**, made explicit and
auditable.

## ReviewRoute

```python
@dataclass(frozen=True)
class ReviewRoute:
    route: str                 # one of routing.ROUTES
    active_triggers: list[str]
    blocking_flags: list[str]
    validity_score: float      # carried through; uncalibrated heuristic, NOT a probability
    trigger_count: int
    blocking_count: int
    rationale: list[str]       # human-readable reasons — what makes the route auditable
```

Naming was chosen to avoid overclaiming: `validity_score` (not "confidence", which would imply a
calibrated probability); integer counts (not "burden" magnitudes); `rationale` rather than a verdict.

## Status as policy, not validated thresholds

The routing rules (which triggers block, when high-impact escalates to specialist) are a transparent,
configurable **policy**, exactly like the validity weights — not calibrated or validated numbers.
They should be **frozen before any Stage-1 calibration**, not tuned ad hoc, and the policy is the
thing an institution reviews and adapts. Routing does not touch the validity weights, so it does not
affect the frozen-weights discipline.

## Boundaries

- Not a medical device; not clinical advice. Routes are advisory validation evidence for a human.
- `accept` ≠ correct; `blocked` ≠ wrong; no route is a diagnostic or therapeutic recommendation.
- Deterministic, offline, model-free — same record + field impact → same route.

## Follow-ups (not in this PR)

- Persist the `ReviewRoute` (route + triggers + rationale) into the audit record, so the routing
  decision is part of the tamper-evident trail.
- A configurable policy object (custom blocking sets, escalation rules, per-field impact registry).
- A `conflicting_anchor` trigger once anchor agreement is exposed on the record.
