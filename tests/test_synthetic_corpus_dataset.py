"""The committed synthetic_mdt_v1 dataset conforms to the row contract.

Guards the in-repo dataset against drift from notevahti.corpus.validate_row. Offline and pure
(no sockets, no extractor); skips gracefully if the data has been stripped from a checkout.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from notevahti.corpus import validate_row

_DATA = Path(__file__).resolve().parents[1] / "corpus" / "synthetic_mdt_v1" / "data"
_LANGUAGES = ["fi", "sv", "nb", "da", "is", "en"]

pytestmark = pytest.mark.skipif(not _DATA.exists(), reason="synthetic_mdt_v1 data not present")


def _rows(lang: str) -> list[dict]:
    path = _DATA / f"synthetic_mdt_{lang}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.mark.parametrize("lang", _LANGUAGES)
def test_every_row_satisfies_the_contract(lang: str):
    failures: list[str] = []
    rows = _rows(lang)
    assert len(rows) == 900
    for row in rows:
        errs = validate_row(row)
        if errs:
            failures.append(f"{row.get('record_id')}: {errs[0]}")
    assert not failures, failures[:5]


@pytest.mark.parametrize("lang", _LANGUAGES)
def test_case_level_split_has_no_leakage(lang: str):
    by_case: dict[str, set[str]] = {}
    formats: Counter = Counter()
    for row in _rows(lang):
        by_case.setdefault(row["case_id"], set()).add(row["split_hint"])
        formats[row["documentation_format"]] += 1
    assert len(by_case) == 300
    # all three documentation formats present, and one split per case (no leakage)
    assert set(formats) == {"free_text", "structured_mini", "structured_v3_1"}
    assert all(len(splits) == 1 for splits in by_case.values())
