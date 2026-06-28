"""Batch validation and proper (batch-level) agreement.

``validate_field`` handles one field; κ is only meaningful across many. ``validate_batch`` runs a
sequence of field inputs (optionally sharing one audit log) and, where references are supplied,
reports agreement **grouped by (field_name, field_type)**. Pooling κ across different fields is
incorrect (a staging κ and a date κ are not comparable and must not be averaged into one number), so
the top-level ``agreement`` is reported only when every referenced item belongs to a single group;
otherwise it is ``not_available`` and the per-group results are in ``agreements_by_field``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .agreement import agreement as _agreement
from .audit import AuditLog
from .types import Agreement, AgreementStatus, FieldType, ValidationRecord
from .validate import validate_field


@dataclass(frozen=True)
class BatchResult:
    records: list[ValidationRecord]
    agreement: Agreement  # single-group agreement, or not_available when fields are mixed
    agreements_by_field: dict[str, Agreement] = field(default_factory=dict)

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
    ``field_type`` here is only the default for items that do not set their own. Agreement is
    computed **per (field_name, field_type) group** using that group's own field type, never pooled
    across fields. The shared ``audit_log`` chains all entries together.
    """
    field_type = FieldType(field_type)
    records: list[ValidationRecord] = []
    # (field_name, field_type) -> (predicted, reference) lists
    groups: dict[tuple[str, FieldType], tuple[list[str], list[str]]] = {}

    for item in items:
        item = dict(item)
        item["field_type"] = FieldType(item.get("field_type", field_type))
        if audit_log is not None:
            item["audit_log"] = audit_log
        reference = item.get("reference")
        rec = validate_field(**item)
        records.append(rec)
        if reference is not None:
            key = (rec.field.name, rec.field.field_type)
            preds, refs = groups.setdefault(key, ([], []))
            preds.append(rec.value)
            refs.append(reference)

    agreements_by_field: dict[str, Agreement] = {
        f"{name}:{ftype.value}": _agreement(preds, refs, ftype)
        for (name, ftype), (preds, refs) in groups.items()
    }

    if not groups:
        agreement = Agreement(status=AgreementStatus.NOT_AVAILABLE, detail="no references supplied")
    elif len(groups) == 1:
        agreement = next(iter(agreements_by_field.values()))
    else:
        agreement = Agreement(
            status=AgreementStatus.NOT_AVAILABLE,
            detail=(
                f"agreement not pooled across {len(groups)} field groups "
                f"({', '.join(sorted(agreements_by_field))}); see agreements_by_field"
            ),
        )

    return BatchResult(
        records=records, agreement=agreement, agreements_by_field=agreements_by_field
    )
