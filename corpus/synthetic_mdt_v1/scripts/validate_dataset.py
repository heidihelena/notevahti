#!/usr/bin/env python3
"""Validate the NoteVahti synthetic MDT JSONL dataset.

Row-level validation is delegated to ``notevahti.corpus.validate_row`` (the single contract shared
with the typed model and the published JSON Schema). This script adds what is *corpus-level* and
not part of one row's contract: per-language distributions and the case-level split, identifier
hygiene (PII), and the note convention that a resolved TNM among several must carry an explicit
"current TNM <value>" marker.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Make the in-repo notevahti package importable without installation (standalone + subprocess use).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from notevahti.corpus import validate_row  # noqa: E402  (after sys.path shim)

DATASET_VERSION = "notevahti_lung_mdt_synthetic_v1"
LANGUAGES = ["fi", "sv", "nb", "da", "is", "en"]
DOCUMENTATION_FORMATS = {"free_text", "structured_mini", "structured_v3_1"}

CASE_CATEGORY_COUNTS = {
    "clear_explicit": 90,
    "missing_ecog": 30,
    "partial_tnm": 30,
    "conflicting_tnm": 30,
    "old_vs_current_staging": 30,
    "mdt_planned": 15,
    "mdt_not_yet_discussed": 15,
    "indirect_functional_status": 30,
    "biomarker_treatment_complexity": 30,
}

HISTOLOGY_COUNTS = {
    "adenocarcinoma": 135,
    "squamous cell carcinoma": 75,
    "NSCLC NOS": 30,
    "small-cell lung cancer": 30,
    "other_or_uncertain": 30,
}

TREATMENT_INTENT_COUNTS = {
    "curative": 105,
    "palliative": 135,
    "diagnostic/additional workup": 45,
    "best supportive care or uncertain": 15,
}

EXPLICIT_ECOG_COUNTS = {0: 36, 1: 84, 2: 60, 3: 48, 4: 12}

TNM_RE = re.compile(
    r"\b(?:y?[cp])?T(?:is|[0-4](?:mi|[abc])?|x)N(?:[0-3](?:[ab])?|x)M(?:0|1a|1b|1c[12]?|x)\b"
)
PERSON_ID_PATTERNS = [
    re.compile(r"\b\d{6}[-+A]\d{3}[0-9A-FHJ-NPR-Y]\b", re.IGNORECASE),
    re.compile(r"\b\d{6}[- ]?\d{4}\b"),
    re.compile(r"\b\d{10,12}\b"),
    re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b"),
    re.compile(
        r"\b(?:MRN|HETU|personnummer|fødselsnummer|fodselsnummer|CPR|kennitala|hospital number)\b",
        re.IGNORECASE,
    ),
]
NAME_HINT_RE = re.compile(
    r"\b(?:patient name|potilaan nimi|personnamn|navn|kennitala|henkilötunnus)\b", re.IGNORECASE
)


class ValidationError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.rstrip("\n")
            if not line:
                fail(f"{path}:{line_no}: blank line")
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                fail(f"{path}:{line_no}: invalid JSON: {exc}")
    return rows


def validate_row_contract(row: dict, expected_lang: str, file_path: Path, row_index: int) -> None:
    """Delegate the row schema + semantic invariants to the shared model contract."""
    errors = validate_row(row)
    if errors:
        fail(f"{file_path}:{row_index}: {errors[0]}")
    if row.get("language") != expected_lang:
        fail(f"{file_path}:{row_index}: language mismatch (file is {expected_lang})")


def validate_identifier_hygiene(row: dict, file_path: Path, row_index: int) -> None:
    note = row["note_text"]
    for pattern in PERSON_ID_PATTERNS:
        if pattern.search(note):
            fail(f"{file_path}:{row_index}: possible real identifier/date pattern in note_text")
    if NAME_HINT_RE.search(note):
        fail(f"{file_path}:{row_index}: possible name/identifier label in note_text")


def validate_current_tnm_marker(row: dict, file_path: Path, row_index: int) -> None:
    """Note convention: a resolved TNM among several must be tagged 'current TNM <value>'."""
    expected = row["expected_output"]["tnm"]
    value = expected.get("value")
    if value is None:
        return
    note = row["note_text"]
    tnm_values = set(TNM_RE.findall(note))
    if value not in tnm_values:
        fail(f"{file_path}:{row_index}: extracted TNM value is absent from note_text")
    if len(tnm_values) > 1 and f"current TNM {value}" not in note:
        fail(f"{file_path}:{row_index}: multiple TNMs resolved without explicit current TNM marker")


def validate_case_group(rows: list[dict], file_path: Path) -> None:
    if len(rows) != 900:
        fail(f"{file_path}: expected 900 rows, found {len(rows)}")

    by_case = defaultdict(list)
    for row in rows:
        by_case[row["case_id"]].append(row)
    if len(by_case) != 300:
        fail(f"{file_path}: expected 300 unique cases, found {len(by_case)}")

    category_counts: Counter = Counter()
    histology_counts: Counter = Counter()
    treatment_counts: Counter = Counter()
    explicit_ecog_counts: Counter = Counter()
    split_counts: Counter = Counter()

    for case_id, case_rows in by_case.items():
        if len(case_rows) != 3:
            fail(f"{file_path}: {case_id} has {len(case_rows)} rows, expected 3")
        formats = {row["documentation_format"] for row in case_rows}
        if formats != DOCUMENTATION_FORMATS:
            fail(f"{file_path}: {case_id} formats are {sorted(formats)}")
        splits = {row["split_hint"] for row in case_rows}
        if len(splits) != 1:
            fail(f"{file_path}: {case_id} split leakage across formats: {sorted(splits)}")
        categories = {row["case_category"] for row in case_rows}
        if len(categories) != 1:
            fail(f"{file_path}: {case_id} category mismatch across formats")

        representative = case_rows[0]
        category_counts[representative["case_category"]] += 1
        histology_counts[representative["ground_truth"]["histology"]] += 1
        treatment_counts[representative["ground_truth"]["treatment_intent"]] += 1
        if representative["ground_truth"]["ecog_status"] == "explicit":
            explicit_ecog_counts[representative["ground_truth"]["ecog_ps"]] += 1
        split_counts[next(iter(splits))] += 1

    if dict(category_counts) != CASE_CATEGORY_COUNTS:
        fail(f"{file_path}: category counts mismatch: {dict(category_counts)}")
    if dict(histology_counts) != HISTOLOGY_COUNTS:
        fail(f"{file_path}: histology counts mismatch: {dict(histology_counts)}")
    if dict(treatment_counts) != TREATMENT_INTENT_COUNTS:
        fail(f"{file_path}: treatment intent counts mismatch: {dict(treatment_counts)}")
    if dict(explicit_ecog_counts) != EXPLICIT_ECOG_COUNTS:
        fail(f"{file_path}: explicit ECOG counts mismatch: {dict(explicit_ecog_counts)}")
    if split_counts != Counter({"train": 210, "dev": 45, "test": 45}):
        fail(f"{file_path}: split counts mismatch: {dict(split_counts)}")


def validate_language_file(root: Path, lang: str) -> list[dict]:
    file_path = root / "data" / f"synthetic_mdt_{lang}.jsonl"
    if not file_path.exists():
        fail(f"Missing file: {file_path}")
    rows = read_jsonl(file_path)
    for row_index, row in enumerate(rows, start=1):
        validate_row_contract(row, lang, file_path, row_index)
        validate_identifier_hygiene(row, file_path, row_index)
        validate_current_tnm_marker(row, file_path, row_index)
    validate_case_group(rows, file_path)
    return rows


def validate_static_files(root: Path) -> None:
    for relative in ["README.md", "manifest.json", "docs/field_definitions.md", "docs/annotation_rules.md"]:
        if not (root / relative).exists():
            fail(f"Missing static file: {root / relative}")
    # The row schema is the repo-canonical contract, not a copy under this dataset directory.
    schema = _REPO_ROOT / "corpus" / "schema" / "synthetic_case.schema.json"
    if not schema.exists():
        fail(f"Missing canonical schema: {schema}")

    with (root / "manifest.json").open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    expected_manifest = {
        "dataset_version": DATASET_VERSION,
        "synthetic_only": True,
        "no_real_patients": True,
        "languages": LANGUAGES,
        "cases_per_language": 300,
        "documentation_formats": ["free_text", "structured_mini", "structured_v3_1"],
        "records_per_language": 900,
        "total_cases": 1800,
        "total_records": 5400,
        "primary_fields": ["mdt_discussed", "ecog_ps", "tnm"],
        "split_policy": "case_level",
        "leakage_prevention": "All documentation formats for a case_id share the same split_hint.",
        "intended_use": (
            "Research, extractor benchmarking, validation-layer testing and "
            "registry-readiness simulation."
        ),
        "not_for_clinical_use": True,
    }
    for key, value in expected_manifest.items():
        if manifest.get(key) != value:
            fail(f"manifest.json field {key!r} mismatch")


def main() -> None:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    validate_static_files(root)
    all_rows = []
    for lang in LANGUAGES:
        all_rows.extend(validate_language_file(root, lang))
    if len(all_rows) != 5400:
        fail(f"expected 5400 total records, found {len(all_rows)}")
    print(f"Validation passed: {len(all_rows)} records across {len(LANGUAGES)} languages")


if __name__ == "__main__":
    try:
        main()
    except ValidationError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
