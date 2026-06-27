"""Agreement vs a reference (gold) set: standard, deterministic κ and accuracy.

This is the only output that needs more than a single field. When a reference set is supplied,
NoteVahti reports Cohen's κ and accuracy over the aligned values; when it is not, it reports
``not_available`` rather than fabricating a number. Agreement is reported *because the design forbids
treating it as validity on its own* — it is one signal among the five, meaningful only alongside the
independence check.

Note: κ and accuracy here are standard statistics, not a NoteVahti contribution. Per-class F1 is
deferred to a later step.
"""

from __future__ import annotations

from collections import Counter
from typing import Sequence

from .provenance import canonical_value
from .types import Agreement, AgreementStatus, FieldType


def agreement(
    predicted: Sequence[str],
    reference: Sequence[str] | None,
    field_type: FieldType = FieldType.TEXT,
) -> Agreement:
    """Cohen's κ and accuracy of ``predicted`` against ``reference``.

    Values are compared by their canonical key for the field type, so agreement uses the same
    normalisation as provenance and validity.
    """
    if reference is None or len(reference) == 0:
        return Agreement(status=AgreementStatus.NOT_AVAILABLE, detail="no reference supplied")
    if len(predicted) != len(reference):
        raise ValueError(
            f"predicted ({len(predicted)}) and reference ({len(reference)}) lengths differ"
        )

    pred = [canonical_value(p, field_type) for p in predicted]
    ref = [canonical_value(r, field_type) for r in reference]
    n = len(pred)

    matches = sum(1 for p, r in zip(pred, ref) if p == r)
    po = matches / n  # observed agreement == accuracy

    # Cohen's kappa: chance agreement from the marginal category distributions.
    pred_counts = Counter(pred)
    ref_counts = Counter(ref)
    categories = set(pred_counts) | set(ref_counts)
    pe = sum((pred_counts[c] / n) * (ref_counts[c] / n) for c in categories)

    if abs(1.0 - pe) < 1e-12:
        # Degenerate: a single category dominates both marginals; kappa is undefined.
        kappa = 1.0 if po >= 1.0 - 1e-12 else 0.0
        detail = f"n={n}; single-category marginals (kappa degenerate); categories={len(categories)}"
    else:
        kappa = (po - pe) / (1.0 - pe)
        detail = f"n={n}; categories={len(categories)}; pe={pe:.4f}"

    return Agreement(
        status=AgreementStatus.AVAILABLE,
        n=n,
        accuracy=round(po, 4),
        kappa=round(kappa, 4),
        detail=detail,
    )
