# RFC: deterministic graph-traceable reporting

## Summary and context

Adopt a Python modular monolith with an in-process directed property graph, immutable
validated models, Decimal calculations, canonical JSON, approved extraction fixtures,
post-computation reconciliation, an optional placeholder-only narrative boundary, and
SQLite append-only evidence.

## Goals, non-goals, and constraints

Goals are deterministic figures, exact source lineage, Firm A equality, config-only Firm
B behavior, fail-closed traces, and tamper-evident audit. A web UI, distributed services,
live risk data, and production identity/retention infrastructure are non-goals. Source
documents are authoritative; answer keys validate but never compute.

## Decision

A modular monolith keeps the assessment runnable and makes dependency rules testable;
microservices would add failure modes without an independent scaling need. An explicit
in-process property graph with canonical JSON provides real traversals, multiedges, stable
IDs, easy review, and reliable Docker startup; Neo4j would add operational dependency.

Policy extraction remains untrusted until a human-approved graph hash matches the exact
PDF and schema/extractor versions. Decimal-from-string and canonical sorted JSON prevent
float and serialization drift. The engine consumes a graph-only read port so lineage is
architectural rather than an after-the-fact citation list.

A validated config mini-DSL dispatches on generic strategies (membership, rating
transition, issuer/parent grouping, percent/bps format), never firm names. Unsupported
strategies fail validation. Answer keys are loaded only after figure finalization/hash,
so changing them cannot influence computation.

LLM narrative is optional and receives qualitative enums and placeholder names only.
Raw digits, number words, units, unsafe markup, and unknown placeholders fail; numeric
values are inserted deterministically and every final numeric token must match the
insertion ledger. The report does not need narrative, so offline mode skips it.

SQLite update/delete triggers demonstrate append-only application behavior. A canonical
per-run hash chain detects offline payload or ordering tampering. Production would pair
this with WORM storage rather than claiming SQLite alone is immutable.

## Alternatives and consequences

Direct dataframe calculations were rejected because provenance can be omitted. Hardcoded
Firm A/B branches were rejected because method changes would require deployments. Letting
an LLM extract or write numbers was rejected because it weakens determinism and proof.
The chosen design has more graph/provenance code and a required approval fixture, but
makes every number reproducible and auditable.

## Security and production hardening

Add authenticated approvals, RBAC, signed graph/config releases, KMS keys, encryption,
WORM retention, schema migrations, centralized telemetry, sandboxed parsing, DLP, retry
and idempotency controls, independent NAV, corporate actions, backups, vulnerability
scanning, and governed model/config versions.

## Test strategy and open questions

Unit tests cover Decimal formatting/status, ratings, config rejection, graph invariants,
firewall attacks, and audit immutability. Integration tests cover both firms, exact Firm A
workbook reconciliation, replay hashes, answer-key isolation, traces, missing parents,
template preservation, and the no-key demo. Open production questions include approval
authority, canonical issuer mastering, independent NAV, and signed retention policy.

