"""Registry-ready yield: what fraction of attempted records can enter the registry without review.

A record counts as *registry-ready* only if NoteVahti would let it through unattended: it is not
flagged for review, has an acceptable provenance span, is not routed to ``blocked``, and meets a
score threshold. This is an operational readiness number for a workflow, not a correctness claim:
a registry-ready record is one the validator did not stop, not one proven correct.

Deterministic and offline. Routing is consulted to detect ``blocked`` (default field impact).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..routing import route_validation
from ..types import ProvenanceStatus, ValidationRecord


@dataclass(frozen=True)
class RegistryYield:
    n_total: int
    n_registry_ready: int
    registry_ready_yield: float
    n_flagged: int
    n_blocked: int
    n_no_span: int
    n_below_threshold: int
    min_score: float


@dataclass(frozen=True)
class _Blockers:
    """Why a single record is not registry-ready (none set means it is)."""

    no_span: bool
    flagged: bool
    below_threshold: bool
    blocked: bool

    @property
    def any(self) -> bool:
        return self.no_span or self.flagged or self.below_threshold or self.blocked


def _blockers(record: ValidationRecord, min_score: float) -> _Blockers:
    return _Blockers(
        no_span=record.provenance.status is ProvenanceStatus.NO_SPAN_FOUND,
        flagged=record.validity.flag_for_human_review,
        below_threshold=record.validity.score < min_score,
        blocked=route_validation(record).route == "blocked",
    )


def is_registry_ready(record: ValidationRecord, min_score: float = 0.80) -> bool:
    """True if NoteVahti would let this single record into the registry unattended.

    Registry-ready means the validator did not stop it (span present, not flagged, not routed to
    ``blocked``, and at or above ``min_score``) — an operational signal, not a correctness claim.
    Shares its definition with :func:`registry_ready_yield`, which aggregates it over many records.
    """
    return not _blockers(record, min_score).any


def registry_ready_yield(
    records: Sequence[ValidationRecord], min_score: float = 0.80
) -> RegistryYield:
    """Fraction of ``records`` that are registry-ready (no review, span, not blocked, scored).

    The condition counts are diagnostic and not mutually exclusive; ``registry_ready_yield`` is the
    only headline number. An empty input yields 0.0.
    """
    n_total = len(records)
    n_ready = n_flagged = n_blocked = n_no_span = n_below = 0
    for rec in records:
        b = _blockers(rec, min_score)
        n_no_span += int(b.no_span)
        n_flagged += int(b.flagged)
        n_below += int(b.below_threshold)
        n_blocked += int(b.blocked)
        if not b.any:
            n_ready += 1
    ratio = (n_ready / n_total) if n_total else 0.0
    return RegistryYield(
        n_total=n_total,
        n_registry_ready=n_ready,
        registry_ready_yield=round(ratio, 6),
        n_flagged=n_flagged,
        n_blocked=n_blocked,
        n_no_span=n_no_span,
        n_below_threshold=n_below,
        min_score=min_score,
    )
