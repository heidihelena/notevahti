"""Trigger-gated validation routing: named regression cases and routing invariants."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from notevahti.routing import FIELD_IMPACTS, ROUTES, route_validation
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


def _record(
    *,
    hallucination: bool = False,
    independence: IndependenceStatus = IndependenceStatus.SATISFIED,
    flag: bool = False,
    agreement: AgreementStatus = AgreementStatus.AVAILABLE,
    score: float = 0.9,
    threshold: float = 0.8,
    field_type: FieldType = FieldType.CATEGORICAL,
) -> ValidationRecord:
    if hallucination:
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
        field=FieldSpec(name="f", field_type=field_type),
        provenance=prov,
        validity=Validity(score=score, flag_for_human_review=flag, threshold=threshold),
        agreement=Agreement(status=agreement),
        independence=Independence(status=independence, reason=""),
    )


# ----------------------------------------------------------------- named regression cases


def test_clean_high_score_accepts():
    r = route_validation(_record())
    assert r.route == "accept"
    assert r.active_triggers == [] and r.blocking_flags == []


def test_no_span_is_blocked():
    r = route_validation(_record(hallucination=True, flag=True, score=0.1))
    assert r.route == "blocked"
    assert "source_span_missing" in r.blocking_flags
    assert "no_source_span_found" in r.active_triggers


def test_independence_violated_is_blocked():
    r = route_validation(_record(independence=IndependenceStatus.VIOLATED))
    assert r.route == "blocked"
    assert "circular_validation" in r.blocking_flags


def test_low_validity_only_is_review():
    r = route_validation(_record(flag=True, score=0.7))
    assert r.route == "review"
    assert r.active_triggers == ["low_validity_score"]
    assert r.blocking_flags == []


def test_high_impact_staging_low_validity_no_agreement_is_specialist():
    r = route_validation(
        _record(
            flag=True,
            score=0.7,
            agreement=AgreementStatus.NOT_AVAILABLE,
            field_type=FieldType.STAGING,
        ),
        field_impact="high",
    )
    assert r.route == "specialist_review"
    assert {"low_validity_score", "agreement_not_available", "high_impact_field"} <= set(
        r.active_triggers
    )


def test_agreement_missing_alone_is_review_not_blocked():
    r = route_validation(_record(agreement=AgreementStatus.NOT_AVAILABLE))
    assert r.route == "review"
    assert r.blocking_flags == []
    assert r.active_triggers == ["agreement_not_available"]


def test_independence_unknown_is_review_not_blocked():
    r = route_validation(_record(independence=IndependenceStatus.UNKNOWN))
    assert r.route == "review"
    assert "independence_unknown" in r.active_triggers
    assert r.blocking_flags == []


def test_rationale_present_and_route_is_advisory():
    r = route_validation(_record(hallucination=True, flag=True, score=0.1))
    assert r.rationale
    assert any("advisory" in line for line in r.rationale)


def test_invalid_field_impact_raises():
    with pytest.raises(ValueError):
        route_validation(_record(), field_impact="critical")


# ----------------------------------------------------------------- invariants (property-based)

_STATUS = st.sampled_from(list(IndependenceStatus))
_AGREE = st.sampled_from(list(AgreementStatus))
_IMPACT = st.sampled_from(list(FIELD_IMPACTS))


@given(hall=st.booleans(), indep=_STATUS, flag=st.booleans(), agree=_AGREE, impact=_IMPACT)
def test_route_is_always_valid(hall, indep, flag, agree, impact):
    r = route_validation(
        _record(hallucination=hall, independence=indep, flag=flag, agreement=agree),
        field_impact=impact,
    )
    assert r.route in ROUTES
    assert r.trigger_count == len(r.active_triggers)
    assert r.blocking_count == len(r.blocking_flags)


@given(hall=st.booleans(), indep=_STATUS, flag=st.booleans(), agree=_AGREE, impact=_IMPACT)
def test_blocked_iff_blocking_flags(hall, indep, flag, agree, impact):
    r = route_validation(
        _record(hallucination=hall, independence=indep, flag=flag, agreement=agree),
        field_impact=impact,
    )
    assert (r.route == "blocked") == (r.blocking_count > 0)


@given(indep=_STATUS, flag=st.booleans(), agree=_AGREE, impact=_IMPACT)
def test_hallucination_always_blocks(indep, flag, agree, impact):
    r = route_validation(
        _record(hallucination=True, independence=indep, flag=flag, agreement=agree),
        field_impact=impact,
    )
    assert r.route == "blocked"


@given(impact=st.sampled_from(["low", "standard"]))
def test_fully_clean_standard_accepts(impact):
    r = route_validation(_record(), field_impact=impact)
    assert r.route == "accept"


@given(hall=st.booleans(), indep=_STATUS, flag=st.booleans(), agree=_AGREE, impact=_IMPACT)
def test_deterministic(hall, indep, flag, agree, impact):
    rec = _record(hallucination=hall, independence=indep, flag=flag, agreement=agree)
    assert route_validation(rec, field_impact=impact) == route_validation(rec, field_impact=impact)
