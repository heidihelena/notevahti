"""Batch validation and proper (batch-level) agreement.

``validate_field`` handles one field; κ is only meaningful across many. ``validate_batch`` runs a
sequence of field inputs (optionally sharing one audit log) and, where references are supplied,
reports a single batch-level :class:`Agreement`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .agreement import agreement as _agreement
from .audit import AuditLog
from .types import Agreement, AgreementStatus, FieldType, ValidationRecord
from .validate import validate_field


@dataclass(frozen=True)
class BatchResult:
    records: list[ValidationRecord]
    agreement: Agreement  # over the items that supplied a reference

    def flagged(self) -> list[ValidationRecord]:
        return [r for r in self.records if r.validity.flag_for_human_review]


def validate_batch(
    items: Sequence[dict[str, Any]],
    *,
    field_type: FieldType = FieldType.TEXT,
    audit_log: AuditLog | None = None,
) -> BatchResult:
    """Validate many field inputs.

    Each item is a kwargs dict for :func:`validate_field` (``value`` and ``note`` required). The
    ``field_type`` here is the default and the type used for the batch agreement; items may override
    their own ``field_type``. The shared ``audit_log`` chains all entries together.
    """
    field_type = FieldType(field_type)
    records: list[ValidationRecord] = []
    preds: list[str] = []
    refs: list[str] = []

    for item in items:
        item = dict(item)
        item["field_type"] = FieldType(item.get("field_type", field_type))
        if audit_log is not None:
            item["audit_log"] = audit_log
        reference = item.get("reference")
        rec = validate_field(**item)
        records.append(rec)
        if reference is not None:
            preds.append(rec.value)
            refs.append(reference)

    if refs:
        agreement = _agreement(preds, refs, field_type)
    else:
        agreement = Agreement(status=AgreementStatus.NOT_AVAILABLE, detail="no references supplied")

    return BatchResult(records=records, agreement=agreement)
