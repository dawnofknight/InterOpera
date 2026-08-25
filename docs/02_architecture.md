# Architecture

## Context and components

```mermaid
flowchart LR
  PDF[Guidelines PDF] --> ING[Registry and chunking]
  CSV[Holdings CSV] --> ING
  ING --> G[Canonical property graph]
  AP[Approved graph record] --> G
  YAML[Firm YAML] --> G
  G --> E[Decimal computation engine]
  E --> T[Trace verifier]
  T --> J[Canonical figures]
  J --> R[Post-computation reconciliation]
  J --> X[XLSX copy/export]
  ING --> A[(Append-only audit)]
  E --> A
  T --> A
  R --> A
  X --> A
```

```mermaid
flowchart TD
  CLI --> Pipeline
  Pipeline --> SourceAdapters
  Pipeline --> GraphRepository
  Pipeline --> Engine
  Pipeline --> TraceVerifier
  Pipeline --> Reconciler
  Pipeline --> Exporters
  Pipeline --> AuditStore
  Engine --> Domain
  Engine --> GraphReadPort[Graph read port]
```

Dependency direction is `orchestration -> application modules -> domain`. The domain
uses the standard library plus model validation. Computation receives graph reads and a
validated generic strategy config only; it has no PDF, CSV, XLSX, answer-key, narrative,
or audit imports. I/O adapters render values but never recalculate them.

## Unified graph

```mermaid
flowchart LR
  Portfolio -->|HOLDS| Position
  Position -->|BELONGS_TO| AssetClass
  Position -->|ISSUED_BY| Issuer
  Issuer -->|ROLLS_UP_TO| ParentIssuer
  AssetClass -->|CONTRIBUTES_TO| Aggregate
  AssetClass -->|INCLUDED_IN| LiquidityBucket
  AssetClass -->|SUBJECT_TO| LimitRule
  Metric -->|SUBJECT_TO| LimitRule
  LimitRule -->|HAS_BREACH_ACTION| Action
  Action -->|NOTIFIES| Owner
  Position -->|DERIVED_FROM| Chunk
  LimitRule -->|DERIVED_FROM| Chunk
  FirmMethodRule -->|DERIVED_FROM| ConfigChunk
  Chunk -->|PART_OF| SourceDocument
```

Nodes and parallel directed edges have stable IDs and provenance. Canonical persistence
sorts both by ID and excludes observational timestamps. A recorded trace resolves exact
edge IDs rather than searching for a convenient path.

```mermaid
sequenceDiagram
  participant P as Pipeline
  participant G as GraphReadPort
  participant E as Engine
  participant T as Trace verifier
  participant X as Exporter
  P->>G: validated graph + firm methods
  E->>G: positions, membership, rule
  G-->>E: typed facts + graph identities
  E-->>T: figure + exact edge steps
  T->>G: resolve edges and chunks
  T-->>P: trace hash or blocking error
  P->>X: verified display strings
```

Docker runs one Python 3.12 CLI container. Source/approved fixtures are image inputs;
`output/` is mounted for reports and SQLite audit evidence.

