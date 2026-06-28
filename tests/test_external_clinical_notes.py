"""External synthetic clinical-note dataset: integrity, Stage-1 flag enrichment, and known gaps.

The dataset (corpus/synthetic_clinical_notes) ships notes, gold labels, simulated extractions and
seeded failure modes. These tests check the data is internally consistent and that NoteVahti's review
flag concentrates true (against-gold) errors — the dataset's stated minimal expected test — while
honestly recording the failure modes the current string-provenance cannot yet catch.
"""

import csv
import sys
from pathlib import Path

from notevahti.audit import hash_text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from eval_clinical_notes import evaluate

DATA = Path(__file__).resolve().parent.parent / "corpus" / "synthetic_clinical_notes"


def _rows(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_dataset_integrity():
    notes = _rows("notes.csv")
    ext = _rows("extractions.csv")
    gold = _rows("gold_labels.csv")
    tc = _rows("test_cases.csv")
    assert len(notes) == 150
    assert len(ext) == len(gold) == 1950
    assert len(tc) == 150
    note_ids = {n["note_id"] for n in notes}
    assert {e["note_id"] for e in ext} <= note_ids
    # languages cover Finnish and Swedish (audit priority #4)
    langs = {n["language"] for n in notes}
    assert {"fi", "sv", "en"} <= langs


def test_note_sha256_matches_text():
    for n in _rows("notes.csv"):
        assert hash_text(n["note_text"]) == n["note_sha256"], n["note_id"]


def test_review_flag_enriches_for_true_errors():
    # The kill/scale test: errors must concentrate in the review group vs the accept group.
    r = evaluate(DATA)
    assert r.true_errors > 0
    assert r.review_n > 0
    assert r.review_error_rate > r.accept_error_rate
    # strong enrichment expected on this dataset (currently ~66x, perfect review precision)
    assert r.enrichment >= 5.0
    assert r.review_error_rate >= 0.9


def test_absence_type_errors_are_caught():
    # Errors where the wrong value is NOT in the note: provenance fails -> flagged.
    r = {s.seeded_type: s for s in evaluate(DATA).by_seeded_type}
    for kind in ("unsupported_value", "unit_format", "negation_trap"):
        s = r[kind]
        assert s.errors > 0
        assert s.errors_caught == s.errors, (kind, s)


def test_known_gap_present_but_wrong_currently_missed():
    # CHARACTERIZATION of the current limitation (audit #2/#3): when the wrong value IS present in
    # the note (copied from an old timepoint, or a conflicting source), string provenance finds it
    # and the flag does NOT fire. Closing this needs temporality + independent-anchor signals.
    # If a future change starts catching these, update this test — the improvement is intended.
    r = {s.seeded_type: s for s in evaluate(DATA).by_seeded_type}
    for kind in ("temporal_trap", "copy_forward_old_stage", "source_conflict"):
        s = r[kind]
        assert s.errors > 0
        assert s.errors_caught == 0, (kind, s)


def test_clean_notes_are_not_flagged_as_errors():
    # 'none' seeded type has no against-gold errors; the flag must not invent errors there.
    r = {s.seeded_type: s for s in evaluate(DATA).by_seeded_type}
    assert r["none"].errors == 0
    assert r["none"].errors_caught == 0
