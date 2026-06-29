"""Typed model + structural validator for one synthetic Nordic lung-cancer MDT case.

stdlib-only, offline, deterministic. The controlled vocabulary below is the single source of truth
shared with the published JSON Schema (``corpus/schema/synthetic_case.schema.json``); a test asserts
the two agree, so they cannot drift. TNM vocabulary (prefix, completeness) is deliberately the same
as :func:`notevahti.extractors.rules.parse_tnm`, so a case authored here can be checked against what
the reference extractor produces without a second mapping.

A case is authored once at the *case* level (one patient, one ground truth) and may be rendered in
several documentation formats. Train/dev/test splits are assigned at the case level, never at the
rendered-variant level — otherwise the same patient leaks across splits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# --- controlled vocabulary (single source of truth, mirrored by the JSON Schema) ---------------
LANGUAGES = frozenset({"fi", "sv", "nb", "da", "is", "en"})  # Norwegian Bokmål = nb (repo-wide)
DOC_FORMATS = frozenset({"free_text", "structured_mini", "structured_v3_1"})
MESSINESS = frozenset({"clean", "semistructured", "messy"})
TNM_PREFIXES = frozenset({"c", "yc", "p", "yp", "unknown", "ambiguous"})
TNM_COMPLETENESS = frozenset({"complete", "partial", "absent", "ambiguous"})  # == parse_tnm
TREATMENT_INTENTS = frozenset({"curative", "palliative", "diagnostic", "unknown"})
SPLITS = frozenset({"train", "dev", "test"})
DIFFICULTY_TAGS = frozenset(
    {
        "explicit",
        "missing_ecog",
        "partial_tnm",
        "conflicting_tnm",
        "old_staging",
        "future_mdt",
        "negated_mdt",
        "indirect_ecog",
        "distractor_biomarkers",
        "multilingual_abbreviation",
    }
)

SOURCE_TYPE = "synthetic"  # the only allowed value: this model is for synthetic data only


@dataclass(frozen=True)
class TnmTruth:
    """Ground-truth TNM components for a case. ``None`` means the axis is not documented."""

    prefix: str  # one of TNM_PREFIXES
    t: str | None
    n: str | None
    m: str | None
    completeness: str  # one of TNM_COMPLETENESS
    edition: str = "unknown"  # 'unknown' unless the case explicitly states one (e.g. '8th')


@dataclass(frozen=True)
class CaseTruth:
    """Machine-checkable ground truth for one case."""

    mdt_discussed: bool | None  # True=documented done, False=documented not done, None=unknown
    ecog_ps: int | None  # 0..4, or None if not documented
    tnm: TnmTruth
    treatment_intent: str  # one of TREATMENT_INTENTS
    histology: str | None = None
    stage_group: str | None = None
    biomarkers: dict[str, str] | None = None
    recommendation: str | None = None


@dataclass(frozen=True)
class ExpectedField:
    """One field of the supervised target: the value, its in-note evidence, and a review flag."""

    value: Any
    evidence: str | None
    requires_review: bool


@dataclass(frozen=True)
class SyntheticCase:
    """One synthetic case: metadata, ground truth, the note, and the supervised target."""

    case_id: str
    language: str
    documentation_format: str
    messiness: str
    truth: CaseTruth
    note: str
    expected_output: dict[str, ExpectedField]
    difficulty_tags: tuple[str, ...] = ()
    split: str | None = None
    source_type: str = SOURCE_TYPE

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> SyntheticCase:
        """Build a case from a parsed-JSON dict, raising ``ValueError`` if it is not valid."""
        errors = validate_case(payload)
        if errors:
            raise ValueError("invalid synthetic case: " + "; ".join(errors))
        t = payload["truth"]
        tnm = t["tnm"]
        expected = {
            name: ExpectedField(
                value=f.get("value"),
                evidence=f.get("evidence"),
                requires_review=bool(f.get("requires_review", False)),
            )
            for name, f in payload.get("expected_output", {}).items()
        }
        return SyntheticCase(
            case_id=payload["case_id"],
            language=payload["language"],
            documentation_format=payload["documentation_format"],
            messiness=payload["messiness"],
            truth=CaseTruth(
                mdt_discussed=t.get("mdt_discussed"),
                ecog_ps=t.get("ecog_ps"),
                tnm=TnmTruth(
                    prefix=tnm["prefix"],
                    t=tnm.get("t"),
                    n=tnm.get("n"),
                    m=tnm.get("m"),
                    completeness=tnm["completeness"],
                    edition=tnm.get("edition", "unknown"),
                ),
                treatment_intent=t["treatment_intent"],
                histology=t.get("histology"),
                stage_group=t.get("stage_group"),
                biomarkers=t.get("biomarkers"),
                recommendation=t.get("recommendation"),
            ),
            note=payload["note"],
            expected_output=expected,
            difficulty_tags=tuple(payload.get("difficulty_tags", ())),
            split=payload.get("split"),
            source_type=payload.get("source_type", SOURCE_TYPE),
        )


def _enum(errors: list[str], path: str, value: Any, allowed: frozenset[str]) -> None:
    if value not in allowed:
        errors.append(f"{path}: {value!r} not in {sorted(allowed)}")


def _validate_tnm(errors: list[str], tnm: Any) -> None:
    if not isinstance(tnm, dict):
        errors.append("truth.tnm: must be an object")
        return
    if "prefix" not in tnm or "completeness" not in tnm:
        errors.append("truth.tnm: 'prefix' and 'completeness' are required")
        return
    _enum(errors, "truth.tnm.prefix", tnm["prefix"], TNM_PREFIXES)
    _enum(errors, "truth.tnm.completeness", tnm["completeness"], TNM_COMPLETENESS)
    for axis in ("t", "n", "m"):
        v = tnm.get(axis)
        if v is not None and not isinstance(v, str):
            errors.append(f"truth.tnm.{axis}: must be a string or null")
    if not isinstance(tnm.get("edition", "unknown"), str):
        errors.append("truth.tnm.edition: must be a string")


def _validate_truth(errors: list[str], truth: Any) -> None:
    if not isinstance(truth, dict):
        errors.append("truth: must be an object")
        return
    mdt = truth.get("mdt_discussed")
    if mdt is not None and not isinstance(mdt, bool):
        errors.append("truth.mdt_discussed: must be true, false, or null")
    ecog = truth.get("ecog_ps")
    if ecog is not None and not (isinstance(ecog, int) and 0 <= ecog <= 4):
        errors.append("truth.ecog_ps: must be an integer 0..4 or null")
    if "tnm" not in truth:
        errors.append("truth.tnm: required")
    else:
        _validate_tnm(errors, truth["tnm"])
    _enum(errors, "truth.treatment_intent", truth.get("treatment_intent"), TREATMENT_INTENTS)
    bm = truth.get("biomarkers")
    if bm is not None and not (
        isinstance(bm, dict) and all(isinstance(v, str) for v in bm.values())
    ):
        errors.append("truth.biomarkers: must be an object of string values")


def validate_case(payload: Any) -> list[str]:
    """Return a list of human-readable problems with ``payload``; empty means valid.

    A pure, dependency-free check (no ``jsonschema``): used by tests, the generator and the
    fine-tuning export so an invalid case never reaches a model. It does not mutate the input.
    """
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["case: must be a JSON object"]

    for key in ("case_id", "language", "documentation_format", "messiness", "truth", "note"):
        if key not in payload:
            errors.append(f"{key}: required")

    if isinstance(payload.get("case_id"), str):
        if not payload["case_id"].strip():
            errors.append("case_id: must be non-empty")
    elif "case_id" in payload:
        errors.append("case_id: must be a string")

    _enum(errors, "language", payload.get("language"), LANGUAGES)
    _enum(errors, "documentation_format", payload.get("documentation_format"), DOC_FORMATS)
    _enum(errors, "messiness", payload.get("messiness"), MESSINESS)

    if payload.get("source_type", SOURCE_TYPE) != SOURCE_TYPE:
        errors.append(f"source_type: must be {SOURCE_TYPE!r}")
    if "note" in payload and not isinstance(payload["note"], str):
        errors.append("note: must be a string")

    if "truth" in payload:
        _validate_truth(errors, payload["truth"])

    tags = payload.get("difficulty_tags", [])
    if not isinstance(tags, list):
        errors.append("difficulty_tags: must be an array")
    else:
        for tag in tags:
            _enum(errors, "difficulty_tags[]", tag, DIFFICULTY_TAGS)

    split = payload.get("split")
    if split is not None:
        _enum(errors, "split", split, SPLITS)

    expected = payload.get("expected_output", {})
    if not isinstance(expected, dict):
        errors.append("expected_output: must be an object")
    else:
        for name, fobj in expected.items():
            if not isinstance(fobj, dict) or "value" not in fobj:
                errors.append(f"expected_output.{name}: must be an object with a 'value'")

    return errors
