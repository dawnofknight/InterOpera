"""Stable application errors and exit-code mapping."""

from __future__ import annotations


class InterOperaError(Exception):
    code = "INTEROPERA_ERROR"
    exit_code = 8

    def __init__(self, message: str, *, entity_id: str | None = None) -> None:
        self.entity_id = entity_id
        super().__init__(f"{message}{f' [{entity_id}]' if entity_id else ''}")


class ConfigSchemaError(InterOperaError):
    code = "CONFIG_SCHEMA_ERROR"
    exit_code = 2


class SourceError(InterOperaError):
    code = "SOURCE_HASH_MISMATCH"
    exit_code = 3


class GraphApprovalRequired(InterOperaError):
    code = "GRAPH_APPROVAL_REQUIRED"
    exit_code = 3


class HoldingValidationError(InterOperaError):
    code = "HOLDING_VALIDATION_ERROR"
    exit_code = 3


class GraphSchemaError(InterOperaError):
    code = "GRAPH_SCHEMA_ERROR"
    exit_code = 4


class TraceabilityError(InterOperaError):
    code = "TRACEABILITY_ERROR"
    exit_code = 4


class ComputationError(InterOperaError):
    code = "COMPUTATION_ERROR"
    exit_code = 5


class ConfiguredGroupKeyMissing(ComputationError):
    code = "CONFIGURED_GROUP_KEY_MISSING"


class ZeroNav(ComputationError):
    code = "ZERO_NAV"


class ReconciliationMismatch(InterOperaError):
    code = "RECONCILIATION_MISMATCH"
    exit_code = 6


class NarrativeFirewallFailed(InterOperaError):
    code = "NARRATIVE_FIREWALL_FAILED"
    exit_code = 7


class AuditChainInvalid(InterOperaError):
    code = "AUDIT_CHAIN_INVALID"
    exit_code = 8

