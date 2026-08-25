# Process, gates, and audit events

## AS-IS and TO-BE flow

The manual AS-IS workflow reads guidelines, filters a spreadsheet, calculates figures,
copies values to a report, and reviews them. It is difficult to replay because source
interpretation, transformations, rounding, and reviewer decisions are not linked.

The TO-BE flow registers and hashes sources, deterministically chunks the PDF, reuses an
approved graph only on exact hash match, parses holdings strictly, validates one unified
graph, computes through graph traversals, verifies every trace, serializes canonical
figures, performs post-computation reconciliation, applies the optional narrative
firewall, exports a copied template, and verifies the audit chain.

Human review is required for a new source hash, extractor/schema version, unresolved
reference, or low-confidence candidate. Readable known source types, valid strict CSV
rows, a matching approved graph, complete graph invariants, and resolvable traces pass
automatically. Missing approval, invalid holdings, broken provenance, or untraceable
figures stop export. Reconciliation writes diagnostics and becomes blocking only in
strict mode. Narrative failure discards narrative and fails a narrative-enabled run.

Retries are replay-safe: the run identity derives from inputs/config/graph/software and
formula versions. Deterministic artifacts are replaced with identical content; audit
events append with new contiguous sequence numbers and never mutate earlier evidence.

## Audit catalogue

| Event | Trigger/evidence | Retention metadata |
|---|---|---|
| RUN_STARTED | versions and run identity | 7 years |
| SOURCE_REGISTERED | file type, size, SHA-256 | 7 years |
| SOURCE_CHUNKED | algorithm, page-aware chunk IDs/hashes | 7 years |
| GRAPH_CANDIDATE_CREATED | extractor/model/confidence when used | 7 years |
| GRAPH_VALIDATION_COMPLETED | graph hash, checks, errors | 7 years |
| GRAPH_APPROVAL_REUSED / GRAPH_APPROVED / GRAPH_REJECTED | reviewer decision and hashes | 7 years |
| HOLDINGS_INGESTED | source hash, row count, NAV diagnostic | 7 years |
| CONFIG_LOADED / CONFIG_CHANGED | firm/config hashes and actor | 7 years |
| FIGURE_COMPUTED / FIGURE_ERROR | formula, ordered inputs, raw/display/status or error | 7 years |
| TRACE_VERIFIED | figure and canonical trace hash | 7 years |
| RECONCILIATION_COMPLETED | answer-key hash and row results | 7 years |
| NARRATIVE_REQUESTED | provider/model and qualitative request hash | 7 years |
| NARRATIVE_FIREWALL_COMPLETED | scans, insertion ledger, attribution | 7 years |
| REPORT_EXPORTED | template/report/figure hashes | 10 years |
| RUN_COMPLETED / RUN_FAILED | summaries, artifacts or failed stage | 7 years |

SQLite triggers reject direct UPDATE and DELETE. Per-run hashes chain the canonical
event payload, type, sequence, run ID, and previous hash. Timestamps are observational
metadata and do not allocate sequence.

