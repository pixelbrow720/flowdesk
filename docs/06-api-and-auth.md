# 06 — API & Auth (`flowdesk-api`)

The API is the transport + control plane. FastAPI app in
`services/api/src/api/`. It depends on `flowdesk-engine` (install editable:
`pip install -e ../engine`).

Per-module deep docs live beside the code:
`src/api/{AUTH_README, FE_AUTH_CONTRACT, REST_README, STATE_README, WORKER_README, WS_README}.md`
and `tests/AUTH_TEST_NOTES.md`. This doc is the map.

## Components

```
main.py            FastAPI app wiring, CORS, router mounts, lifespan
worker.py          per-instrument session state machine + minute tick → engine
session.py         session resolution (date, minute_index, state)
ws.py              WebSocket: subscribe per instrument, push snapshots
state.py           session-state helpers (PREMARKET|LIVE|STALE|CLOSED|HOLIDAY)
auth.py            Discord OAuth flow
auth_session.py    signed session cookies (SESSION_SECRET)
discord_client.py  Discord API client (identify, guilds.members.read)
security.py        guards / dependency injection for protected routes
entitlement.py     guild membership + DESK_ROLE_ID check
models.py          API-side models
errors.py          typed error responses
db/repo.py         Redis (hot snapshot) + Timescale (history) repositories
db/migrations/0001_init.sql   Timescale schema
mocks/             local mock data for running without Databento
```

## The worker

`worker.py` is the heartbeat. For each instrument it advances the session state
machine, resolves time-to-expiry (real wall-clock to 16:00 ET — the engine stays
calendar-free), pulls the chain from the feed adapter, calls
`engine.build_snapshot(...)`, then:

- writes the **latest** Snapshot to **Redis** (hot read path),
- appends to **Timescale** (history / replay),
- broadcasts to subscribed **WebSocket** clients.

## REST (see `REST_README.md`)

Typical surface: latest snapshot per instrument, historical snapshot by
minute/time, and `/api/me` (identity + entitlement for the FE). All data routes
are gated; see `FE_AUTH_CONTRACT.md` for the exact FE↔API auth handshake.

## WebSocket (see `WS_README.md`)

Clients subscribe per instrument and receive each new Snapshot as the worker
produces it. Snapshots are validated against the contract before broadcast.

## Auth (see `AUTH_README.md` + `entitlement.py`)

- **Discord OAuth**, scopes `identify guilds.members.read`.
- A user is entitled iff they are a member of `DISCORD_GUILD_ID` **and** hold
  `DESK_ROLE_ID`.
- Sessions are signed cookies keyed by `SESSION_SECRET`.
- ~75 API tests cover auth, entitlement, state transitions, and serialization;
  `tests/AUTH_TEST_NOTES.md` explains the auth-test rationale.

## Storage

- **Redis** — hot, last-known Snapshot per instrument (fast FE first paint).
- **Timescale** (`TIMESCALE_DSN`) — historical Snapshots for replay; schema in
  `db/migrations/0001_init.sql`.

## Run locally

```bash
cd services/api
pip install -e ../engine && pip install -e ".[dev]"
uvicorn api.main:app --reload --port 8000 --app-dir src
pytest && ruff check . && mypy
```
