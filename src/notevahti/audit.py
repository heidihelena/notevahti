"""Audit: a local, append-only, tamper-evident record (ALCOA++ in spirit).

Each entry is hash-chained to the previous one, so any later edit to a past entry breaks the chain
and is detectable. PHI (note text and matched snippets) is stored as a SHA-256 hash by default;
retaining raw text is an explicit, local opt-in. Determinism: ids, timestamps and actor are supplied
by the caller (no clock in the core); hashing is stdlib ``hashlib``, no network.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Optional

from .types import AuditEntry, ValidationRecord

GENESIS_HASH = "0" * 64


def hash_text(text: str) -> str:
    """SHA-256 hex of UTF-8 text. Used to record PHI without storing it."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_entry_hash(
    record_id: str, timestamp: str, actor: str, prev_hash: str, payload: dict[str, Any]
) -> str:
    """Deterministic hash over everything in the entry except the hash field itself."""
    material = _canonical_json(
        {
            "record_id": record_id,
            "timestamp": timestamp,
            "actor": actor,
            "prev_hash": prev_hash,
            "payload": payload,
        }
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def make_entry(
    record_id: str, timestamp: str, actor: str, prev_hash: str, payload: dict[str, Any]
) -> AuditEntry:
    entry_hash = compute_entry_hash(record_id, timestamp, actor, prev_hash, payload)
    return AuditEntry(
        record_id=record_id,
        timestamp=timestamp,
        actor=actor,
        prev_hash=prev_hash,
        payload=payload,
        entry_hash=entry_hash,
    )


def audit_payload(
    record: ValidationRecord,
    note: Optional[str] = None,
    retain_text: bool = False,
) -> dict[str, Any]:
    """Build a PHI-aware payload from a ValidationRecord.

    The note and any matched snippet are hashed unless ``retain_text`` is set. The registry value and
    span offsets are kept (they are the attributable subject of the audit, and offsets are not text).
    """
    d = record.to_dict()
    prov = d.get("provenance", {})

    matched_text = prov.get("matched_text")
    if matched_text is not None:
        prov["matched_text_sha256"] = hash_text(matched_text)
        if not retain_text:
            prov.pop("matched_text", None)

    if note is not None:
        d["note_sha256"] = hash_text(note)
        if retain_text:
            d["note_text"] = note

    return d


class AuditLog:
    """Append-only JSONL audit log with a verifiable hash chain."""

    def __init__(self, path: str):
        self.path = path

    def last_hash(self) -> str:
        if not os.path.exists(self.path):
            return GENESIS_HASH
        last = None
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    last = line
        if last is None:
            return GENESIS_HASH
        return str(json.loads(last)["entry_hash"])

    def append(
        self, record_id: str, timestamp: str, actor: str, payload: dict[str, Any]
    ) -> AuditEntry:
        prev_hash = self.last_hash()
        entry = make_entry(record_id, timestamp, actor, prev_hash, payload)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(_canonical_json(_entry_to_dict(entry)) + "\n")
        return entry

    def entries(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        out: list[dict[str, Any]] = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def verify(self) -> tuple[bool, str]:
        """Re-hash every entry and check the chain. Returns (ok, message)."""
        prev = GENESIS_HASH
        entries = self.entries()
        for i, e in enumerate(entries):
            recomputed = compute_entry_hash(
                e["record_id"], e["timestamp"], e["actor"], e["prev_hash"], e["payload"]
            )
            if recomputed != e["entry_hash"]:
                return False, f"entry {i} (record_id={e.get('record_id')!r}) hash mismatch — tampered"
            if e["prev_hash"] != prev:
                return False, f"entry {i} (record_id={e.get('record_id')!r}) broken chain link"
            prev = e["entry_hash"]
        return True, f"chain ok ({len(entries)} entries)"


def _entry_to_dict(entry: AuditEntry) -> dict[str, Any]:
    return {
        "record_id": entry.record_id,
        "timestamp": entry.timestamp,
        "actor": entry.actor,
        "prev_hash": entry.prev_hash,
        "payload": entry.payload,
        "entry_hash": entry.entry_hash,
    }
