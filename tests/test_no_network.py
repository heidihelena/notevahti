"""Local-first guarantee: the validation core makes no network connections.

We disable socket creation entirely, then run a full validate_field (provenance, independence,
validity, agreement, audit). If anything in the core tried to open a socket, this test fails.
"""

import socket

import pytest

from notevahti.audit import AuditLog
from notevahti.validate import validate_field
from notevahti.types import FieldType, Lineage, Signal, SignalKind


@pytest.fixture
def no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network access attempted by the validation core")

    monkeypatch.setattr(socket, "socket", _blocked)
    # also block the lower-level connection creator
    monkeypatch.setattr(socket, "create_connection", _blocked)
    yield


def test_validate_field_makes_no_network_calls(no_network, tmp_path):
    log = AuditLog(str(tmp_path / "audit.jsonl"))
    rec = validate_field(
        "cT2aN0M0",
        "Clinical stage cT2a N0 M0. Plan: SABR.",
        field_type=FieldType.STAGING,
        value_lineage=Lineage(source_id="n1", model_id="m"),
        anchors=[Signal("cT2aN0M0", Lineage(human_id="B"), SignalKind.INDEPENDENT_HUMAN)],
        reference="cT2aN0M0",
        audit_log=log,
        record_id="r1",
        timestamp="2026-06-27T00:00:00Z",
        actor="A",
    )
    assert rec.audit is not None
    ok, _ = log.verify()
    assert ok


def test_core_modules_do_not_import_network_libs():
    # The core must not pull in network stacks at import time.
    import importlib
    import sys

    for mod in ["notevahti.provenance", "notevahti.validity", "notevahti.independence",
                "notevahti.agreement", "notevahti.audit", "notevahti.validate", "notevahti.types"]:
        importlib.import_module(mod)
    forbidden = {"urllib.request", "http.client", "requests", "httpx", "aiohttp"}
    assert forbidden.isdisjoint(sys.modules.keys()), (
        f"core imported a network library: {forbidden & set(sys.modules)}"
    )
