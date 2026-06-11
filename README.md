# FlowDesk

**Real-time 0DTE GEX/DEX options terminal for /ES & /NQ** (CME futures options,
Databento GLBX.MDP3, Black-76).

A Python compute engine prices the option chain and emits one canonical
`Snapshot` per instrument per minute; a FastAPI service serves snapshots over
REST/WebSocket behind Discord-role auth; a Next.js app renders the heatmap and
exposure profiles.

## Documentation

All documentation lives in **[`docs/`](docs/README.md)**. Start there.

- **AI agents / Claude Code:** read [`AGENTS.md`](AGENTS.md) first.
- **Architecture:** [`docs/01-architecture.md`](docs/01-architecture.md)
- **The locked contract:** [`docs/02-locked-contract.md`](docs/02-locked-contract.md)
- **Status & gaps (honest):** [`docs/08-status-and-gaps.md`](docs/08-status-and-gaps.md)

## Quick start

```bash
# TS workspaces
pnpm install
pnpm dev:web                      # Next.js dev on :3000

# Engine
cd services/engine && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" && pytest

# API (install engine editable first)
cd services/api && pip install -e ../engine && pip install -e ".[dev]"
uvicorn api.main:app --reload --port 8000 --app-dir src
```

Monorepo layout, commands, environment, and the acceptance gate are documented in
[`docs/`](docs/README.md).
