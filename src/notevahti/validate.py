"""The orchestrator: ``validate_field`` wires the five outputs into one ValidationRecord.

This is the contract. Everything above it (batch, CLI) is convenience. The function is
deterministic: all non-determinism (record id, timestamp, actor) is supplied by the caller, and the
audit log is the only thing that touches disk.
"""

from __future__ import annotations

from collections.abc import Iterable

from . import __version__
from .agreement import agreement as _agreement
from .audit import GENESIS_HASH, AuditLog, audit_payload, make_entry
from .independence import check_independence
from .provenance import verify_span
from .types import (
    Agreement,
    AgreementStatus,
    FieldSpec,
    FieldType,
    Lineage,
    Signal,
    ValidationRecord,
)
from .validity import DEFAULT_THRESHOLD, score_validity


def validate_field(
    value: str,
    note: str,
    *,
    claimed_span: tuple[int, int] | None = None,
    field: FieldSpec | None = None,
    field_type: FieldType = FieldType.TEXT,
    field_name: str = "field",
    value_lineage: Lineage = Lineage(),
    anchors: Iterable[Signal] | None = None,
    reference: str | None = None,
    review_threshold: float = DEFAULT_THRESHOLD,
    weights: dict[str, float] | None = None,
    # audit (optional; all deterministic inputs supplied by the caller)
    audit_log: AuditLog | None = None,
    record_id: str | None = None,
    timestamp: str | None = None,
    actor: str | None = None,
    retain_text: bool = False,
) -> ValidationRecord:
    """Validate one extracted field value against its source note.

    A single ``reference`` value yields a degenerate (n=1) agreement; for meaningful κ supply a
    reference *set* via :func:`notevahti.batch.validate_batch`.
    """
    # Coerce field_type to the enum so callers may pass a plain string (e.g. from JSON/CLI).
    field_type = FieldType(field_type)
    if field is None:
        field = FieldSpec(name=field_name, field_type=field_type)
    else:
        field = FieldSpec(field.name, FieldType(field.field_type), field.allowed_values)
    ftype = field.field_type
    anchor_list = list(anchors or [])

    provenance = verify_span(value, note, claimed_span=claimed_span, field_type=ftype)
    independence = check_independence(value_lineage, anchor_list)
    validity = score_validity(
        value,
        value_lineage,
        provenance,
        anchor_list,
        independence,
        field_type=ftype,
        weights=weights,
        threshold=review_threshold,
    )
    if reference is None:
        agreement = Agreement(status=AgreementStatus.NOT_AVAILABLE, detail="no reference supplied")
    else:
        agreement = _agreement([value], [reference], ftype)
        agreement = Agreement(
            status=agreement.status,
            n=agreement.n,
            accuracy=agreement.accuracy,
            kappa=None,  # κ is not meaningful for a single pair
            detail="single-item reference (n=1); use validate_batch for kappa",
        )

    record = ValidationRecord(
        value=value,
        field=field,
        provenance=provenance,
        validity=validity,
        agreement=agreement,
        independence=independence,
        audit=None,
        notevahti_version=__version__,
    )

    # Audit: persist to the log if given, else attach a standalone (un-persisted) entry if the
    # caller supplied id/timestamp/actor. No audit at all otherwise.
    if record_id is not None and timestamp is not None and actor is not None:
        payload = audit_payload(record, note=note, retain_text=retain_text)
        if audit_log is not None:
            entry = audit_log.append(record_id, timestamp, actor, payload)
        else:
            entry = make_entry(record_id, timestamp, actor, GENESIS_HASH, payload)
        record = ValidationRecord(
            value=record.value,
            field=record.field,
            provenance=record.provenance,
            validity=record.validity,
            agreement=record.agreement,
            independence=record.independence,
            audit=entry,
            notevahti_version=record.notevahti_version,
        )

    return record
