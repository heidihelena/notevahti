"""Boundary eval: can NoteVahti's provenance BIND canonical ground-truth values in messy MDT notes?

These cases (corpus/messy_mdt) are deliberately hard: implicit staging (no verbatim cTNM), heavy
abbreviation (adenoCa, neg/pos, chemoRT), copy-forward and distractor lines, a typo. We treat each
ground-truth field value as what an extractor might emit and ask whether `verify_span` (search, no
extractor-supplied span) can locate it.

Honest purpose: map the limit of string provenance. It shows (a) inferred values (staging) cannot be
bound at all, (b) abbreviated/synonymous values are missed, and (c) trivial single-token values can
*spuriously* bind to an incidental substring. The lesson is that NoteVahti validates spans the
extractor supplies; it is not a re-locator. Deterministic and offline.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from notevahti.provenance import verify_span
from notevahti.types import FieldType, ProvenanceStatus

_DEFAULT = Path(__file__).resolve().parent.parent / "corpus" / "messy_mdt" / "cases.jsonl"

_FT = {
    "key_date": FieldType.TEXT,
    "age": FieldType.NUMERIC,
    "ecog": FieldType.NUMERIC,
    "PD_L1_tps_percent": FieldType.NUMERIC,
    "sex": FieldType.CATEGORICAL,
    "histology": FieldType.CATEGORICAL,
    "mdt_decision": FieldType.CATEGORICAL,
    "EGFR": FieldType.CATEGORICAL,
    "ALK": FieldType.CATEGORICAL,
    "ROS1": FieldType.CATEGORICAL,
    "KRAS": FieldType.CATEGORICAL,
    "cT": FieldType.STAGING,
    "cN": FieldType.STAGING,
    "cM": FieldType.STAGING,
    "stage_group": FieldType.STAGING,
}
_STAGING_FIELDS = {"cT", "cN", "cM", "stage_group"}


def field_type_for(field: str) -> FieldType:
    return _FT.get(field, FieldType.CATEGORICAL)


def candidates(gt: dict[str, object]) -> Iterator[tuple[str, str]]:
    for k in (
        "age",
        "sex",
        "histology",
        "cT",
        "cN",
        "cM",
        "stage_group",
        "ecog",
        "mdt_decision",
        "key_date",
    ):
        v = gt.get(k)
        if v is not None:
            yield k, str(v)
    biomarkers = gt.get("biomarkers")
    if isinstance(biomarkers, dict):
        for bk, bv in biomarkers.items():
            if bv is not None:
                yield bk, str(bv)


@dataclass(frozen=True)
class BindingResult:
    total: int
    found: int
    missed: int
    by_field: dict[str, tuple[int, int]]  # field -> (found, total)
    staging_found: int
    staging_total: int


def evaluate(path: Path = _DEFAULT) -> BindingResult:
    by_field: dict[str, list[int]] = {}
    found = total = staging_found = staging_total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        note = rec["note_text"]
        for field, val in candidates(rec["ground_truth"]):
            p = verify_span(val, note, field_type=field_type_for(field))
            ok = p.status is ProvenanceStatus.SPAN_FOUND
            total += 1
            found += ok
            fc = by_field.setdefault(field, [0, 0])
            fc[0] += ok
            fc[1] += 1
            if field in _STAGING_FIELDS:
                staging_total += 1
                staging_found += ok
    return BindingResult(
        total=total,
        found=found,
        missed=total - found,
        by_field={f: (a, b) for f, (a, b) in sorted(by_field.items())},
        staging_found=staging_found,
        staging_total=staging_total,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", type=Path, default=_DEFAULT)
    args = ap.parse_args(argv)
    r = evaluate(args.path)
    print(f"ground-truth values bound by search: {r.found}/{r.total} (missed {r.missed})")
    print(f"staging (cT/cN/cM/stage_group) bound: {r.staging_found}/{r.staging_total}")
    print("per field (found/total):")
    for f, (a, b) in r.by_field.items():
        print(f"  {f:18} {a}/{b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
