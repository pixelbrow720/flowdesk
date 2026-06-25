# Single-VPS deploy checklist — FlowDesk backend (beta)

**Audience:** whoever provisions + owns the VPS (the backend lives in the
FlowDesk repo, separate from the flowjob.id frontend on Vercel).
**Scope:** the beta-safe, historical-replay backend on ONE Docker host behind a
Caddy TLS proxy. This is the practical companion to the environment-agnostic
`docs/ops/deploy-runbook.md` (which is written k8s-style). For the live-feed arm
procedure, defer to that runbook §5 — **live stays OFF for beta.**

The artifacts this checklist drives (all additive, already in the repo):
- `docker-compose.yml` — base stack (api + worker + redis + timescale). API,
  Redis, and Postgres host ports are bound to `127.0.0.1` only.
- `infra/docker-compose.prod.yml` — prod overlay: `restart: unless-stopped` +
  a Caddy TLS reverse proxy (the ONLY public entrypoint, 80/443).
- `infra/Caddyfile` — automatic Let's Encrypt + WebSocket pass-through.
- `scripts/vps_bootstrap.sh` — one-shot installer (Docker, ufw, build, verify).

---

## 0. What you (the human) must provide

These cannot be automated — they cost money / are secrets / are external:

- [ ] **A VPS.** 2 vCPU / 4 GB RAM / 40 GB disk is comfortable for beta
  (e.g. Hetzner CPX21/CPX31, ~EUR 8-15/mo). Ubuntu 22.04 or 24.04 LTS.
- [ ] **A domain/subdomain** for the API, e.g. `api.flowdesk.flowjob.id`.
- [ ] **A DNS A record** pointing that name at the VPS public IP (do this
  FIRST — Caddy needs it resolving to issue the TLS cert).
- [ ] **Discord OAuth app** credentials (client id + secret) and the guild +
  DESK role snowflakes.
- [ ] **Session secret**: `openssl rand -hex 32`.
- [ ] **Cached Databento data** in `./data/cache/` (the historical replay
  source). Without it the worker idles — see `docs/ops/deploy-runbook.md` §7.

## 1. First-boot sequence

```bash
# On the VPS, as a sudo-capable user:
git clone <flowdesk-repo-url> flowdesk && cd flowdesk
cp .env.example .env
# Edit .env — fill in everything in section 2 below. THEN:
bash scripts/vps_bootstrap.sh
```

The script installs Docker, enables it on boot, configures ufw (22/80/443
only), builds + starts the stack via the prod overlay, and verifies
`/healthz` + the worker boot line. It contains no secrets and is idempotent.

## 2. .env keys for a public deploy

Start from `.env.example`, then ensure these are set correctly for production
(the script fails fast if the obvious placeholders are left in):

| Key | Production value |
|-----|------------------|
| `SESSION_SECRET` | `openssl rand -hex 32` output |
| `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` | from the Discord OAuth app |
| `DISCORD_GUILD_ID` | Flowjob.id guild snowflake |
| `DISCORD_DESK_ROLE_ID` | DESK role snowflake |
| `CORS_ORIGINS` | `https://flowjob.id` (the site that embeds the terminal) |
| `PUBLIC_BASE_URL` | `https://api.flowdesk.flowjob.id` |
| `COOKIE_INSECURE` | `0` — MUST be 0 in prod (cookies require HTTPS) |
| `FEED_MODE` | `historical` (do not change for beta) |
| `LIVE_FEED_ARMED` | leave UNSET |
| `FLOWDESK_API_DOMAIN` | `api.flowdesk.flowjob.id` (Caddy TLS host) |
| `FLOWDESK_TLS_EMAIL` | your email (Let's Encrypt expiry notices) |

Datastore URLs (`REDIS_URL`, `TIMESCALE_DSN`) are wired to the compose service
names inside the compose files — you do NOT set those in `.env` for this
single-host layout.

## 3. Post-deploy verification (from your laptop, not the VPS)

- [ ] `curl https://api.flowdesk.flowjob.id/healthz` → `{"status":"ok"}` over a
  valid TLS cert (no cert warning).
- [ ] `docker compose -f docker-compose.yml -f infra/docker-compose.prod.yml ps`
  on the VPS shows api **healthy**, redis/timescale **healthy**, worker + caddy
  **running**.
- [ ] Worker log shows `feed_mode=historical live_armed=False`.
- [ ] From the VPS, confirm the datastores are NOT public:
  `ss -ltn | grep -E ':6379|:5432|:8000'` → each must show `127.0.0.1`, never
  `0.0.0.0`.

## 4. Wire the frontend (Iqbal, on Vercel)

Once the API is green over HTTPS:

- [ ] Set `NEXT_PUBLIC_API_BASE_URL=https://api.flowdesk.flowjob.id` in the
  Vercel project env.
- [ ] Confirm `CORS_ORIGINS` on the backend includes the exact Vercel origin
  (`https://flowjob.id`).
- [ ] Redeploy the frontend. A logged-in DESK user opening `/dashboard/app`
  should see live REST + WS frames (the "24421357" axis glitch disappears once
  real snapshots arrive).

## 5. Day-2 operations

- **Update backend code:** `git pull` on the VPS, then
  `docker compose -f docker-compose.yml -f infra/docker-compose.prod.yml up -d --build`.
- **Logs:** `... logs -f api` / `... logs -f worker`.
- **Restart after reboot:** automatic (`restart: unless-stopped` + Docker
  enabled on boot). Nothing to do.
- **Backups / retention / incident triage:** `docs/ops/deploy-runbook.md`
  §7-§8.
- **Arming the live feed:** NOT in beta. `docs/ops/deploy-runbook.md` §5.

## 6. Cost snapshot (for budgeting)

| Item | Rough monthly |
|------|---------------|
| VPS (2 vCPU / 4 GB) | EUR 8-15 |
| Domain | amortized, ~USD 1-2 |
| TLS (Let's Encrypt via Caddy) | free |
| Databento (historical, already cached for beta) | no incremental cost while on cached replay |

Live Databento streaming is a separate paid decision deferred past beta.
