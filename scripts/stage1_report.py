"""Emit the Stage-1 evidence pack and preregistration skeleton for the clinical-note dataset.

Runs NoteVahti over corpus/synthetic_clinical_notes (gold never fed to the validator), builds the
TRIPOD+AI-aligned evidence pack with subgroups by language and field, and prints it with the
preregistration skeleton. The inputs are SYNTHETIC, so the pack is a synthetic-only methodology
demonstration, not validation evidence. Deterministic and offline.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from notevahti.analytics.evidence_pack import Observation, build_evidence_pack, to_markdown
from notevahti.analytics.preregistration import preregistration_markdown
from notevahti.types import FieldType, Lineage
from notevahti.validate import validate_field

_DATA = Path(__file__).resolve().parent.parent / "corpus" / "synthetic_clinical_notes"
_STAGING = {"stage", "tnm_t", "tnm_n", "tnm_m"}


def _field_type(field_name: str) -> FieldType:
    if field_name in _STAGING:
        return FieldType.STAGING
    if field_name == "pack_years":
        return FieldType.NUMERIC
    return FieldType.CATEGORICAL


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def observations(data_dir: Path = _DATA) -> list[Observation]:
    notes = {n["note_id"]: n for n in _read(data_dir / "notes.csv")}
    obs: list[Observation] = []
    for e in _read(data_dir / "extractions.csv"):
        note = notes[e["note_id"]]
        rec = validate_field(
            e["extracted_value"],
            note["note_text"],
            field_type=_field_type(e["field_name"]),
            field_name=e["field_name"],
            value_lineage=Lineage(source_id=e["note_id"], model_id=e["extractor_id"]),
        )
        obs.append(
            Observation(
                error=e["is_correct_against_gold"] == "False",
                flagged=rec.validity.flag_for_human_review,
                validity_score=rec.validity.score,
                subgroups={"language": note["language"], "field": e["field_name"]},
            )
        )
    return obs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=_DATA)
    ap.add_argument("--deployment-prevalence", type=float, default=0.05)
    args = ap.parse_args(argv)
    pack = build_evidence_pack(
        observations(args.dir),
        subgroup_dims=("language", "field"),
        deployment_prevalence=args.deployment_prevalence,
        seed=20260628,
        bootstrap=1000,
    )
    print(to_markdown(pack))
    print("\n" + "=" * 80 + "\n")
    print(preregistration_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
