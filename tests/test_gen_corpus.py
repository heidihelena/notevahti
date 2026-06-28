"""The synthetic MDT corpus generator: determinism and gold-span integrity.

The corpus is the validation harness's fixture, so its gold spans MUST resolve through NoteVahti's
own provenance check — otherwise the fixture and the tool disagree.
"""

import importlib.util
import json
from pathlib import Path

from notevahti.provenance import verify_span
from notevahti.types import FieldType, ProvenanceStatus

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "gen_corpus.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("gen_corpus", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_generates_all_groups(tmp_path):
    gen = _load_generator()
    manifest = gen.generate(n=4, out_dir=tmp_path)
    # 6 free-text languages + 2 structured English groups
    assert len(manifest["groups"]) == 8
    assert {
        "free_fi",
        "free_sv",
        "free_nb",
        "free_da",
        "free_is",
        "free_en",
        "semistructured_en",
        "structured_en",
    } == set(manifest["groups"])
    assert (tmp_path / "manifest.json").exists()


def test_all_gold_spans_resolve_and_six_fields(tmp_path):
    gen = _load_generator()
    gen.generate(n=8, out_dir=tmp_path)
    checked = 0
    for path in tmp_path.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            assert len(rec["fields"]) == 6, rec["case_id"]
            for f in rec["fields"].values():
                p = verify_span(
                    f["value"],
                    rec["note"],
                    claimed_span=tuple(f["span"]),
                    field_type=FieldType(f["field_type"]),
                )
                assert p.status is ProvenanceStatus.SPAN_FOUND, (rec["case_id"], f)
                assert list(p.matched_span) == f["span"]
                checked += 1
    assert checked == 8 * 8 * 6  # 8 groups * 8 cases * 6 gold fields


def test_no_unrendered_template_tokens(tmp_path):
    gen = _load_generator()
    gen.generate(n=5, out_dir=tmp_path)
    for path in tmp_path.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            assert "{f:" not in line and "}" not in json.loads(line)["note"]


def test_challenges_present_and_resolvable(tmp_path):
    gen = _load_generator()
    gen.generate(n=12, out_dir=tmp_path)
    ft = {
        "clinical_stage": FieldType.STAGING,
        "histology": FieldType.CATEGORICAL,
        "pdl1": FieldType.CATEGORICAL,
    }
    saw_sv = saw_pw = 0
    for path in tmp_path.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            note = rec["note"]
            ch = rec["challenges"]
            for fn, val in ch["surface_variant"].items():
                p = verify_span(val, note, field_type=ft[fn])
                assert p.status is ProvenanceStatus.SPAN_FOUND, (rec["case_id"], fn, val)
                saw_sv += 1
            for fn, val in ch["present_but_wrong"].items():
                # wrong value, but it IS in the note -> found, and NOT a hallucination
                p = verify_span(val, note, field_type=ft[fn])
                assert p.status is ProvenanceStatus.SPAN_FOUND, (rec["case_id"], fn, val)
                assert p.hallucination_flag is False, (rec["case_id"], fn, val)
                saw_pw += 1
    assert saw_sv > 0 and saw_pw > 0


def test_deterministic(tmp_path):
    gen = _load_generator()
    a, b = tmp_path / "a", tmp_path / "b"
    gen.generate(n=6, out_dir=a)
    gen.generate(n=6, out_dir=b)
    for fa in a.glob("*.jsonl"):
        assert fa.read_bytes() == (b / fa.name).read_bytes(), fa.name
