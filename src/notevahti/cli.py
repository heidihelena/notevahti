"""Local CLI: ``notevahti validate <items.json>`` — a thin wrapper over the core.

Reads a JSON array of field inputs, validates them (optionally writing an audit log), and prints a
JSON result to stdout. Offline; the only I/O is reading the input file and (optionally) the audit
log. Boundary: this produces validation evidence for human review, not a clinical recommendation.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import __version__
from .audit import AuditLog
from .batch import validate_batch
from .types import Agreement, FieldType, Lineage, Signal, SignalKind


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

    args = parser.parse_args(argv)

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
