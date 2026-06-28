"""Error-injection mode of the corpus generator (opt-in; notes unchanged)."""

import importlib.util
import json
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "gen_corpus.py"


def _gen():
    spec = importlib.util.spec_from_file_location("gen_corpus", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load(d: Path) -> list[dict]:
    rows: list[dict] = []
    for f in sorted(d.glob("*.jsonl")):
        rows += [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return rows


def test_default_has_no_extractions(tmp_path):
    _gen().generate(n=4, out_dir=tmp_path)
    assert all("extractions" not in r for r in _load(tmp_path))


def test_errors_emit_labelled_extractions(tmp_path):
    gen = _gen()
    gen.generate(n=20, out_dir=tmp_path, error_rate=0.5)
    rows = _load(tmp_path)
    seen_error = seen_correct = 0
    for r in rows:
        assert len(r["extractions"]) == 6
        for ex in r["extractions"]:
            # the label is consistent with the value
            assert ex["is_error"] == (ex["extracted"] != ex["gold"])
            if ex["is_error"]:
                assert ex["error_type"] != "none"
                seen_error += 1
            else:
                assert ex["error_type"] == "none"
                seen_correct += 1
    assert seen_error > 0 and seen_correct > 0


def test_notes_are_byte_identical_regardless_of_error_rate(tmp_path):
    gen = _gen()
    clean, dirty = tmp_path / "clean", tmp_path / "dirty"
    gen.generate(n=10, out_dir=clean)
    gen.generate(n=10, out_dir=dirty, error_rate=0.7)
    by_id_clean = {r["case_id"]: r["note"] for r in _load(clean)}
    for r in _load(dirty):
        assert r["note"] == by_id_clean[r["case_id"]], r["case_id"]


def test_error_injection_is_deterministic(tmp_path):
    gen = _gen()
    a, b = tmp_path / "a", tmp_path / "b"
    gen.generate(n=8, out_dir=a, error_rate=0.5)
    gen.generate(n=8, out_dir=b, error_rate=0.5)
    for fa in a.glob("*.jsonl"):
        assert fa.read_bytes() == (b / fa.name).read_bytes(), fa.name
