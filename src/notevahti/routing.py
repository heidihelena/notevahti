"""Trigger-gated validation routing — an optional layer ON TOP of ``ValidationRecord``.

``validate_field`` answers "what does the evidence say about this value?". Routing answers a
different, downstream question: "given that evidence, what should happen before a human trusts it?".
It integrates the record's signals (provenance, validity, independence, agreement) plus a
caller-declared field impact into one auditable route.

Precise meaning of the route (this is the whole point -- read it before using):

- ``accept``            : no validation trigger fired; the value takes the routine path. This is NOT
                          a claim the value is correct -- only that nothing in the evidence demanded
                          attention.
- ``review``            : at least one trigger fired; a human should review before trusting it.
- ``specialist_review`` : a high-impact field with multiple triggers; route to a domain specialist.
- ``blocked``           : a *blocking* validation failure (no supporting span, or circular
                          validation) -- the value must not be auto-accepted and needs human
                          adjudication. ``blocked`` is advice to the pipeline, NOT NoteVahti
                          enforcing anything on the registry, and NOT a verdict that the value
                          is wrong.

The router is a deterministic, transparent **policy** over the record -- not a calibrated or
validated threshold, and not a clinical/diagnostic decision. Like the validity weights, the routing
rules are configurable and should be frozen before any Stage-1 calibration, not tuned ad hoc.
NoteVahti remains validation evidence for human review; routing makes the *why* explicit and
auditable.
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import AgreementStatus, IndependenceStatus, ValidationRecord

#: The four routes, from least to most constrained.
ROUTES = ("accept", "review", "specialist_review", "blocked")

#: Declared importance of the field (caller-supplied, never inferred). Only "high" changes routing.
FIELD_IMPACTS = ("low", "standard", "high")


@dataclass(frozen=True)
class ReviewRoute:
    """An auditable routing decision derived from a ``ValidationRecord``.

    Counts are integers (they count triggers, not a magnitude). ``validity_score`` is carried
    through unchanged -- an uncalibrated heuristic, not a probability. ``rationale`` is
    human-readable and is what makes the route auditable.
    """

    route: str
    active_triggers: list[str]
    blocking_flags: list[str]
    validity_score: float
    trigger_count: int
    blocking_count: int
    rationale: list[str]

    def to_dict(self) -> dict[str, object]:
        """JSON-serializable view (e.g. to record the route in the audit trail)."""
        return {
            "route": self.route,
            "active_triggers": list(self.active_triggers),
            "blocking_flags": list(self.blocking_flags),
            "validity_score": self.validity_score,
            "trigger_count": self.trigger_count,
            "blocking_count": self.blocking_count,
            "rationale": list(self.rationale),
        }


def _rationale(record: ValidationRecord, triggers: list[str], field_impact: str) -> list[str]:
    lines: list[str] = []
    v = record.validity
    for t in triggers:
        if t == "no_source_span_found":
            lines.append(
                "no source span supports the value (possible hallucination); not auto-acceptable"
            )
        elif t == "independence_violated":
            lines.append(
                "validation was circular (an anchor shares lineage with the value); "
                "independent corroboration is required"
            )
        elif t == "independence_unknown":
            lines.append(
                "no independent corroboration available (anchor lineage undeclared or no anchor)"
            )
        elif t == "low_validity_score":
            lines.append(
                f"validity score {v.score} is below the review threshold {v.threshold} "
                "(or a disagreeing independent anchor forced review)"
            )
        elif t == "agreement_not_available":
            lines.append("no reference set, so agreement (kappa/accuracy) could not be computed")
        elif t == "high_impact_field":
            lines.append("field declared high-impact; routine human review applies")
    return lines


def route_validation(
    record: ValidationRecord,
    *,
    field_impact: str = "standard",
) -> ReviewRoute:
    """Route a validation record to ``accept`` / ``review`` / ``specialist_review`` / ``blocked``.

    Deterministic and pure: the route is a function of the record and the declared ``field_impact``
    (one of :data:`FIELD_IMPACTS`). Only ``"high"`` affects routing; a high-impact field is always
    routed to at least ``review`` (a deliberate, configurable policy -- high-impact fields get a
    human look even when the evidence is clean).
    """
    if field_impact not in FIELD_IMPACTS:
        raise ValueError(f"field_impact must be one of {FIELD_IMPACTS}, got {field_impact!r}")

    triggers: list[str] = []
    blocking: list[str] = []

    if record.provenance.hallucination_flag:
        triggers.append("no_source_span_found")
        blocking.append("source_span_missing")

    if record.independence.status is IndependenceStatus.VIOLATED:
        triggers.append("independence_violated")
        blocking.append("circular_validation")
    elif record.independence.status is IndependenceStatus.UNKNOWN:
        triggers.append("independence_unknown")

    if record.validity.flag_for_human_review:
        triggers.append("low_validity_score")

    if record.agreement.status is AgreementStatus.NOT_AVAILABLE:
        triggers.append("agreement_not_available")

    if field_impact == "high":
        triggers.append("high_impact_field")

    if blocking:
        route = "blocked"
    elif field_impact == "high" and len(triggers) >= 2:
        route = "specialist_review"
    elif triggers:
        route = "review"
    else:
        route = "accept"

    rationale = _rationale(record, triggers, field_impact)
    rationale.append(
        f"route={route} (advisory; a human decides — not a correctness or device claim)"
    )

    return ReviewRoute(
        route=route,
        active_triggers=triggers,
        blocking_flags=blocking,
        validity_score=record.validity.score,
        trigger_count=len(triggers),
        blocking_count=len(blocking),
        rationale=rationale,
    )
