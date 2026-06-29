"""Local CLI for NoteVahti.

``notevahti validate <items.json>`` — validate already-extracted field inputs.
``notevahti extract-validate <input.json>`` — run the reference rule extractor, then validate and
route each proposed value end-to-end.

Offline; the only I/O is reading the input file and (optionally) writing an audit log. Boundary:
this produces validation evidence for human review, not a clinical recommendation.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import __version__
from .analytics.registry_yield import is_registry_ready
from .audit import AuditLog, audit_payload
from .batch import validate_batch
from .extractors.rules import MODEL_ID, RuleBasedExtractor, rules_lineage
from .routing import route_validation
from .types import Agreement, FieldSpec, FieldType, Lineage, Signal, SignalKind
from .validate import validate_field


def _lineage(d: dict[str, Any] | None) -> Lineage:
    d = d or {}
    return Lineage(
        source_id=d.get("source_id"), model_id=d.get("model_id"), human_id=d.get("human_id")
    )


def _signal(d: dict[str, Any]) -> Signal:
    kind = d.get("kind", "other")
    return Signal(value=d["value"], lineage=_lineage(d.get("lineage")), kind=SignalKind(kind))


def _item_to_kwargs(
    item: dict[str, Any], default_field_type: FieldType, threshold: float
) -> dict[str, Any]:
    kw: dict[str, Any] = {
        "value": item["value"],
        "note": item["note"],
        "field_type": FieldType(item.get("field_type", default_field_type.value)),
        "review_threshold": item.get("review_threshold", threshold),
    }
    if "field_name" in item:
        kw["field_name"] = item["field_name"]
    if item.get("claimed_span") is not None:
        s = item["claimed_span"]
        kw["claimed_span"] = (int(s[0]), int(s[1]))
    if "value_lineage" in item:
        kw["value_lineage"] = _lineage(item["value_lineage"])
    if "anchors" in item:
        kw["anchors"] = [_signal(a) for a in item["anchors"]]
    if item.get("reference") is not None:
        kw["reference"] = item["reference"]
    for key in ("record_id", "timestamp", "actor", "retain_text"):
        if key in item:
            kw[key] = item[key]
    return kw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="notevahti", description=__doc__)
    parser.add_argument("--version", action="version", version=f"notevahti {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="validate a JSON array of field inputs")
    v.add_argument("items", help="path to a JSON file containing an array of field inputs")
    v.add_argument("--field-type", default="text", choices=[t.value for t in FieldType])
    v.add_argument("--threshold", type=float, default=0.80)
    v.add_argument("--audit", help="path to an append-only JSONL audit log to write")
    v.add_argument("--out", help="write JSON result here instead of stdout")

    ev = sub.add_parser(
        "extract-validate", help="run the reference extractor, then validate and route each value"
    )
    ev.add_argument("input", help="JSON array of {record_id, note, fields: [names]}")
    ev.add_argument("--extractor", default="rules", choices=["rules"])
    ev.add_argument("--threshold", type=float, default=0.80)
    ev.add_argument("--audit", help="path to an append-only JSONL audit log to write")
    ev.add_argument("--out", help="write JSON result here instead of stdout")

    args = parser.parse_args(argv)

    if args.command == "extract-validate":
        return _run_extract_validate(args, parser)

    if args.command == "validate":
        with open(args.items, encoding="utf-8") as fh:
            items = json.load(fh)
        if not isinstance(items, list):
            parser.error("input JSON must be an array of field inputs")

        default_ft = FieldType(args.field_type)
        kwargs_list = [_item_to_kwargs(it, default_ft, args.threshold) for it in items]
        audit_log = AuditLog(args.audit) if args.audit else None
        result = validate_batch(kwargs_list, field_type=default_ft, audit_log=audit_log)

        out = {
            "notevahti_version": __version__,
            "summary": {
                "n": len(result.records),
                "flagged_for_review": len(result.flagged()),
            },
            "agreement": _agreement_dict(result.agreement),
            "records": [r.to_dict() for r in result.records],
        }
        text = json.dumps(out, indent=2, ensure_ascii=False)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        else:
            sys.stdout.write(text + "\n")
        return 0

    return 1


def _write(text: str, out: str | None) -> None:
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")


def _run_extract_validate(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        with open(args.input, encoding="utf-8") as fh:
            records = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"could not read input JSON: {exc}")
    if not isinstance(records, list):
        parser.error("input JSON must be an array of {record_id, note, fields}")

    extractor = RuleBasedExtractor()  # only "rules" is supported (choices enforce it)
    audit_log = AuditLog(args.audit) if args.audit else None
    out_records: list[dict[str, Any]] = []

    for i, rec in enumerate(records):
        if not isinstance(rec, dict) or "note" not in rec or "fields" not in rec:
            parser.error(f"record {i} must have 'note' and 'fields'")
        record_id = str(rec.get("record_id", f"rec-{i:04d}"))
        note = rec["note"]
        fields_out = {
            field_name: _process_field(extractor, note, field_name, record_id, args, audit_log)
            for field_name in rec["fields"]
        }
        out_records.append({"record_id": record_id, "fields": fields_out})

    out = {"extractor": args.extractor, "notevahti_version": __version__, "records": out_records}
    _write(json.dumps(out, indent=2, ensure_ascii=False), args.out)
    return 0


def _process_field(
    extractor: RuleBasedExtractor,
    note: str,
    field_name: str,
    record_id: str,
    args: argparse.Namespace,
    audit_log: AuditLog | None,
) -> dict[str, Any]:
    """Extract, validate and route one field of one record into a JSON-ready entry."""
    ftype = extractor.field_type(field_name) or FieldType.TEXT
    cands = extractor.candidates(note, field_name)
    chosen = extractor.extract(note, FieldSpec(name=field_name, field_type=ftype))
    entry: dict[str, Any] = {
        "candidates": [
            {
                "value": c.value,
                "matched_text": c.matched_text,
                "span": list(c.span),
                "negated": c.negated,
            }
            for c in cands
        ],
        "chosen": None,
        "validation": None,
        "route": None,
        "registry_ready": None,
    }
    if not chosen.value:
        return entry  # no value (absent or ambiguous): nothing to validate

    entry["chosen"] = {"value": chosen.value, "span": list(chosen.source_span or ())}
    vrec = validate_field(
        chosen.value,
        note,
        field_type=ftype,
        field_name=field_name,
        claimed_span=chosen.source_span,
        value_lineage=rules_lineage(source_id=record_id),
        review_threshold=args.threshold,
    )
    route = route_validation(vrec)
    entry["validation"] = vrec.to_dict()
    entry["route"] = route.to_dict()
    entry["registry_ready"] = is_registry_ready(vrec, min_score=args.threshold)
    if audit_log is not None:
        audit_log.append(
            record_id=f"{record_id}:{field_name}",
            timestamp=_edge_timestamp(),
            actor=f"extract-validate:{MODEL_ID}",
            payload=audit_payload(vrec, note=note, routing=route.to_dict()),
        )
    return entry


def _edge_timestamp() -> str:
    """Wall-clock timestamp for audit entries (the CLI is the edge; the core takes no clock)."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _agreement_dict(agreement: Agreement) -> dict[str, Any]:
    return {
        "status": agreement.status.value,
        "n": agreement.n,
        "accuracy": agreement.accuracy,
        "kappa": agreement.kappa,
        "detail": agreement.detail,
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
