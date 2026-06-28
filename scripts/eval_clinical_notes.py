"""Stage-1 enrichment eval on the external synthetic clinical-note dataset.

Runs the NoteVahti review flag (single-source: value + note, no gold injected) over every extraction
in ``corpus/synthetic_clinical_notes`` and measures whether the flag concentrates true
(against-gold) errors — the dataset's own "minimal expected test" and the Stage-1 kill/scale signal.

Honest by construction: the gold value is never fed to the validator. We only measure what the flag
predicts from the note and the extracted value. Deterministic and offline.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from notevahti.analytics.discrimination import (
    FlagDiscrimination,
    ScoreDiscrimination,
    flag_discrimination,
    score_discrimination,
)
from notevahti.types import FieldType, Lineage, ProvenanceStatus
from notevahti.validate import validate_field

_STAGING_FIELDS = {"stage", "tnm_t", "tnm_n", "tnm_m"}
_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "corpus" / "synthetic_clinical_notes"


def field_type_for(field_name: str) -> FieldType:
    if field_name in _STAGING_FIELDS:
        return FieldType.STAGING
    if field_name == "pack_years":
        return FieldType.NUMERIC
    return FieldType.CATEGORICAL


@dataclass(frozen=True)
class SeededStat:
    seeded_type: str
    n: int
    errors: int
    flagged: int
    errors_caught: int
    provenance_found: int


@dataclass(frozen=True)
class EnrichmentResult:
    n: int
    true_errors: int
    review_n: int
    accept_n: int
    review_error_rate: float
    accept_error_rate: float
    enrichment: float  # review_error_rate / accept_error_rate (inf if accept rate is 0)
    sensitivity: float
    provenance_found: int
    by_seeded_type: list[SeededStat]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def evaluate(dataset_dir: Path = _DEFAULT_DIR) -> EnrichmentResult:
    notes = {n["note_id"]: n for n in _read_csv(dataset_dir / "notes.csv")}
    extractions = _read_csv(dataset_dir / "extractions.csv")

    tp = fp = tn = fn = 0
    provenance_found = 0
    acc: dict[str, dict[str, int]] = {}

    for e in extractions:
        note = notes[e["note_id"]]
        rec = validate_field(
            e["extracted_value"],
            note["note_text"],
            field_type=field_type_for(e["field_name"]),
            field_name=e["field_name"],
            value_lineage=Lineage(source_id=e["note_id"], model_id=e["extractor_id"]),
        )
        flagged = rec.validity.flag_for_human_review
        found = rec.provenance.status is ProvenanceStatus.SPAN_FOUND
        error = e["is_correct_against_gold"] == "False"

        provenance_found += found
        if error and flagged:
            tp += 1
        elif error and not flagged:
            fn += 1
        elif not error and flagged:
            fp += 1
        else:
            tn += 1

        st = note["seeded_error_type"]
        s = acc.setdefault(
            st, {"n": 0, "errors": 0, "flagged": 0, "errors_caught": 0, "provenance_found": 0}
        )
        s["n"] += 1
        s["errors"] += error
        s["flagged"] += flagged
        s["provenance_found"] += found
        if error and flagged:
            s["errors_caught"] += 1

    review_n = tp + fp
    accept_n = tn + fn
    review_rate = tp / review_n if review_n else 0.0
    accept_rate = fn / accept_n if accept_n else 0.0
    enrichment = (review_rate / accept_rate) if accept_rate else float("inf")
    true_errors = tp + fn
    sensitivity = tp / true_errors if true_errors else 0.0

    by_type = [
        SeededStat(
            seeded_type=st,
            n=s["n"],
            errors=s["errors"],
            flagged=s["flagged"],
            errors_caught=s["errors_caught"],
            provenance_found=s["provenance_found"],
        )
        for st, s in sorted(acc.items(), key=lambda kv: -kv[1]["errors"])
    ]
    return EnrichmentResult(
        n=len(extractions),
        true_errors=true_errors,
        review_n=review_n,
        accept_n=accept_n,
        review_error_rate=round(review_rate, 4),
        accept_error_rate=round(accept_rate, 4),
        enrichment=round(enrichment, 2) if enrichment != float("inf") else enrichment,
        sensitivity=round(sensitivity, 4),
        provenance_found=provenance_found,
        by_seeded_type=by_type,
    )


def discrimination(
    dataset_dir: Path = _DEFAULT_DIR, *, deployment_prevalence: float = 0.05
) -> tuple[FlagDiscrimination, ScoreDiscrimination]:
    """TRIPOD+AI-style discrimination of the flag/validity score over the dataset.

    Honest: the gold value is never fed to the validator. ``deployment_prevalence`` is the assumed
    registry error base-rate at which PPV/NPV are reported (a pilot's PPV does not transfer).
    """
    notes = {n["note_id"]: n for n in _read_csv(dataset_dir / "notes.csv")}
    flags: list[bool] = []
    scores: list[float] = []
    errors: list[bool] = []
    for e in _read_csv(dataset_dir / "extractions.csv"):
        note = notes[e["note_id"]]
        rec = validate_field(
            e["extracted_value"],
            note["note_text"],
            field_type=field_type_for(e["field_name"]),
            field_name=e["field_name"],
            value_lineage=Lineage(source_id=e["note_id"], model_id=e["extractor_id"]),
        )
        flags.append(rec.validity.flag_for_human_review)
        scores.append(rec.validity.score)
        errors.append(e["is_correct_against_gold"] == "False")
    flag = flag_discrimination(
        flags, errors, deployment_prevalence=deployment_prevalence, bootstrap=1000, seed=20260628
    )
    # validity score: HIGHER means LESS likely an error
    score = score_discrimination(
        scores, errors, higher_is_error=False, bootstrap=1000, seed=20260628
    )
    return flag, score


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=_DEFAULT_DIR)
    ap.add_argument("--deployment-prevalence", type=float, default=0.05)
    args = ap.parse_args(argv)
    r = evaluate(args.dir)
    print(f"rows={r.n}  provenance_found={r.provenance_found}/{r.n}  true_errors={r.true_errors}")
    print(f"review n={r.review_n}  error rate within review = {r.review_error_rate}")
    print(f"accept n={r.accept_n}  error rate within accept = {r.accept_error_rate}")
    print(f"ENRICHMENT (review/accept) = {r.enrichment}x   sensitivity = {r.sensitivity}")
    print("\nseeded_type              n  err  flagged  caught  provfound")
    for s in r.by_seeded_type:
        print(
            f"  {s.seeded_type:22}{s.n:4} {s.errors:4} {s.flagged:8} "
            f"{s.errors_caught:7} {s.provenance_found:9}"
        )

    fd, sd = discrimination(args.dir, deployment_prevalence=args.deployment_prevalence)
    print("\nTRIPOD+AI discrimination (flag):")
    print(
        f"  sensitivity={fd.sensitivity}  specificity={fd.specificity}  "
        f"PPV(sample)={fd.ppv_sample}  NPV(sample)={fd.npv_sample}"
    )
    print(
        f"  at deployment prevalence {fd.deployment_prevalence}: "
        f"PPV={fd.ppv_at_deployment}  NPV={fd.npv_at_deployment}"
    )
    print(f"  enrichment={fd.enrichment}  95% CI={fd.enrichment_ci}")
    print("validity score:")
    print(f"  AUROC={sd.auroc} CI={sd.auroc_ci}  AUPRC={sd.auprc} (baseline={sd.auprc_baseline})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
