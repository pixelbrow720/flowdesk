# flowdesk-api

Python 3.11 + FastAPI API/WS service for FlowDesk.

This package is a **skeleton** in this task. It exposes a single endpoint:

- `GET /api/health` -> `{ "status": "ok" }`

Later phases add the full contract from PRD #8 (`/api/instruments`,
`/api/snapshot/latest`, `/api/replay*`, Discord OAuth routes, `/api/me`,
and the `/ws` WebSocket), plus DESK gating.

## Pinned dependencies

| Package | Version |
| --- | --- |
| fastapi | 0.112.2 |
| uvicorn[standard] | 0.30.6 |
| pydantic | 2.8.2 |
| ruff (dev) | 0.5.7 |
| mypy (dev) | 1.11.1 |

## Local setup & run

```bash
cd services/api
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run the dev server (http://localhost:8000)
uvicorn api.main:app --reload --port 8000 --app-dir src
```

Then verify:

```bash
curl http://localhost:8000/api/health
# {"status":"ok"}
```

## Quality gates

```bash
ruff check .   # lint
mypy           # strict type-check
```
