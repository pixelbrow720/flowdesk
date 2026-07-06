# Deploy runbook — FlowDesk backend

**Audience:** the on-call operator deploying or re-arming the backend.
**Companion docs:**
- `docs/architecture/beta-readiness.md` — what landed, what's gated.
- `docs/architecture/live-feed-threat-model.md` — the F1–F7 failure modes
  the LiveAdapter rail defends against.

This runbook deliberately omits credentials, secret values, and the
exact `LIVE_FEED_ARMED` flip procedure for any environment outside
staging — that step lives in the secret-manager-backed operator
notebook, not in the repo.

---

## 1. Environment matrix

| Env | `FEED_MODE` | `LIVE_FEED_ARMED` | Network → Databento | Audience |
|-----|-------------|-------------------|--------------------|----------|
| local dev | `historical` | unset | NEVER | engineers |
| CI | `historical` | unset (set per-test only) | NEVER | tests |
| staging | `historical` | unset by default; can flip with on-caller | gated | beta operators |
| **production / paid beta** | **`historical`** | **unset** | **NEVER** | paying users |

The paid beta image ships with `FEED_MODE=historical` and
`LIVE_FEED_ARMED` deliberately absent. Both env vars are inherited via
the secret manager; neither is baked into the image.

## 2. Required environment variables

The 12-key contract per PRD #8 §10. Every key has a safe default OR
must be populated from the secret manager — none of them live in the
repo.

| Key | Source | Notes |
|-----|--------|-------|
| `SESSION_SECRET` | secret manager | 32-byte random; `openssl rand -hex 32` |
| `DISCORD_CLIENT_ID` | secret manager | OAuth app |
| `DISCORD_CLIENT_SECRET` | secret manager | OAuth app |
| `DISCORD_GUILD_ID` | config | Flowjob.id snowflake |
| `DISCORD_DESK_ROLE_ID` (or `DESK_ROLE_ID`) | config | DESK role snowflake |
| `CORS_ORIGINS` | config | `https://app.flowdesk.id` (production) |
| `PUBLIC_BASE_URL` | config | `https://app.flowdesk.id` (production) |
| `FEED_MODE` | **MUST be `historical`** in beta | the only mode beta users see |
| `LIVE_FEED_ARMED` | **MUST be unset** in beta | flipping requires on-caller + checklist |
| `DATA_DIR` | config | `/data/raw` (cached Databento exports) |
| `DATABENTO_API_KEY` | secret manager | unused while `FEED_MODE=historical`; populated for the eventual live flip |
| `TIMESCALE_DSN` | secret manager | derived snapshots store (90-day retention) |
| `REDIS_URL` | secret manager | per-instrument state + pub/sub |
| `SOFR_RATE` | config | daily; defaults to 0.0531 |
| `QUOTE_SCHEMA` | config | `mbp-1` (default) or `bbo-1m` (cheaper export) |

Operational knobs (Pilihan A locked, all safe defaults):
- `COOKIE_INSECURE` (dev only — must be unset in prod)
- `RATE_LIMIT_*` (defaults safe; tune per-scope only with an SRE pair)
- `WS_HEARTBEAT_S` (default 30)
- `MOCK_ACCESS_STATE` / `MOCK_RECHECK_STATE` (dev/QA only)
- `DISCORD_JOIN_URL` (defaults to BUY_URL)

## 3. Pre-deploy checklist (every deploy, every environment)

Before `apply` / `kubectl rollout restart` / equivalent:

- [ ] Confirm baseline branch is `main` and HEAD matches the intended
  release tag.
- [ ] Engine suite green:
  ```
  cd services/engine && PYTHONPATH=src ../../.venv/Scripts/python.exe -m pytest -q
  ```
  → expect **450 passed** (as of 2026-07-06).
- [ ] API suite green:
  ```
  cd services/api && PYTHONPATH=src:../engine/src ../../.venv/Scripts/python.exe -m pytest -q
  ```
  → expect **116 passed**.
- [ ] No `.env` / `.env.*` (other than `.env.example`) is in `git ls-files`:
  ```
  git ls-files | grep -E '^\.env'    # MUST return only ".env.example"
  ```
- [ ] No live-token shapes leaked:
  ```
  git grep -E 'db-[A-Za-z0-9]{8,}' -- ':!.env.example' ':!docs/'
  ```
  → MUST return 0 lines in code; `.env.example` carries the documented
  `db-xxxxxxxxxxxxxxxxxxxxxxxx` placeholder by design.
- [ ] `FEED_MODE` in the deploy manifest is `historical`. Look at the
  rendered ConfigMap / Secret, not the template.
- [ ] `LIVE_FEED_ARMED` is **NOT** in the rendered ConfigMap / Secret.
  This is enforced by the runbook, not by code — code refuses but the
  refusal must never fire in production.
- [ ] Secret manager has `SESSION_SECRET`, `DISCORD_CLIENT_SECRET`,
  `DATABENTO_API_KEY`, `TIMESCALE_DSN`, `REDIS_URL` populated.
- [ ] On-caller is paged before any production rollout.

## 4. Post-deploy verification

Within 5 minutes of rollout completing:

- [ ] Worker boot log line `flowdesk worker boot: feed_mode=historical
  live_armed=False` is present (this is a `WARNING` so it shows up
  early). If `feed_mode=live` shows up here in production: **HALT**,
  rollback, page the team.
- [ ] `/healthz` returns 200.
- [ ] WS handshake from a logged-in DESK user succeeds; first
  Snapshot frame arrives within 2 minutes.
- [ ] `state="LIVE"` (or `"REPLAY"` outside RTH) in the first
  snapshot. `state="STALE"` for >2 min → investigate.
- [ ] Rate-limit metrics: no spike in 4429 close codes; no spike in
  /me/recheck 429s.

## 5. Live-feed arm procedure (DOES NOT APPLY in beta)

This section is documented for completeness; **DO NOT FOLLOW** during
the paid beta. The beta runs on historical replay only.

When the team eventually decides to flip a single staging environment
to live:

1. Open the live-feed threat model
   (`docs/architecture/live-feed-threat-model.md`) §8 and walk the
   pre-deploy operator checklist line by line.
2. Confirm with the Databento dashboard that the account is in good
   standing.
3. Page the on-caller. The first **30 minutes** of live operation must
   be supervised — no exceptions.
4. Set both env vars in the secret manager:
   - `FEED_MODE=live`
   - `LIVE_FEED_ARMED=1`
5. Roll out and watch the boot log: it MUST say
   `feed_mode=live live_armed=True`. Anything else: rollback.
6. Watch the circuit-breaker metric for 30 min. Expected pattern: 0
   failures. One isolated reconnect with a successful follow-up: OK.
   Two consecutive failures: investigate. ≥5 in 5 min: the breaker
   trips automatically and the worker degrades to `historical` for
   the rest of the process lifetime; do NOT auto-restart — page the
   team.
7. Document the flip in the post-deploy ledger (date, time, on-caller,
   first-30-min observations).

## 6. Rollback procedure

For any non-live-feed regression (auth break, CORS reject loop, WS
disconnect storm, snapshot finiteness reject, etc.):

1. `kubectl rollout undo deploy/api` (or equivalent for the deploy
   tool in use).
2. Confirm the previous-image worker boot log shows the expected
   `feed_mode=historical`.
3. Page the team in the same hour.

For a live-feed regression (breaker tripped, account warning email
arrived, abnormal subscription pattern reported by Databento):

1. **Unset `LIVE_FEED_ARMED` in the secret manager FIRST.**
2. Roll back the deployment.
3. Verify `feed_mode=historical` in the new pod's boot log.
4. Do NOT re-arm until a human-led postmortem identifies the cause.

## 7. Backup / data retention

- Snapshots: TimescaleDB hypertable, 90-day retention via compression
  policy (per PRD #8 §11).
- FluxState: Redis snapshot per tick, TTL 5400s
  (`flowdesk:flux:{instrument}`). Loss → graceful Tier-2 fresh
  accumulator on the next tick.
- Session cookies: HMAC-signed, 7d TTL, no server-side store needed.
- Cached Databento exports (`DATA_DIR=/data/raw`): regenerable via
  `services/engine/scripts/ingest_databento.py`; back up the parquet
  index, not the raw bundles (regenerable).

## 8. Incident triage quick-reference

| Symptom | First thing to check |
|---------|----------------------|
| Users see `state="STALE"` for >2 min | check worker pod logs for FLUX restore errors or feed gap WARNING |
| `/api/me` 401 storm | Discord OAuth app settings; `DISCORD_CLIENT_SECRET` rotated? |
| WS close 4429 storm | rate-limit Redis health; `RATE_LIMIT_*` env tuned too tight? |
| Snapshot reject (zod boundary) | check egress for unexpected NaN/Inf — signals an engine bug, not an ops issue |
| Worker boot fails with `LiveFeedNotArmed` | someone set `FEED_MODE=live` without arming — unset it, rollback |
| Worker boot fails with `LiveFeedNotAvailable` after arming | Databento credential / API contact issue; confirm with the Databento dashboard |
| Repeated arming (crash-loop) | check restart count; the in-process breaker will eventually open and degrade to `historical` |

## 9. Contact

- Backend on-call: see the team rota.
- Databento support: dashboard ticket; do NOT email — the audit trail
  needs to live in their system.
- Discord OAuth issues: app owner in the Discord developer portal.
