"""Core data types for NoteVahti.

These are pure data carriers — no logic, no I/O, no clock, no RNG, no model. Anything
non-deterministic (timestamps, ids) is supplied by the caller at the edge and merely stored here, so
the validation core stays deterministic and testable.

Enums subclass ``str`` so that ``to_dict`` output is directly JSON-serializable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, cast

# --------------------------------------------------------------------------- enums


class FieldType(str, Enum):
    """How a field's value should be compared and scored."""

    CATEGORICAL = "categorical"
    NUMERIC = "numeric"
    DATE = "date"
    TEXT = "text"
    STAGING = "staging"  # TNM / clinical stage — categorical with domain normalisation


class MatchKind(str, Enum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    NONE = "none"


class ProvenanceStatus(str, Enum):
    SPAN_FOUND = "span_found"
    NO_SPAN_FOUND = "no_span_found"


class IndependenceStatus(str, Enum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNKNOWN = "unknown"


class AgreementStatus(str, Enum):
    AVAILABLE = "available"
    NOT_AVAILABLE = "not_available"


class SignalKind(str, Enum):
    INDEPENDENT_HUMAN = "independent_human"
    INDEPENDENT_MODEL = "independent_model"
    INDEPENDENT_SOURCE = "independent_source"
    OTHER = "other"


# --------------------------------------------------------------------------- lineage / inputs


@dataclass(frozen=True)
class Lineage:
    """Declared origin of a value or signal.

    Independence is enforced on *declared* lineage: two lineages are independent only if they share
    no identifier on any populated axis. NoteVahti does not infer independence; the caller declares
    it and NoteVahti enforces disjointness and records the declaration.
    """

    source_id: str | None = None  # the note / document the value was read from
    model_id: str | None = None  # the model/regex/pipeline that produced it
    human_id: str | None = None  # the person who produced/adjudicated it

    def is_empty(self) -> bool:
        return not (self.source_id or self.model_id or self.human_id)

    def shares_with(self, other: Lineage) -> str | None:
        """Return the name of the first shared, populated axis, or None if disjoint."""
        for axis in ("source_id", "model_id", "human_id"):
            a = getattr(self, axis)
            b = getattr(other, axis)
            if a is not None and b is not None and a == b:
                return axis
        return None


@dataclass(frozen=True)
class FieldSpec:
    """Describes the field under validation."""

    name: str
    field_type: FieldType = FieldType.TEXT
    allowed_values: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Signal:
    """An independent validation signal: another assertion of the field's value."""

    value: str
    lineage: Lineage
    kind: SignalKind = SignalKind.OTHER


@dataclass(frozen=True)
class ExtractionResult:
    """What a (pluggable) extractor returns. NoteVahti never trusts this as truth."""

    value: str
    source_span: tuple[int, int] | None = None  # char offsets [start, end) into the note
    extractor_id: str = "unknown"
    version: str = "0"


# --------------------------------------------------------------------------- outputs


@dataclass(frozen=True)
class Provenance:
    status: ProvenanceStatus
    claimed_span: tuple[int, int] | None
    matched_span: tuple[int, int] | None
    matched_text: str | None
    match_kind: MatchKind
    hallucination_flag: bool
    detail: str = ""


@dataclass(frozen=True)
class Validity:
    score: float  # in [0, 1]
    flag_for_human_review: bool
    threshold: float
    components: dict[str, float] = field(default_factory=dict)
    detail: str = ""


@dataclass(frozen=True)
class Agreement:
    status: AgreementStatus
    n: int = 0
    accuracy: float | None = None
    kappa: float | None = None
    detail: str = ""


@dataclass(frozen=True)
class Independence:
    status: IndependenceStatus
    reason: str
    anchors_considered: int = 0
    independent_anchors: int = 0


@dataclass(frozen=True)
class AuditEntry:
    """One append-only, hash-chained audit record. ids/timestamps are caller-supplied."""

    record_id: str
    timestamp: str  # ISO-8601, supplied by the caller (no clock in the core)
    actor: str
    prev_hash: str
    payload: dict[str, Any]
    entry_hash: str = ""  # filled by the audit module


@dataclass(frozen=True)
class ValidationRecord:
    """The unit of NoteVahti output: the five outputs, bound to the value and field."""

    value: str
    field: FieldSpec
    provenance: Provenance
    validity: Validity
    agreement: Agreement
    independence: Independence
    audit: AuditEntry | None = None
    notevahti_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable view (enums are str-subclasses; tuples become lists)."""
        return cast("dict[str, Any]", _jsonable(asdict(self)))


# --------------------------------------------------------------------------- helpers


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, Enum):
        return obj.value
    return obj
