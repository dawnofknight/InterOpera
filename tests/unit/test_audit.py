from __future__ import annotations

import sqlite3

import pytest

from interopera.audit.store import AuditStore
from interopera.audit.verifier import verify_chain


def test_audit_chain_and_append_only_triggers(tmp_path) -> None:
    path = tmp_path / "audit.sqlite3"
    store = AuditStore(path)
    store.append("run:test", "RUN_STARTED", {"version": "1"})
    head = store.append("run:test", "RUN_COMPLETED", {"result": "PASS"})
    assert verify_chain(store, "run:test") == head
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.connection.execute("UPDATE audit_events SET payload_json='{}'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.connection.execute("DELETE FROM audit_events")
    store.close()

