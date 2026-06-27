"""Independence: refuse to let a source validate itself.

The failure mode this prevents is *shared-reference bias* — an extractor graded against a reference
that is not truly independent of it looks excellent and is wrong (agreement is not validity). A
validation signal (anchor) counts only if its declared lineage is disjoint from the value-under-test.
NoteVahti does not infer independence; the caller declares lineage and NoteVahti enforces it.

Outcomes:
- SATISFIED  — at least one anchor has lineage disjoint from the value (shared anchors are excluded,
               not fatal).
- VIOLATED   — anchors were supplied and *every* one shares lineage with the value (circular).
- UNKNOWN    — no anchors, or no confirmable independent anchor because lineage is undeclared.
"""

from __future__ import annotations

from typing import Iterable

from .types import Independence, IndependenceStatus, Lineage, Signal


def _classify(value_lineage: Lineage, anchor: Signal) -> str:
    if value_lineage.is_empty() or anchor.lineage.is_empty():
        return "unknown"
    if value_lineage.shares_with(anchor.lineage) is not None:
        return "shared"
    return "independent"


def check_independence(value_lineage: Lineage, anchors: Iterable[Signal]) -> Independence:
    anchors = list(anchors)
    considered = len(anchors)
    classes = [_classify(value_lineage, a) for a in anchors]
    independent = classes.count("independent")
    shared = classes.count("shared")
    unknown = classes.count("unknown")

    if independent >= 1:
        reason = f"{independent} independent anchor(s)"
        if shared:
            reason += f"; {shared} shared anchor(s) excluded as circular"
        if unknown:
            reason += f"; {unknown} anchor(s) of undeclared lineage ignored"
        status = IndependenceStatus.SATISFIED
    elif considered == 0:
        status = IndependenceStatus.UNKNOWN
        reason = "no anchors provided; no independent validation signal"
    elif shared >= 1 and unknown == 0:
        status = IndependenceStatus.VIOLATED
        reason = "every anchor shares lineage with the value under test (circular validation)"
    else:
        status = IndependenceStatus.UNKNOWN
        reason = "no confirmable independent anchor (lineage undeclared)"

    return Independence(
        status=status,
        reason=reason,
        anchors_considered=considered,
        independent_anchors=independent,
    )
