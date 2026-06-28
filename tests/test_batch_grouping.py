"""Batch agreement must be grouped by (field_name, field_type), never pooled across fields."""

from notevahti.batch import validate_batch
from notevahti.types import AgreementStatus


def test_mixed_fields_are_not_pooled():
    items = [
        {
            "value": "cT2a N0 M0",
            "note": "stage cT2a N0 M0",
            "field_type": "staging",
            "field_name": "clinical_stage",
            "reference": "cT2aN0M0",
        },
        {
            "value": "adenocarcinoma",
            "note": "biopsy: adenocarcinoma",
            "field_type": "categorical",
            "field_name": "histology",
            "reference": "adenocarcinoma",
        },
    ]
    res = validate_batch(items)
    # No single pooled kappa across different fields.
    assert res.agreement.status is AgreementStatus.NOT_AVAILABLE
    assert "agreements_by_field" in res.agreement.detail
    assert set(res.agreements_by_field) == {"clinical_stage:staging", "histology:categorical"}
    assert res.agreements_by_field["clinical_stage:staging"].status is AgreementStatus.AVAILABLE
    assert res.agreements_by_field["histology:categorical"].accuracy == 1.0


def test_single_field_group_is_reported_at_top_level():
    items = [
        {
            "value": "cT2a N0 M0",
            "note": "x cT2a N0 M0 y",
            "field_type": "staging",
            "field_name": "clinical_stage",
            "reference": "cT2aN0M0",
        }
        for _ in range(3)
    ]
    res = validate_batch(items)
    assert res.agreement.status is AgreementStatus.AVAILABLE
    # staging uses compact normalisation, so spaced value agrees with compact reference
    assert res.agreement.accuracy == 1.0
    assert set(res.agreements_by_field) == {"clinical_stage:staging"}


def test_group_uses_its_own_field_type_not_batch_default():
    # batch default is text, but the staging group must normalise as staging (else it would disagree)
    items = [
        {
            "value": "cT2a N0 M0",
            "note": "n cT2a N0 M0",
            "field_type": "staging",
            "field_name": "stage",
            "reference": "cT2aN0M0",
        }
    ]
    res = validate_batch(items)  # field_type default = text
    assert res.agreements_by_field["stage:staging"].accuracy == 1.0
