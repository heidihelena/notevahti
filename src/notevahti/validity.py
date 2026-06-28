"""Validity: a transparent, rule-based trustworthiness heuristic — NOT a guaranteed error rate.

The research pass refuted distribution-free coverage guarantees for clinical extraction, and found
miscalibration direction reverses across field types. So the validity score is a documented,
inspectable weighted rule whose weights you can see and change; whether it predicts true abstraction
errors is an open question to be answered by a validation study, not asserted here.

The score's job is to drive ONE decision: ``flag_for_human_review``. Components, in [0, 1]:

- span_presence    : is the value supported by a span at all? (a missing span is near-fatal)
- span_quality     : exactness of the match, penalised if the extractor's claimed offsets were wrong
- independence     : was the validation non-circular? (satisfied / unknown / violated)
- anchor_agreement : do the *independent* anchors agree with the value? (neutral if none)
"""

from __future__ import annotations

from collections.abc import Iterable

from .provenance import values_equivalent
from .types import (
    FieldType,
    Independence,
    IndependenceStatus,
    Lineage,
    MatchKind,
    Provenance,
    ProvenanceStatus,
    Signal,
    Validity,
)

DEFAULT_WEIGHTS: dict[str, float] = {
    "span_presence": 0.45,
    "span_quality": 0.20,
    "independence": 0.15,
    "anchor_agreement": 0.20,
}
DEFAULT_THRESHOLD = 0.80

# A value with no supporting span cannot be trusted regardless of other signals.
_NO_SPAN_CEILING = 0.10

_INDEPENDENCE_SCORE = {
    IndependenceStatus.SATISFIED: 1.0,
    IndependenceStatus.UNKNOWN: 0.5,
    IndependenceStatus.VIOLATED: 0.0,
}


def _span_quality(prov: Provenance) -> float:
    if prov.status is ProvenanceStatus.NO_SPAN_FOUND:
        return 0.0
    base = 1.0 if prov.match_kind is MatchKind.EXACT else 0.7
    # Extractor claimed a span but the supporting text was actually elsewhere: weaker provenance.
    if prov.claimed_span is not None and prov.matched_span != prov.claimed_span:
        base *= 0.6
    return base


def _anchor_agreement(
    value: str,
    value_lineage: Lineage,
    anchors: Iterable[Signal],
    field_type: FieldType,
) -> tuple[float, int, int]:
    """Agreement over *independent* anchors only. Returns (component, agreeing, n_independent)."""
    independent = [
        a
        for a in anchors
        if not value_lineage.is_empty()
        and not a.lineage.is_empty()
        and value_lineage.shares_with(a.lineage) is None
    ]
    if not independent:
        return 0.5, 0, 0  # neutral: no independent anchor to agree or disagree
    agreeing = sum(1 for a in independent if values_equivalent(a.value, value, field_type))
    return agreeing / len(independent), agreeing, len(independent)


def score_validity(
    value: str,
    value_lineage: Lineage,
    provenance: Provenance,
    anchors: Iterable[Signal],
    independence: Independence,
    field_type: FieldType = FieldType.TEXT,
    weights: dict[str, float] | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> Validity:
    weights = weights or DEFAULT_WEIGHTS
    anchors = list(anchors)

    span_presence = 0.0 if provenance.status is ProvenanceStatus.NO_SPAN_FOUND else 1.0
    span_quality = _span_quality(provenance)
    indep = _INDEPENDENCE_SCORE[independence.status]
    agreement, agreeing, n_indep = _anchor_agreement(value, value_lineage, anchors, field_type)

    components = {
        "span_presence": span_presence,
        "span_quality": span_quality,
        "independence": indep,
        "anchor_agreement": agreement,
    }
    score = sum(weights[k] * components[k] for k in weights)

    # Hard rule: no provenance -> cannot be trusted, whatever else says.
    if provenance.status is ProvenanceStatus.NO_SPAN_FOUND:
        score = min(score, _NO_SPAN_CEILING)

    score = max(0.0, min(1.0, score))

    # Correctness rule (not mere calibration): a disagreeing independent anchor is the canonical
    # "needs human adjudication" signal, so it forces review regardless of score. Without this, a
    # wrong-but-present value with strong provenance can clear the threshold despite an independent
    # second source contradicting it.
    disagreeing_anchor = n_indep >= 1 and agreeing < n_indep
    flag = (score < threshold) or disagreeing_anchor

    detail = (
        f"span_presence={span_presence:.2f}, span_quality={span_quality:.2f}, "
        f"independence={indep:.2f} ({independence.status.value}), "
        f"anchor_agreement={agreement:.2f} ({agreeing}/{n_indep} independent)"
    )
    if disagreeing_anchor:
        detail += "; flagged: independent anchor disagrees"
    return Validity(
        score=round(score, 4),
        flag_for_human_review=flag,
        threshold=threshold,
        components={k: round(v, 4) for k, v in components.items()},
        detail=detail,
    )
