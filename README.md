# InterOpera Assessment

InterOpera is a deterministic, graph-traceable reporting pipeline for the fictional
Meridian Fixed Income Fund. It ingests the supplied guidelines PDF and holdings CSV,
computes 13 report figures through an explicit property-graph read port, verifies every
figure's data/policy/config lineage, fills the supplied workbook, reconciles Firm A, and
records an append-only hash-chained audit trail. Firm B uses the same engine with a
different validated YAML configuration.

## Run

The complete offline demonstration requires Docker only:

```bash
docker compose up --build --abort-on-container-exit
```

It runs both firms, strictly reconciles Firm A, independently validates Firm B's changed
figures, verifies traces and audit chains, and writes artifacts under `output/<run-id>/`.
No LLM key is required. The source files under `sample_docs/` were extracted unchanged
from `reference/sample_docs.zip` and are never modified by the pipeline.

For a local Python 3.12 environment:

```bash
python -m pip install -e '.[dev]'
python -m interopera.cli demo
pytest -q
```

Useful commands include:

```bash
python -m interopera.cli graph validate
python -m interopera.cli graph query --name duration-breach-route
python -m interopera.cli audit verify --run-id <sha256:...>
python -m interopera.cli trace --run-id <sha256:...> --figure aggregate_non_ig_exposure
```

## Architecture

The modular monolith uses immutable Pydantic models, `Decimal`, a canonical JSON
directed property multigraph, openpyxl, and SQLite. The calculation engine accepts only
`GraphRepository`, the graph read port; it cannot import document readers, answer keys,
LLMs, audit storage, or exporters. Approved policy extraction is committed under
`approved_graph/` and tied to the exact guideline and canonical graph hashes.

The answer key is loaded only after canonical figures have been written and hashed.
Narrative is disabled by default; the optional boundary accepts words and approved
placeholders only, with deterministic substitution and numeric-token attribution.

See [process and audit events](docs/01_flow_and_audit_events.md),
[architecture](docs/02_architecture.md), and [the decision RFC](docs/03_rfc.md).

