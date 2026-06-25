# FlowDesk Beta Readiness — Deep Dive Audit & Master Checklist

> **PURPOSE**: This is the **single persistent reference** for any AI agent working on FlowDesk
> beta readiness. It contains (1) deep-dive audit findings from 6 subagent analyses, and (2) a
> master checklist with completion status. **Every new session MUST read this file first** before
> touching anything — it provides the full context so you don't need to re-read 576-line gap docs
> or 551-line schemas to understand where the project stands.
>
> **LOCATION**: `/data/WORK-PROJECT/flowdesk/docs/BETA-READINESS-CHECKLIST.md`
>
> **UPDATE RULE**: When you complete a checklist item, change `[ ]` → `[x]` and add the commit SHA
> or completion date inline. When you start work on an item, change `[ ]` → `[~]` (in progress).
> Do NOT delete items — mark them `[x]` when done or `[cancelled]` if explicitly decided not to do.

---

## 0. Project Snapshot (quick orientation)

| Field | Value |
|---|---|
| **What** | Real-time 0DTE GEX/DEX options terminal for /ES & /NQ (CME futures options) |
| **Stack** | Python engine (Black-76) + FastAPI REST/WS + Next.js 15 dashboard + lightweight-charts |
| **Auth** | Discord OAuth + DESK role gate |
| **Data** | Databento GLBX.MDP3 (historical replay today; live adapter built but disarmed) |
| **DB** | TimescaleDB (history) + Redis (hot snapshot, FLUX state) |
| **Repo** | `/data/WORK-PROJECT/flowdesk/` on branch `feat/live-feed-databento-080-and-docker` |
| **Engine version** | 0.9.0 · API version 0.1.0 |
| **Tests** | 442 engine + 116 API + 26 FE helpers + 109 harness = ~693 total |
| **Schema** | `schema_version = 2`, mirrored pydantic ↔ zod byte-for-byte |

---

## 1. Deep Dive Findings — Engine & Methodology

*Source: subagent bedah `black76.py`, `exposure.py`, `schema.py`, `levels.py`, `flux.py`, `surface.py`,
`synthetic_oi.py`, `ddoi.py`, `proprietary.py`, `exposure_ext.py`, `iv.py`, `field.py` + all test files.*

### Engineering Quality: **9/10**

**Strengths:**
- Black-76 textbook-accurate: d1/d2, price, all 7 greeks (delta, gamma, vega, theta, vanna, charm)
  verified via finite-difference + put-call parity
- IV convergence: Newton→bisection fallback, tol 1e-6, arbitrage bounds guard, max 100 iter
- Pure functions throughout — zero side effects, zero globals, stdlib-only hot path
- `frozen=True` dataclasses prevent accidental mutation
- 442+ tests including golden fixture, cross-language parity, exhaustive finiteness
- Three-layer NaN/Inf defense: pydantic ingress → egress walk → zod mirror
- `FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]` on every numeric field
- Nelder-Mead SVI fitter self-contained (no numpy/scipy dependency)
- Deterministic tie-breaking everywhere
- FluxState Redis round-trip for restart safety

**Gaps (-1):**
- Test suite validates internal consistency but NOT predictive value
- DDOI time-weight `w(i)=1-2·i/(n-1)` is whole-day-normalized — look-ahead for per-minute use,
  documented but no runtime guard preventing per-minute misuse
- `_argmax_abs` in levels.py uses strict `>` — deterministic but undocumented design choice

### Methodology Soundness: **6/10**

**Strengths:**
- Locked VOL-GEX formula mathematically correct, faithfully implemented
- Dealer sign convention (+1/-1) standard, documented, locked
- Honest gap documentation (576 lines of self-critical assessment) — exemplary
- Experimental lenses properly isolated as optional/non-authoritative
- FLUX formula (HIRO-style) standard and t-causal
- SVI surface fitting well-established (Gatheral 2004)

**Gaps (-4):**
- **VOL-GEX is the naive version** (acknowledged Gap #2): cumulative vol × static dealer sign
  cannot capture real dealer inventory; aggressor ≠ customer; cumulative volume double-counts
- **No price validation exists** (Gap #1): GEX/DEX/levels have no proven predictive relationship
  to price; raw rho ~0.4 collapses to ~0.08-0.24 after volume control
- **DDOI inconclusive/leaning-redundant** at n=4 — largely sign-flipped scalar of VOL-GEX
- **No true 0DTE validation**: DDOI "49.2% vs 50.8%" was contaminated (quarterly data, not 0DTE)
- **Synthetic-OI UNDETERMINED** at n=4 for both /ES and /NQ
- **FLUX predictive null** at k=15/30 (suggestive at k=5)
- **Proprietary metrics INFERRED approximations** — VT method contradicts cited source
  (renamed to `oi_gamma_flip` honestly)
- Locked contract freezes naive methodology — cannot evolve without human approval

---

## 2. Deep Dive Findings — API & Security

*Source: subagent bedah `auth.py`, `auth_session.py`, `security.py`, `discord_client.py`,
`entitlement.py`, `worker.py`, `ws.py`, `state.py`, `rate_limit.py`, `db/repo.py`, `main.py`,
live feed (`feed/__init__.py`, `feed/live.py`), plus context docs.*

### Security & Safety: **8/10**

**Strengths:**
- Discord OAuth: correct Authorization Code flow, minimal scopes (`identify guilds.members.read`),
  `prompt=consent` forces re-consent
- CSRF `state` is signed + expiring (10 min) + double-checked against cookie
- Guild membership via `fetch_member`, DESK role via `desk_role_id in member.roles`
- `access_token` stored **encrypted (Fernet)** inside signed session cookie — not plaintext
- Fail-fast at boot: blank `SESSION_SECRET` or `DESK_ROLE_ID` refuses to boot
- CORS strict: `allow_credentials=True` with explicit origin allowlist; `*` + credentials rejected
  at boot (RuntimeError); only https/localhost origins allowed
- No SQL injection: `db/repo.py` uses asyncpg parameterized queries exclusively
- No hardcoded secrets: `.env` gitignored, all secrets from `os.environ`
- No stack-trace leakage: catch-all returns generic error
- Rate limiting: 3 scopes (POST /me/recheck 6/min, OAuth callback 10/min, WS handshake 30/min),
  Redis-backed, fail-open, `Retry-After` header, WS close 4429
- Session state machine: correct timezone-aware transitions, STALE branch attempts live recovery
- Two-key live arming: `FEED_MODE=live` AND `LIVE_FEED_ARMED=1`, enforced before any network call
- Circuit breaker: 5 consecutive failures in 300s → opens permanently, no auto-recovery

**Gaps:**
- 🔴 `/ws/ticks` endpoint has **broken import** (`ws.py:343` imports from `api.state` which
  doesn't export `parse_session_cookie`, `require_desk`, `SESSION_COOKIE`) → endpoint crashes
  on connect (fails closed, not exploitable, but dead code)
- 🟡 `DEV_AUTH_BYPASS=1` exists with no boot-time guard preventing it in production
- 🟡 `SESSION_SECRET` not rotated: single static env key, Fernet derived via `sha256(secret)`
  (not a proper KDF); no rotation mechanism; leaked secret compromises all 7-day sessions
- 🟡 Crash-loop detector (F3 mitigation) documented in threat model but **unimplemented**
- 🟡 Rate-limit coverage excludes data-plane GET endpoints (`/api/snapshot`, `/api/replay*`,
  `/api/me` GET) — logged-in user could hammer unthrottled
- 🟢 `Fernet` key derivation = `sha256(secret)` rather than PBKDF2/HKDF — fine if high-entropy

### Production Readiness: **7/10**

**Strengths:**
- Worker + state machine + breaker + arming rail tested (116 API tests, FakeLiveClient)
- Fail-fast config validation, structured errors
- Boot logging with feed_mode/live_armed

**Gaps:**
- `/ws/ticks` broken — must fix or remove before ship
- Live Databento client (`_DatabentoLiveClient`) is `# pragma: no cover` — untested against
  real socket; wire-format enum encodings unvalidated
- No graceful secret rotation
- For historical-mode beta deploy: READY. For live-mode production: needs supervised first-30-min

---

## 3. Deep Dive Findings — Validation & Evidence

*Source: subagent bedah `analysis/harness/` (flux_eval, synthetic_oi_eval, synthetic_oi_regime_eval,
ddoi_divergence, metrics, run_validation) + `docs/research/empirical/*.md`.*

### Validation Evidence: **2/10** · Signal Quality: **1.5/10**

**Harness is methodologically excellent:**
- All evals strictly t-causal, look-ahead-free
- Positive controls planted (proven ALIVE: perfect lead → hit_rate 1.0, anti-lead → 0.0)
- Red-team caught 5 bugs: look-ahead attraction, distance baseline bias, ES+NQ pooling,
  single-day artefact NQ, cumulative-flow leak — all FIXED
- Tenor provenance guard: fail-closed `assert_session_iids_0dte`
- Three-state classifier: EDGE / NULL / UNDETERMINED (never collapses underpowered to null)
- `MIN_DAYS_FOR_EDGE=5` makes YES unreachable at n<5 by construction

**But evidence is ZERO:**

| Lensa | Hasil | Detail |
|---|---|---|
| FLUX ES k=5 | SUGGESTIVE-POSITIVE, at-threshold | gap ~+0.047 < 0.05 threshold, 4/4 days positive, n=4 < 5 |
| FLUX ES k=15/30 | NULL | gap ~+0.01/~0, sign inconsistent |
| FLUX NQ k=5 | UNDETERMINED | forward coverage only 0.43 |
| Synthetic-OI regime | UNDETERMINED | n=3, sign inconsistent across days |
| Synthetic-OI #4 structural | UNDETERMINED | flow term materially-sized (~0.5 /ES, ~0.79 /NQ) but direction not separable from random |
| Synthetic-OI #6 tiered | UNDETERMINED | near-scalar-rescale of plain flow, ALL norm_ratio_gap NEGATIVE |
| DDOI structural | INCONCLUSIVE-leaning-REDUNDANT | signed correlation ~−0.34, bimodal (2/8 textbook sign-flip, rest noise) |
| Reconciliation | Weak | Volume-controlled rho collapses to 0.08–0.24 ("active strikes are active") |
| Pinning/attraction | Zero signal | Excess-attraction small/mixed, pin-rate ≈ 0 |

**Hard limits:**
- n=3-4 correlated days (one crash arc) — severely underpowered
- Forward is parity reconstruction from options (not traded futures price)
- 90-day forward run **dropped by operator** — no statistical power incoming
- Only k∈{5,15,30} tested

---

## 4. Deep Dive Findings — Frontend & UX

*Source: subagent bedah 35 dashboard files + 21 landing files.*

### Frontend Quality: **8.5/10** · User Experience: **8/10**

**Strengths:**
- Stack: Next.js 15 + React 19 + lightweight-charts v5 + Three.js + Tailwind + TypeScript
- **API wiring FULLY WIRED** (not static!): 3-tier fallback — WS `/ws?instrument=…` (real-time,
  ping/pong, capped backoff 1s→15s, fatal codes 4401/4403/4429 trigger fallback) → REST polling
  `/api/snapshot` (30s interval, cookie auth) → static JSON `/data/<I>_<date>.json` (last resort)
- `isSnapshot()` runtime guard validates `ts`, `forward`, `profile`, `regime`, `levels`
- `useReplaySnapshots`: VCR replay with speed control, playhead math in pure `playback.ts`
- TerminalShell: shared frame (toolbar, FeedBadge, ReplayControlBar, AwaitingDataOverlay)
- Fog lens: two-zone terminal — LEFT (26%, strike ladder + GEX/DEX/VEX/CHEX bars + IV smile)
  + RIGHT (lightweight-charts price candles + selectable key levels + ratio overlays + metrics strip)
- Arc lens: **fully implemented** — Three.js 3D vol surface + ArcGammaTable + TotalHedgingSparklines
- Flux lens: **fully implemented** — HIRO cumulative flow pane beneath Fog price chart
- Pure helpers: `strikeMath.ts` (394 lines) + `levelsChart.ts` (320 lines) — domain-expert level
- 26+ unit tests via `node:test` (zero deps)
- Landing page: 8-section narrative arc, horizontal pinned scroll, i18n ready, mobile responsive
- Error handling: 6 feed states, empty states, graceful degradation
- Design tokens: turquoise/crimson/bone, JetBrains Mono, Space Grotesk — consistent

**Gaps:**
- Dashboard **desktop-only** — no `md:` breakpoints, fixed px, no mobile responsive
- No keyboard shortcuts (traders expect hotkeys)
- No onboarding/tutorial overlay for first-time users
- Three.js not lazy-loaded (dynamic import) — bundle size concern (~600kB)
- No React Error Boundaries at component level
- No React component tests (no RTL, no Playwright)
- Landing: no live demo/screenshot/video, no pricing page, no social proof/testimonials
- `regl` in dependencies but unclear if used (potential dead dep)
- ArcGammaTable has duplicate interface declaration
- IV Smile labeled EXPERIMENTAL but on by default

---

## 5. Deep Dive Findings — Infrastructure & Data Pipeline

*Source: subagent bedah Docker, compose, Dockerfile, feed adapters, ingest, db schema, Makefile,
CI/CD, deploy runbook, threat model, data contract.*

### Infrastructure Readiness: **7/10** · Data Pipeline Quality: **9/10**

**Infrastructure strengths:**
- Multi-stage Dockerfile: security-conscious (non-root user, pinned Python 3.11, proper PYTHONPATH)
- docker-compose: Redis + TimescaleDB + API + Worker, healthchecks, dependency ordering, volumes
- CI/CD: GitHub Actions with pytest (hard gate), ruff/mypy (advisory), TS contract validation
- Health endpoints: `/api/health`, `/healthz` (compose healthcheck)
- Deploy runbook: pre/post-deploy checklists, rollback, incident triage
- 12-key ENV contract documented, `.env.example` exists, `.env` gitignored

**Infrastructure gaps:**
- No production orchestration (no K8s, Terraform, Helm)
- No load balancer/reverse proxy (nginx/Traefik)
- No monitoring stack (Prometheus, Grafana, alerting)
- No backup automation (TimescaleDB pg_dump cron missing)
- Makefile limited: only dev-api/lint/typecheck, no build/push/deploy
- Single-region assumption, no DR architecture
- CI doesn't build Docker images or push to registry
- No security scanning (Snyk/Trivy)

**Data pipeline strengths:**
- HistoricalSimAdapter: CSV-based, binary search, put-call parity forward fallback
- LiveAdapter: two-key arming, circuit breaker, exponential backoff, lazy databento import
- LiveBook: pure assembly logic, wire-format decoders, session rollover
- Ingest: rate-limit-aware (4 requests/schema), idempotent, backoff + jitter
- TimescaleDB: hypertable on `ts`, composite PK, 90-day retention, replay index
- Redis: clean key scheme (now/session/updates/flux), FLUX state 90-min TTL
- FakeLiveClient seam, dependency injection, offline testability
- Threat model: 7 failure modes F1-F7 with specific mitigations

**Data pipeline gaps:**
- Live feed untested against real Databento socket (wire format provisional)
- No automated data quality checks (reconciliation between historical and live)
- No streaming backfill if worker misses minutes
- Manual ingest only (no scheduled Databento pulls)
- No data lineage tracking

---

## 6. Deep Dive Findings — Market Viability & Business

*Source: subagent bedah all strategic docs + landing page.*

### Market Viability: **5/10** · Business Readiness: **4/10**

**Target market:** Advanced retail / prosumer futures options traders who understand GEX/DEX and
seek intraday 0DTE edge. Small prop traders / trading desks as secondary. NOT: retail beginners,
hedge funds, buy-and-hold investors.

**UVP:** "Real-time 0DTE dealer positioning terminal built futures-native for /ES & /NQ, with
deterministic math and transparent EXPERIMENTAL labels." Key differentiator vs SpotGamma:
futures-native (not SPX-proxy), auditable math, honest labels.

**Competitive landscape:** Crowded in SPX/options analytics, blue ocean in futures-native 0DTE.
SpotGamma is benchmark ($99-249/mo), Unusual Whales ($49-99/mo), ORATS ($500+/mo).

**Pricing recommendation:** $49-79/mo beta, $99-129/mo founder, $199-299/mo desk.

**GTM:** Discord community play — seed from flowjob.id guild, content-led growth,
limited beta (50-100 seats), referral-only invites.

**Business gaps:**
- TAM very small (niche within niche)
- Validation 2/10 = high churn risk (traders outcome-driven, churn in 1-2 months if no edge)
- No billing/payment system (Stripe/Paddle)
- No social proof/testimonials
- Discord dependency for auth
- No expandability to other instruments in roadmap
- Probability of success as paid beta (limited): 6/10
- Probability of success as scaled SaaS: 3/10

---

## 7. MASTER CHECKLIST — Phased Action Items

> **Status key**: `[ ]` not started · `[~]` in progress · `[x]` done (add commit/date) · `[cancelled]` decided not to do

### PHASE 0: Pre-Launch Blockers (MUST FIX sebelum beta)

#### Critical Code Fixes

- [x] **Fix `/ws/ticks` broken import** ✅ (2026-06-25)
  - Fixed: Import dari `api.state` → `api.security`
  - Added: Auth gate BEFORE accept (same as `/ws`)
  - Added: Rate-limiting, heartbeat, instrument validation
  - Verified: 123/123 API tests passed

- [x] **Add `DEV_AUTH_BYPASS` prod-boot guard** ✅ (2026-06-25)
  - Added: Boot-time check in `_validate_auth_config()` (main.py)
  - Refuses to boot jika `DEV_AUTH_BYPASS=*` and `AUTH_CONFIG_OPTIONAL != "1"`
  - Verified: 123/123 API tests passed, 0 regressions

- [x] **Implement crash-loop detector (F3 mitigation)** ✅ (2026-06-25)
  - Added: `_CrashLoopGuard` class in `services/engine/src/engine/feed/live.py`
  - Tunables: `CRASH_LOOP_MAX_ARMS = 3`, `CRASH_LOOP_WINDOW_SECONDS = 600`
  - New error: `LiveFeedCrashLoop` raised when >3 arms in 10 minutes
  - Fail-open on I/O errors (warn but don't refuse)
  - Unarmed boots never pollute the ledger
  - Default path: `~/.flowdesk/live-arm-attempts.log` (override via `LIVE_ARM_LOG_PATH`)
  - Verified: 472/472 engine tests passed (11 new tests + 14 updated)

- [x] **Dynamic import Three.js / ArcPanel** ✅ (2026-06-25)
  - Added: `next/dynamic` import in `apps/dashboard/src/app/fog/page.tsx`
  - ArcPanel lazy-loaded (not in initial bundle)
  - Bundle size: `/fog` route 177 kB First Load JS (Three.js chunk loaded on demand)
  - Verified: typecheck ✅, build ✅ (8/8 static pages)

- [x] **Add React Error Boundaries** ✅ (2026-06-25)
  - Created: `apps/dashboard/src/components/ErrorBoundary.tsx`
  - Wrapped: `MetricBarPanel`, `LevelsChartPanel`, `ArcGammaTable`, `TotalHedgingSparklines`, `ArcPanel`
  - Fallback UI: user-friendly messages ("Strike bars unavailable", "Price chart unavailable", etc.)
  - Retry button + console logging
  - Verified: typecheck ✅, build ✅ (177 kB First Load JS)

#### Business Critical Setup

- [x] **Discord DESK role gate — ALREADY BUILT** ✅
  - Auth: Discord OAuth → guild membership check → DESK role check → terminal access
  - Billing: handled externally at **flowjob.id** (Midtrans + Supabase auth + DESK tier)
  - Flow: user pays at flowjob.id → gets DESK role → logs into FlowDesk → terminal opens
  - No Stripe/Paddle needed — billing is FlowJob's responsibility
  - Files: `services/api/src/api/discord_client.py`, `services/api/src/api/auth.py`, `services/api/src/api/entitlement.py`
  - Landing CTA: primary = Discord login, secondary = "Claim DESK at flowjob.id"

- [ ] **Integrate terminal into flowjob.id** (per INTEGRASI-FLOWDESK-KE-FLOWJOB.md)
  - Status: **Plan exists, not yet executed**
  - Approach: Port dashboard components into `flowjob-master` as `/dashboard/app`
  - Gate: reuse existing DESK tier gate (already working in FlowJob)
  - Landing: convert FlowDesk landing → `/docs/terminal` on flowjob.id
  - See: `INTEGRASI-FLOWDESK-KE-FLOWJOB.md` for 9-phase implementation plan

- [ ] **Add social proof to landing/flowjob.id**
  - Content: testimonials, user count, or "trusted by X traders" counter
  - Location: either FlowDesk landing (if kept standalone) or FlowJob marketing pages
  - Severity: Conversion rate depends on trust signals

---

### PHASE 1: Beta Launch Essentials (2-4 weeks, HIGH priority)

#### 1.A — Frontend UX Improvements

- [ ] **Add keyboard shortcuts for traders**
  - Shortcuts: `G`/`D`/`V`/`C` = toggle GEX/DEX/VEX/CHEX, `Space` = play/pause replay,
    `←/→` = step frame, `1-9` = toggle key levels
  - File: `apps/dashboard/src/components/terminal/TerminalShell.tsx`
  - Library: Custom hook or `mousetrap`

- [ ] **Add onboarding tooltip for first-time users**
  - Content: Explain Fog lens zones, strike ladder, GEX bars, key levels, replay controls
  - Trigger: First visit (localStorage flag `fd_onboarded`)
  - Library: `react-joyride` or custom tooltip overlay

- [ ] **IV Smile: default OFF, not ON**
  - Issue: IV smile labeled EXPERIMENTAL but renders by default — confusing for users
  - Fix: Toggle off by default, user must explicitly enable
  - File: Fog page toggle state

- [ ] **Remove dead `regl` dependency**
  - File: `apps/dashboard/package.json`
  - Issue: `regl` listed but unclear if used (legacy from deleted heatmap)
  - Fix: Verify no imports, remove from package.json if dead

- [ ] **Fix duplicate interface in ArcGammaTable**
  - File: `apps/dashboard/src/components/arc/ArcGammaTable.tsx`
  - Issue: Duplicate interface declaration at lines 28-34 and 37-44
  - Fix: Remove duplicate, keep one

- [ ] **Add functional settings page**
  - Features: Default instrument, default lens, theme toggle, EXPERIMENTAL toggle
  - Persistence: localStorage
  - File: `apps/dashboard/src/app/settings/page.tsx`

#### 1.B — Infrastructure

- [ ] **Add monitoring stack** (Prometheus + Grafana)
  - Metrics: Request rate, error rate, feed gap duration, WS connections, engine compute time
  - Dashboard: Real-time health overview
  - Alerting: PagerDuty or OpsGenie for critical alerts
  - Config: Add to docker-compose or deploy separately

- [ ] **Add backup automation**
  - Script: `pg_dump` TimescaleDB daily → S3/GCS upload
  - Cron: `0 2 * * *` (2 AM UTC)
  - Test: Monthly restore verification
  - Retention: 30 days on S3, lifecycle policy

- [ ] **Add data quality checks**
  - Post-ingest: Validate row counts, date ranges, NaN spikes
  - Live vs historical reconciliation script
  - Alert on anomalies: missing minutes, price jumps >5%, unexpected NaN

- [ ] **Add CI Docker build/push**
  - Pipeline: GitHub Actions → build → push to GHCR
  - Tags: Git SHA + `latest`
  - Multi-arch: amd64 + arm64

#### 1.C — Validation

- [ ] **Run 90-day forward validation**
  - Lensa priority: FLUX ES k=5 (suggestive-positive, gap +0.047)
  - Data needed: 90 independent 0DTE trading days
  - Method: Same t-causal harness, shuffled-sign null, MIN_DAYS_FOR_EDGE=5
  - Output: Validation report with confidence intervals
  - Cost: Databento data pull for 90 days + compute time
  - **THIS IS THE SINGLE MOST IMPORTANT ITEM ON THIS LIST**

- [ ] **Document validation plan** (if 90-day run approved)
  - Write: `docs/research/empirical/validation-plan-90day.md`
  - Include: Data requirements, statistical power calculation, timeline, budget

#### 1.D — Business (handled by FlowJob ecosystem)

- [x] **Discord auth + DESK role gate = already working** ✅ (see Phase 0.C)

- [ ] **Integrate terminal frontend into flowjob.id** — this IS the beta launch
  - Per `INTEGRASI-FLOWDESK-KE-FLOWJOB.md` (9-phase plan exists)
  - Priority: Phase 0-3 of integration plan (port components, wire API, deploy)
  - This replaces the need for a standalone FlowDesk landing/billing system
  - flowjob.id already handles: auth (Supabase + Discord), billing (Midtrans), DESK tier

- [ ] **Verify DESK role assignment flow end-to-end**
  - Flow: User pays at flowjob.id → Midtrans → Supabase → Discord bot assigns DESK role
  - Verify: Does the Discord bot auto-assign DESK role after payment? Or is it manual?
  - If manual: needs automation (Discord bot webhook from FlowJob payment events)

- [ ] **Add live demo screenshot/video to flowjob.id terminal docs**
  - Format: Animated GIF or short video of Fog lens in action
  - Location: `/docs/terminal` page on flowjob.id (replacing standalone landing)
  - Content: Strike ladder + GEX bars + key levels + replay scrubbing

---

### PHASE 2: Beta Operations (1-3 months, ongoing)

#### 2.A — Operations

- [ ] **Collect user feedback system**
  - Tool: In-app feedback button + dedicated Discord channel
  - Frequency: Weekly survey (3 questions max)
  - Metrics: NPS score, feature requests, bug reports
  - Action: Prioritize by impact/frequency

- [ ] **Monitor churn rate**
  - Metric: Monthly churn rate via Stripe dashboard
  - Target: <10% for beta
  - Action: If churn >15%, interview 5 churned users within 48h

- [ ] **Track P&L testimonials**
  - Method: Optional submission form (no guarantee of accuracy)
  - Use: Marketing material for scale phase
  - Compliance: "Past performance ≠ future results" disclaimer on every testimonial

- [ ] **Validate live feed through runbook**
  - Action: Operator runs supervised first-30-minutes with `LIVE_FEED_ARMED=1`
  - Verify: Minute assembly, definition seeding, FLUX parity, circuit breaker behavior
  - Document: Write post-validation report

#### 2.B — Infrastructure

- [ ] **Add integration tests (end-to-end)**
  - Scope: Ingest → engine → API → WebSocket → dashboard
  - Tool: docker compose + pytest
  - Coverage: Historical path + live path (FakeLiveClient)
  - CI: Run in GitHub Actions

- [ ] **Add Kubernetes manifests** (if scaling >100 users)
  - Tool: Helm chart or kustomize
  - Services: API, Worker, Redis (Sentinel), TimescaleDB (with replication)
  - Scaling: HPA based on CPU/memory

- [ ] **Add security scanning to CI**
  - Tool: Trivy or Snyk
  - Scope: Docker image + Python dependencies + npm packages
  - Gate: Block on critical vulnerabilities

#### 2.C — Frontend

- [ ] **Add mobile responsive (minimal, read-only)**
  - Scope: Strike ladder + price chart only (no 3D surface on mobile)
  - Breakpoints: `md:` and `lg:` Tailwind classes
  - Priority: Monitoring view, not full trading terminal

- [ ] **Add alerting/notifications**
  - Features: Email or Discord webhook when price crosses gamma flip, GEX sign change
  - Triggers: Key level breach, regime flip, large FLUX spike
  - Delivery: Email (SendGrid/Mailgun) or Discord webhook

- [ ] **Add React component tests**
  - Tool: Playwright or React Testing Library
  - Scope: TerminalShell, FeedBadge, ReplayControlBar, strike bars rendering
  - CI: Run in GitHub Actions

#### 2.D — Validation (continued)

- [ ] **Run synthetic-OI predictive eval** (if 90-day data available)
  - Lensa: Synthetic-OI regime (volatility predictor)
  - Data: 90 independent days
  - Metric: Separation score vs regime-label shuffle null
  - Output: Validation report

- [ ] **Run DDOI predictive eval** (if data sufficient)
  - Lensa: DDOI-GEX vs VOL-GEX divergence
  - Note: Auditor recommended NOT funding 90-day run on DDOI (structural eval was
    inconclusive-leaning-redundant) — only do this if operator insists

---

### PHASE 3: Scale & Growth (3-6 months, MEDIUM priority)

#### 3.A — Business

- [ ] **Expand to more instruments**
  - Priority: Based on user demand data from Phase 2
  - Candidates: /CL (crude oil), /GC (gold), /RTY (Russell 2000), /ZN (10-year Treasury)
  - Engineering: Each instrument needs own multiplier, strike step, definition mapping
  - Locked contract: Requires human approval to add instruments

- [ ] **Add broader auth channels** (reduce Discord dependency)
  - Options: Email+password auth, Google OAuth, GitHub OAuth
  - Goal: Reduce single-platform dependency risk
  - Migration: Keep Discord as primary, add alternatives as secondary

- [ ] **Create affiliate program**
  - Commission: 20-30% recurring for first 12 months
  - Target: Trading educators, content creators, Discord community leaders
  - Platform: Rewardful or custom Stripe integration

- [ ] **Build community features**
  - In-app: User profiles, shared levels annotation, chat
  - Or: Deep Discord integration (auto-post daily levels, regime alerts)
  - Goal: Increase retention and engagement

#### 3.B — Product

- [ ] **Add options strategy builder**
  - Features: Spread builder, payoff diagram, P&L calculator
  - Inspiration: OptionStrat-style visual
  - Integration: Link GEX/DEX levels to strategy suggestions

- [ ] **Add broker execution integration**
  - Brokers: Interactive Brokers, Tradier, Alpaca (start with one)
  - Features: One-click trade from terminal, position tracking
  - Compliance: Broker-dealer agreement, "not a broker" disclaimer

- [ ] **Add AI-powered insights** (if validated)
  - Features: Anomaly detection, regime auto-classification, pattern recognition
  - Model: Lightweight classifier trained on validated GEX data
  - Gate: Only build after 90-day validation confirms predictive signal

#### 3.C — Infrastructure

- [ ] **Add multi-region deployment**
  - Regions: US-East (primary), US-West, EU (secondary)
  - Tool: Cloudflare Workers or AWS CloudFront
  - Goal: <100ms latency for US users, <200ms for EU

- [ ] **Add high availability**
  - Redis: Redis Sentinel or Cluster
  - TimescaleDB: Read replicas + automatic failover
  - API: Load balancer + auto-scaling group

---

### PHASE 4: Long-term Roadmap (6-12 months+, FUTURE)

- [ ] **Expand to international markets** (Eurex, CME Asia, etc.)
- [ ] **Build institutional tier** (multi-user desks, API access, custom data, $500+/mo)
- [ ] **Create educational content** (video courses, webinars, newsletter)
- [ ] **Add ML signal layer** (LSTM/Transformer, only if Phase 2 validation confirms edge)
- [ ] **Series A fundraising** (if traction strong: 200+ users, ARR >$50k)
- [ ] **Mobile app** (native iOS/Android for monitoring + alerts)

---

## 8. Score Summary & Success Criteria

### Current Scores (from deep dive)

| # | Dimension | Metric | Score |
|---|---|---|---|
| 1 | Engine | Engineering Quality | 9/10 |
| 2 | Engine | Methodology Soundness | 6/10 |
| 3 | API & Security | Security & Safety | 8/10 |
| 4 | API & Security | Production Readiness | 7/10 |
| 5 | Validation | Validation Evidence | 2/10 |
| 6 | Validation | Signal Quality | 1.5/10 |
| 7 | Frontend | Frontend Quality | 8.5/10 |
| 8 | Frontend | User Experience | 8/10 |
| 9 | Infrastructure | Infrastructure Readiness | 7/10 |
| 10 | Infrastructure | Data Pipeline Quality | 9/10 |
| 11 | Business | Market Viability | 5/10 |
| 12 | Business | Business Readiness | 4/10 |

**Overall Beta Readiness: 5.5/10**

### Phase Gate Criteria

| Gate | Criteria | Current Status |
|---|---|---|
| **Phase 0 → 1** | All 8 critical fixes done + payment system live | ❌ Not met |
| **Phase 1 → 2** | Beta launched, 50+ paying users, churn <15% | ❌ Not met |
| **Phase 2 → 3** | 90-day validation complete, predictive edge proven | ❌ Not met |
| **Phase 3 → 4** | 200+ users, ARR >$50k, positive unit economics | ❌ Not met |

### Target Scores After Phase Completion

| Phase | Target Overall Score | Key Improvement |
|---|---|---|
| After Phase 0 | 6.5/10 | Fix blockers, payment ready |
| After Phase 1 | 7/10 | UX improved, monitoring live, billing running |
| After Phase 2 | 8/10 | Validation evidence, user feedback, stable ops |
| After Phase 3 | 8.5/10 | Scale validated, multi-instrument, retention solid |

---

## 9. Quick Reference for New Sessions

### First things to do in a new session:
1. **Read this file** (`docs/BETA-READINESS-CHECKLIST.md`) — it contains the full audit context
2. **Run `git log --oneline -10`** to see what changed since last session
3. **Check checklist status** — look for `[~]` (in progress) items to continue, or `[ ]` items to start
4. **Update this file** when you complete or start work on any item
5. **Follow AGENTS.md** for project rules (locked contract, verification commands, etc.)

### Verification commands (from AGENTS.md):
```bash
# Engine
cd services/engine && pytest && ruff check . && mypy

# API (install engine editable first)
cd services/api && pip install -e ../engine && pytest && ruff check . && mypy

# TS contracts
pnpm -r typecheck && pnpm -r lint && pnpm --filter @flowdesk/contracts validate

# Dashboard
cd apps/dashboard && pnpm install && pnpm run typecheck && pnpm run build && node --test src/lib/*.test.ts

# Full lint+typecheck
make lint && make typecheck
```

### Key file locations:
| Need | Path |
|---|---|
| Engine core | `services/engine/src/engine/` |
| API + auth | `services/api/src/api/` |
| Dashboard | `apps/dashboard/src/` |
| Landing | `apps/landing/src/` |
| Contracts (TS) | `packages/contracts/src/` |
| Contracts (PY) | `services/engine/src/engine/schema.py` |
| Docker | Root `docker-compose.yml` + `infra/docker-compose.yml` |
| CI | `.github/workflows/` |
| Harness | `analysis/harness/` |
| Docs | `docs/` (start at `docs/README.md`) |

---

*Last updated: 2026-06-25 (initial creation from 6-subagent deep dive audit)*
*Next update: When any checklist item status changes*
