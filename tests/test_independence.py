"""Step 3: the independent-anchor rule (non-circular validation)."""

from notevahti.independence import check_independence
from notevahti.types import IndependenceStatus, Lineage, Signal, SignalKind

VALUE_LINEAGE = Lineage(source_id="note_417", model_id="regex_v1")


def _anchor(lineage: Lineage) -> Signal:
    return Signal(value="cT2aN0M0", lineage=lineage, kind=SignalKind.OTHER)


def test_independent_human_anchor_satisfies():
    r = check_independence(VALUE_LINEAGE, [_anchor(Lineage(human_id="abstractor_B"))])
    assert r.status is IndependenceStatus.SATISFIED
    assert r.independent_anchors == 1


def test_self_validation_is_violated():
    # anchor produced by the same model -> circular
    r = check_independence(VALUE_LINEAGE, [_anchor(Lineage(model_id="regex_v1"))])
    assert r.status is IndependenceStatus.VIOLATED
    assert r.independent_anchors == 0


def test_shared_source_is_violated():
    r = check_independence(VALUE_LINEAGE, [_anchor(Lineage(source_id="note_417"))])
    assert r.status is IndependenceStatus.VIOLATED


def test_no_anchors_is_unknown():
    r = check_independence(VALUE_LINEAGE, [])
    assert r.status is IndependenceStatus.UNKNOWN
    assert r.anchors_considered == 0


def test_undeclared_lineage_is_unknown():
    r = check_independence(VALUE_LINEAGE, [_anchor(Lineage())])
    assert r.status is IndependenceStatus.UNKNOWN


def test_value_lineage_undeclared_is_unknown():
    r = check_independence(Lineage(), [_anchor(Lineage(human_id="B"))])
    assert r.status is IndependenceStatus.UNKNOWN


def test_one_independent_among_shared_satisfies_and_excludes():
    anchors = [_anchor(Lineage(model_id="regex_v1")), _anchor(Lineage(human_id="B"))]
    r = check_independence(VALUE_LINEAGE, anchors)
    assert r.status is IndependenceStatus.SATISFIED
    assert r.independent_anchors == 1
    assert "excluded" in r.reason
