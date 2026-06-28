"""Property-based tests (Hypothesis) for the core normalisation contract.

These pin invariants that the deterministic core promises for *all* inputs, not just the
hand-picked examples in the other test modules. They are pure and offline — they obey the
suite-wide ``--disable-socket`` guarantee like every other test.
"""

from hypothesis import given
from hypothesis import strategies as st

from notevahti.provenance import canonical_value, values_equivalent
from notevahti.types import FieldType

field_types = st.sampled_from(list(FieldType))
# Include whitespace and case so the compact/normalise rules are actually exercised.
texts = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=0x2FFF),
    max_size=40,
)


@given(s=texts, ft=field_types)
def test_canonical_value_is_idempotent(s: str, ft: FieldType) -> None:
    once = canonical_value(s, ft)
    assert canonical_value(once, ft) == once


@given(s=texts, ft=field_types)
def test_values_equivalent_is_reflexive(s: str, ft: FieldType) -> None:
    assert values_equivalent(s, s, ft)


@given(a=texts, b=texts, ft=field_types)
def test_equivalence_matches_canonical_key_equality(a: str, b: str, ft: FieldType) -> None:
    # The documented contract: two values are equivalent iff their canonical keys are equal.
    assert values_equivalent(a, b, ft) == (canonical_value(a, ft) == canonical_value(b, ft))
