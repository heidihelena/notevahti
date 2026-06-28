"""Stage-1 evidence pack and preregistration skeleton."""

import pytest

from notevahti.analytics.evidence_pack import (
    Observation,
    build_evidence_pack,
    default_heuristic_card,
    to_markdown,
)
from notevahti.analytics.preregistration import PreregSpec, preregistration_markdown


def _obs(error: bool, flagged: bool, score: float, **subgroups: str) -> Observation:
    return Observation(error=error, flagged=flagged, validity_score=score, subgroups=subgroups)


def _sample() -> list[Observation]:
    # perfectly-precise flag (everything flagged is an error), two languages
    return [
        _obs(True, True, 0.10, language="fi", field="stage"),
        _obs(True, True, 0.10, language="en", field="stage"),
        _obs(False, False, 0.90, language="fi", field="stage"),
        _obs(False, False, 0.90, language="en", field="histology"),
        _obs(False, False, 0.85, language="fi", field="histology"),
        _obs(False, False, 0.88, language="en", field="histology"),
    ]


def test_pack_overall_metrics():
    pack = build_evidence_pack(
        _sample(),
        subgroup_dims=("language", "field"),
        deployment_prevalence=0.05,
        seed=1,
        bootstrap=200,
    )
    assert pack.n == 6
    assert pack.n_errors == 2
    assert pack.error_prevalence == pytest.approx(0.3333, abs=1e-3)
    assert pack.overall_flag.specificity == 1.0
    assert pack.overall_flag.sensitivity == 1.0
    # perfectly separating validity score -> AUROC 1.0
    assert pack.overall_score.auroc == 1.0


def test_subgroups_present_and_summed():
    pack = build_evidence_pack(_sample(), subgroup_dims=("language",), seed=1, bootstrap=100)
    langs = {s.value: s for s in pack.subgroups if s.dimension == "language"}
    assert set(langs) == {"fi", "en"}
    assert sum(s.n for s in pack.subgroups if s.dimension == "language") == 6


def test_heuristic_card_is_pinned_and_hashed():
    card = default_heuristic_card()
    assert card.notevahti_version
    assert len(card.config_hash) == 64  # sha256 hex
    assert "span_presence" in card.validity_weights
    # deterministic
    assert default_heuristic_card().config_hash == card.config_hash


def test_markdown_has_machine_and_human_sections():
    md = to_markdown(
        build_evidence_pack(_sample(), subgroup_dims=("language",), seed=1, bootstrap=50)
    )
    assert "Discrimination (overall)" in md
    assert "Discrimination (subgroups)" in md
    assert "Narrative (human) — required, not generated" in md
    assert "config hash" in md


def test_empty_raises():
    with pytest.raises(ValueError):
        build_evidence_pack([])


def test_preregistration_markdown_defaults():
    md = preregistration_markdown()
    assert "Preregistration" in md
    assert "BEFORE unblinding" in md
    assert "Kill / scale criterion" in md
    assert "independence" in md.lower()
    # frozen threshold surfaced
    assert "0.8" in md


def test_preregistration_spec_override():
    md = preregistration_markdown(PreregSpec(title="My study", frozen_config_threshold=0.75))
    assert "My study" in md
    assert "0.75" in md
