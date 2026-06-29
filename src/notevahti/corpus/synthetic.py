"""Typed model + structural validator for one synthetic Nordic lung-cancer MDT *record*.

stdlib-only, offline, deterministic. The on-disk shape is the row schema produced by the corpus
generator (see ``docs/research/synthetic_corpus_generator_prompt.md``): one JSON object per text
record, with each clinical ``case_id`` rendered in three documentation formats. The controlled
vocabulary below is the single source of truth shared with the published JSON Schema
(``corpus/schema/synthetic_case.schema.json``); a test asserts the two agree, so they cannot drift.

``validate_row`` enforces the generator's own quality invariants (evidence must be an exact span of
the note, conflicting TNM must not be silently resolved, a planned MDT is not a completed MDT,
indirect/missing ECOG is not turned into a number, the split is consistent across a case's variants
via ``record_id``). It is dependency-free (no ``jsonschema``) so the generator can call it to fail
fast, and it never mutates its input.

The TNM block keeps the generator's ``complete``/``ambiguous`` booleans; ``Tnm.completeness``
derives the same four-way vocabulary as :func:`notevahti.extractors.rules.parse_tnm`, so a record
can be compared against the reference extractor's output without a second mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DATASET_VERSION = "notevahti_lung_mdt_synthetic_v1"
SOURCE_TYPE = "synthetic"  # the only allowed value: this model is for synthetic data only

# --- controlled vocabulary (single source of truth, mirrored by the JSON Schema) ---------------
LANGUAGES = frozenset({"fi", "sv", "nb", "da", "is", "en"})  # Norwegian Bokmål = nb (repo-wide)
DOC_FORMATS = frozenset({"free_text", "structured_mini", "structured_v3_1"})
MESSINESS = frozenset({"clean", "semistructured", "messy"})
SPLITS = frozenset({"train", "dev", "test"})
TNM_PREFIXES = frozenset({"c", "yc", "p", "yp", "unknown", "ambiguous"})
MDT_STATUSES = frozenset({"completed", "planned", "not_completed", "unknown"})
ECOG_STATUSES = frozenset({"explicit", "indirect", "missing", "conflicting", "unknown"})
TREATMENT_INTENTS = frozenset(
    {"curative", "palliative", "diagnostic", "best_supportive_care", "unknown"}
)
BIOMARKER_KEYS = frozenset({"egfr", "alk", "ros1", "braf", "met", "ret", "ntrk", "kras", "pdl1"})
PRIMARY_FIELDS = ("mdt_discussed", "ecog_ps", "tnm")
QUALITY_LABEL_KEYS = frozenset(
    {
        "has_negation",
        "has_conflict",
        "has_missing_ecog",
        "has_partial_tnm",
        "has_old_staging",
        "has_future_mdt",
        "has_indirect_ecog",
        "requires_review",
        "registry_ready",
    }
)


@dataclass(frozen=True)
class Tnm:
    """Ground-truth TNM. ``None`` on an axis means it is not documented."""

    prefix: str  # one of TNM_PREFIXES
    t: str | None
    n: str | None
    m: str | None
    complete: bool
    ambiguous: bool
    full: str | None = None  # combined surface, e.g. 'cT2aN1M0', or None
    edition: str = "unknown"

    @property
    def completeness(self) -> str:
        """Four-way completeness using the same vocabulary as ``parse_tnm``."""
        if self.ambiguous:
            return "ambiguous"
        if self.complete:
            return "complete"
        if any((self.t, self.n, self.m)):
            return "partial"
        return "absent"


@dataclass(frozen=True)
class GroundTruth:
    """Machine-checkable ground truth for a case (authored before the note)."""

    mdt_discussed: bool | None
    mdt_status: str  # one of MDT_STATUSES
    ecog_ps: int | None  # 0..4 or None
    ecog_status: str  # one of ECOG_STATUSES
    tnm: Tnm
    treatment_intent: str  # one of TREATMENT_INTENTS
    histology: str | None = None
    stage_group: str | None = None
    biomarkers: dict[str, str] | None = None
    mdt_recommendation: str | None = None
    imaging_summary: str | None = None
    pathology_summary: str | None = None
    diagnostic_uncertainty: bool | str | None = None
    review_required: bool | None = None


@dataclass(frozen=True)
class ExpectedField:
    """One field of the supervised target: value, verbatim in-note evidence, and a review flag."""

    value: Any
    evidence: str | None
    requires_review: bool
    components: dict[str, Any] | None = None  # e.g. TNM {prefix, t, n, m}


@dataclass(frozen=True)
class QualityLabels:
    """Per-record quality flags. All booleans."""

    has_negation: bool = False
    has_conflict: bool = False
    has_missing_ecog: bool = False
    has_partial_tnm: bool = False
    has_old_staging: bool = False
    has_future_mdt: bool = False
    has_indirect_ecog: bool = False
    requires_review: bool = False
    registry_ready: bool = True


@dataclass(frozen=True)
class SyntheticRow:
    """One synthetic text record: metadata, ground truth, the note, target, and quality labels."""

    case_id: str
    record_id: str
    language: str
    documentation_format: str
    messiness: str
    split_hint: str
    ground_truth: GroundTruth
    note_text: str
    expected_output: dict[str, ExpectedField] = field(default_factory=dict)
    quality_labels: QualityLabels = field(default_factory=QualityLabels)
    dataset_version: str = DATASET_VERSION
    source_type: str = SOURCE_TYPE

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> SyntheticRow:
        """Build a row from a parsed-JSON dict, raising ``ValueError`` if it is not valid."""
        errors = validate_row(payload)
        if errors:
            raise ValueError("invalid synthetic row: " + "; ".join(errors))
        gt = payload["ground_truth"]
        tnm = gt["tnm"]
        expected = {
            name: ExpectedField(
                value=f.get("value"),
                evidence=f.get("evidence"),
                requires_review=bool(f.get("requires_review", False)),
                components=f.get("components"),
            )
            for name, f in payload.get("expected_output", {}).items()
        }
        ql = payload.get("quality_labels", {})
        return SyntheticRow(
            case_id=payload["case_id"],
            record_id=payload["record_id"],
            language=payload["language"],
            documentation_format=payload["documentation_format"],
            messiness=payload["messiness"],
            split_hint=payload["split_hint"],
            ground_truth=GroundTruth(
                mdt_discussed=gt.get("mdt_discussed"),
                mdt_status=gt["mdt_status"],
                ecog_ps=gt.get("ecog_ps"),
                ecog_status=gt["ecog_status"],
                tnm=Tnm(
                    prefix=tnm["prefix"],
                    t=tnm.get("t"),
                    n=tnm.get("n"),
                    m=tnm.get("m"),
                    complete=bool(tnm["complete"]),
                    ambiguous=bool(tnm["ambiguous"]),
                    full=tnm.get("full"),
                    edition=tnm.get("edition", "unknown"),
                ),
                treatment_intent=gt["treatment_intent"],
                histology=gt.get("histology"),
                stage_group=gt.get("stage_group"),
                biomarkers=gt.get("biomarkers"),
                mdt_recommendation=gt.get("mdt_recommendation"),
                imaging_summary=gt.get("imaging_summary"),
                pathology_summary=gt.get("pathology_summary"),
                diagnostic_uncertainty=gt.get("diagnostic_uncertainty"),
                review_required=gt.get("review_required"),
            ),
            note_text=payload["note_text"],
            expected_output=expected,
            quality_labels=QualityLabels(**{k: bool(ql[k]) for k in QUALITY_LABEL_KEYS if k in ql}),
            dataset_version=payload.get("dataset_version", DATASET_VERSION),
            source_type=payload.get("source_type", SOURCE_TYPE),
        )


def _enum(errors: list[str], path: str, value: Any, allowed: frozenset[str]) -> None:
    if value not in allowed:
        errors.append(f"{path}: {value!r} not in {sorted(allowed)}")


def _validate_tnm(errors: list[str], tnm: Any) -> None:
    if not isinstance(tnm, dict):
        errors.append("ground_truth.tnm: must be an object")
        return
    for key in ("prefix", "complete", "ambiguous"):
        if key not in tnm:
            errors.append(f"ground_truth.tnm.{key}: required")
    _enum(errors, "ground_truth.tnm.prefix", tnm.get("prefix"), TNM_PREFIXES)
    for axis in ("t", "n", "m", "full"):
        v = tnm.get(axis)
        if v is not None and not isinstance(v, str):
            errors.append(f"ground_truth.tnm.{axis}: must be a string or null")
    for flag in ("complete", "ambiguous"):
        if flag in tnm and not isinstance(tnm[flag], bool):
            errors.append(f"ground_truth.tnm.{flag}: must be true or false")
    if not isinstance(tnm.get("edition", "unknown"), str):
        errors.append("ground_truth.tnm.edition: must be a string")


def _validate_biomarkers(errors: list[str], bm: Any) -> None:
    if bm is None:
        return
    if not isinstance(bm, dict):
        errors.append("ground_truth.biomarkers: must be an object or null")
        return
    for k, v in bm.items():
        if k not in BIOMARKER_KEYS:
            errors.append(f"ground_truth.biomarkers: unknown marker {k!r}")
        if not isinstance(v, str):
            errors.append(f"ground_truth.biomarkers.{k}: must be a string")


def _validate_ground_truth(errors: list[str], gt: Any) -> None:
    if not isinstance(gt, dict):
        errors.append("ground_truth: must be an object")
        return
    for key in ("mdt_status", "ecog_status", "tnm", "treatment_intent"):
        if key not in gt:
            errors.append(f"ground_truth.{key}: required")
    mdt = gt.get("mdt_discussed")
    if mdt is not None and not isinstance(mdt, bool):
        errors.append("ground_truth.mdt_discussed: must be true, false, or null")
    _enum(errors, "ground_truth.mdt_status", gt.get("mdt_status"), MDT_STATUSES)
    ecog = gt.get("ecog_ps")
    if ecog is not None and not (isinstance(ecog, int) and 0 <= ecog <= 4):
        errors.append("ground_truth.ecog_ps: must be an integer 0..4 or null")
    _enum(errors, "ground_truth.ecog_status", gt.get("ecog_status"), ECOG_STATUSES)
    _enum(errors, "ground_truth.treatment_intent", gt.get("treatment_intent"), TREATMENT_INTENTS)
    if "tnm" in gt:
        _validate_tnm(errors, gt["tnm"])
    _validate_biomarkers(errors, gt.get("biomarkers"))


def _validate_expected(errors: list[str], expected: Any, note_text: Any) -> None:
    if not isinstance(expected, dict):
        errors.append("expected_output: must be an object")
        return
    for name in PRIMARY_FIELDS:
        if name not in expected:
            errors.append(f"expected_output.{name}: required")
    for name, fobj in expected.items():
        if not isinstance(fobj, dict) or "value" not in fobj:
            errors.append(f"expected_output.{name}: must be an object with a 'value'")
            continue
        evidence = fobj.get("evidence")
        if evidence is not None:
            if not isinstance(evidence, str):
                errors.append(f"expected_output.{name}.evidence: must be a string or null")
            elif isinstance(note_text, str) and evidence not in note_text:
                errors.append(f"expected_output.{name}.evidence: not an exact span of note_text")
    ecog = expected.get("ecog_ps")
    if isinstance(ecog, dict):
        v = ecog.get("value")
        if v is not None and not (isinstance(v, int) and 0 <= v <= 4):
            errors.append("expected_output.ecog_ps.value: must be an integer 0..4 or null")


def _validate_quality_labels(errors: list[str], ql: Any) -> None:
    if not isinstance(ql, dict):
        errors.append("quality_labels: must be an object")
        return
    for k, v in ql.items():
        if k not in QUALITY_LABEL_KEYS:
            errors.append(f"quality_labels: unknown flag {k!r}")
        elif not isinstance(v, bool):
            errors.append(f"quality_labels.{k}: must be true or false")


def _cross_checks(errors: list[str], payload: dict[str, Any]) -> None:
    """The generator's own invariants — these must hold for any correct record."""
    case_id = payload.get("case_id")
    fmt = payload.get("documentation_format")
    record_id = payload.get("record_id")
    if (
        isinstance(case_id, str)
        and isinstance(fmt, str)
        and isinstance(record_id, str)
        and record_id != f"{case_id}_{fmt}"
    ):
        errors.append(f"record_id: expected {case_id}_{fmt!r}-style id, got {record_id!r}")

    gt = payload.get("ground_truth")
    expected = payload.get("expected_output")
    ql = payload.get("quality_labels")
    if not isinstance(gt, dict):
        return

    mdt_status = gt.get("mdt_status")
    if mdt_status == "completed" and gt.get("mdt_discussed") is not True:
        errors.append("mdt_status 'completed' requires ground_truth.mdt_discussed true")
    if mdt_status in ("planned", "not_completed") and gt.get("mdt_discussed") is True:
        errors.append(f"mdt_status {mdt_status!r} is incompatible with mdt_discussed true")

    tnm = gt.get("tnm")
    if isinstance(tnm, dict) and tnm.get("ambiguous") is True and isinstance(expected, dict):
        tfield = expected.get("tnm")
        if isinstance(tfield, dict):
            if tfield.get("value") is not None:
                errors.append("ambiguous TNM: expected_output.tnm.value must be null")
            if tfield.get("requires_review") is not True:
                errors.append("ambiguous TNM: expected_output.tnm.requires_review must be true")

    if isinstance(ql, dict) and isinstance(expected, dict):
        if ql.get("has_missing_ecog") or ql.get("has_indirect_ecog"):
            efield = expected.get("ecog_ps")
            if isinstance(efield, dict) and efield.get("value") is not None:
                errors.append("missing/indirect ECOG: expected_output.ecog_ps.value must be null")
        if ql.get("requires_review") is True and ql.get("registry_ready") is True:
            errors.append(
                "quality_labels: requires_review true is incompatible with registry_ready true"
            )


def validate_row(payload: Any) -> list[str]:
    """Return a list of human-readable problems with ``payload``; empty means valid.

    A pure, dependency-free check (no ``jsonschema``): used by tests and the generator's QC step so
    an invalid record never reaches a model. It does not mutate the input.
    """
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["row: must be a JSON object"]

    required = (
        "case_id",
        "record_id",
        "language",
        "documentation_format",
        "messiness",
        "split_hint",
        "ground_truth",
        "note_text",
    )
    for key in required:
        if key not in payload:
            errors.append(f"{key}: required")

    for key in ("case_id", "record_id", "note_text"):
        v = payload.get(key)
        if key in payload and (not isinstance(v, str) or not v.strip()):
            errors.append(f"{key}: must be a non-empty string")

    if payload.get("dataset_version", DATASET_VERSION) != DATASET_VERSION:
        errors.append(f"dataset_version: must be {DATASET_VERSION!r}")
    if payload.get("source_type", SOURCE_TYPE) != SOURCE_TYPE:
        errors.append(f"source_type: must be {SOURCE_TYPE!r}")

    _enum(errors, "language", payload.get("language"), LANGUAGES)
    _enum(errors, "documentation_format", payload.get("documentation_format"), DOC_FORMATS)
    _enum(errors, "messiness", payload.get("messiness"), MESSINESS)
    _enum(errors, "split_hint", payload.get("split_hint"), SPLITS)

    if "ground_truth" in payload:
        _validate_ground_truth(errors, payload["ground_truth"])
    _validate_expected(errors, payload.get("expected_output", {}), payload.get("note_text"))
    if "quality_labels" in payload:
        _validate_quality_labels(errors, payload["quality_labels"])

    _cross_checks(errors, payload)
    return errors
