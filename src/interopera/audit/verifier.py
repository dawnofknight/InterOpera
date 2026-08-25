from __future__ import annotations

from interopera.audit.store import ZERO_HASH, AuditStore, calculate_event_hash
from interopera.errors import AuditChainInvalid


def verify_chain(store: AuditStore, run_id: str) -> str:
    previous = ZERO_HASH
    events = store.events(run_id)
    if not events:
        raise AuditChainInvalid("Audit run contains no events", entity_id=run_id)
    for expected_sequence, event in enumerate(events, start=1):
        if event["sequence"] != expected_sequence or event["previous_hash"] != previous:
            raise AuditChainInvalid("Audit sequence or previous hash is invalid", entity_id=run_id)
        calculated = calculate_event_hash(previous, run_id, expected_sequence,
                                          str(event["event_type"]), str(event["payload_json"]))
        if calculated != event["event_hash"]:
            raise AuditChainInvalid("Audit event hash is invalid", entity_id=run_id)
        previous = str(event["event_hash"])
    return previous

