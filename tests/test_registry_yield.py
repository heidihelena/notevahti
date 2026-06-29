"""Registry-ready yield analytics."""

from notevahti.analytics.registry_yield import is_registry_ready, registry_ready_yield
from notevahti.types import (
    Agreement,
    AgreementStatus,
    FieldSpec,
    FieldType,
    Independence,
    IndependenceStatus,
    MatchKind,
    Provenance,
    ProvenanceStatus,
    ValidationRecord,
    Validity,
)


def _rec(
    *,
    no_span: bool = False,
    flagged: bool = False,
    score: float = 0.95,
    independence: IndependenceStatus = IndependenceStatus.SATISFIED,
) -> ValidationRecord:
    if no_span:
        prov = Provenance(
            status=ProvenanceStatus.NO_SPAN_FOUND,
            claimed_span=None,
            matched_span=None,
            matched_text=None,
            match_kind=MatchKind.NONE,
            hallucination_flag=True,
        )
    else:
        prov = Provenance(
            status=ProvenanceStatus.SPAN_FOUND,
            claimed_span=(0, 1),
            matched_span=(0, 1),
            matched_text="x",
            match_kind=MatchKind.EXACT,
            hallucination_flag=False,
        )
    return ValidationRecord(
        value="x",
        field=FieldSpec(name="f", field_type=FieldType.CATEGORICAL),
        provenance=prov,
        validity=Validity(score=score, flag_for_human_review=flagged, threshold=0.8),
        agreement=Agreement(status=AgreementStatus.AVAILABLE),
        independence=Independence(status=independence, reason=""),
    )


def test_perfect_record_is_registry_ready():
    r = registry_ready_yield([_rec()])
    assert r.n_total == 1 and r.n_registry_ready == 1
    assert r.registry_ready_yield == 1.0


def test_no_span_is_not_ready():
    r = registry_ready_yield([_rec(), _rec(no_span=True, flagged=True, score=0.1)])
    assert r.n_registry_ready == 1 and r.n_no_span == 1
    assert r.registry_ready_yield == 0.5


def test_flagged_is_not_ready():
    r = registry_ready_yield([_rec(flagged=True, score=0.95)])
    assert r.n_registry_ready == 0 and r.n_flagged == 1
    assert r.registry_ready_yield == 0.0


def test_blocked_route_is_not_ready():
    # independence violated -> routed to blocked -> not registry-ready
    r = registry_ready_yield([_rec(independence=IndependenceStatus.VIOLATED)])
    assert r.n_blocked == 1 and r.n_registry_ready == 0


def test_threshold_changes_yield_deterministically():
    rec = _rec(score=0.75)
    assert registry_ready_yield([rec], min_score=0.70).registry_ready_yield == 1.0
    below = registry_ready_yield([rec], min_score=0.80)
    assert below.registry_ready_yield == 0.0 and below.n_below_threshold == 1


def test_empty_is_zero():
    r = registry_ready_yield([])
    assert r.n_total == 0 and r.registry_ready_yield == 0.0


def test_is_registry_ready_matches_aggregate():
    # The single-record predicate must agree with the aggregate's headline count, since both
    # share one definition of "registry-ready".
    cases = [
        _rec(),
        _rec(no_span=True),
        _rec(flagged=True),
        _rec(score=0.5),
        _rec(independence=IndependenceStatus.VIOLATED),
    ]
    for rec in cases:
        ready = is_registry_ready(rec)
        assert ready == (registry_ready_yield([rec]).n_registry_ready == 1)
    assert is_registry_ready(_rec()) is True
    assert is_registry_ready(_rec(no_span=True)) is False


def test_is_registry_ready_respects_threshold():
    rec = _rec(score=0.75)
    assert is_registry_ready(rec, min_score=0.70) is True
    assert is_registry_ready(rec, min_score=0.80) is False
