from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from interopera.canonical import canonical_bytes, sha256_bytes

ZERO_HASH = "0" * 64


def calculate_event_hash(previous_hash: str, run_id: str, sequence: int,
                         event_type: str, payload_json: str) -> str:
    material = f"{previous_hash}\n{run_id}\n{sequence}\n{event_type}\n{payload_json}".encode()
    return sha256_bytes(material)


class AuditStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path)
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        self.connection.executescript(schema)

    def append(self, run_id: str, event_type: str, payload: Any,
               *, actor_type: str = "system", actor_id: str = "interopera") -> str:
        payload_json = canonical_bytes(payload).decode().rstrip("\n")
        with self.connection:
            row = self.connection.execute(
                "SELECT sequence, event_hash FROM audit_events WHERE run_id=? ORDER BY sequence DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            sequence = int(row[0]) + 1 if row else 1
            previous = str(row[1]) if row else ZERO_HASH
            event_hash = calculate_event_hash(previous, run_id, sequence, event_type, payload_json)
            self.connection.execute(
                "INSERT INTO audit_events(run_id,sequence,event_type,actor_type,actor_id,occurred_at,payload_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?,?,?)",
                (run_id, sequence, event_type, actor_type, actor_id,
                 datetime.now(timezone.utc).isoformat(), payload_json, previous, event_hash),
            )
        return event_hash

    def events(self, run_id: str) -> tuple[dict[str, Any], ...]:
        cursor = self.connection.execute(
            "SELECT sequence,event_type,actor_type,actor_id,occurred_at,payload_json,previous_hash,event_hash FROM audit_events WHERE run_id=? ORDER BY sequence",
            (run_id,),
        )
        return tuple({"sequence": row[0], "event_type": row[1], "actor_type": row[2],
            "actor_id": row[3], "occurred_at": row[4], "payload": json.loads(row[5]),
            "payload_json": row[5], "previous_hash": row[6], "event_hash": row[7]} for row in cursor)

    def close(self) -> None:
        self.connection.close()
