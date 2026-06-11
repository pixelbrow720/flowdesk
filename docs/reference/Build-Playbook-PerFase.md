# FlowDesk — Build Playbook Per-Fase (Prompt-by-Prompt)

> Kompilasi seluruh prompt per-fase (Fase 0–6, total 34 prompt) untuk membangun FlowDesk lewat AI agent.
> Aturan: **satu prompt = satu deliverable ZIP + README**. Kerjakan Fase 0 → 6 berurutan.
> Sebelum mengirim prompt apa pun ke agent, **tempel MASTER PREAMBLE di bawah ini di ATAS prompt** (itu yang mengunci: no-internet, output file lengkap, token desain, anti-AI-look).

## 🧱 MASTER PREAMBLE (tempel di ATAS setiap prompt)

```text
You are a senior full-stack engineer building "FlowDesk" — a real-time 0DTE GEX/DEX options terminal for /ES & /NQ futures (inspired by SpotGamma TRACE + GEXBOT, but VOL-based and 0DTE-focused).

OPERATING RULES (non-negotiable):
- Sandbox has NO internet, NO package install, NO code execution. You ONLY write files.
- Deliver ONE .zip containing every file for THIS task + a README.md with: exact local setup/run commands, a manual verification checklist, and an "Assumptions" section.
- Output COMPLETE file contents. No "...", no TODO, no stubs, no "rest unchanged". Pin EXACT dependency versions.
- The PRD is the single source of truth. The LOCKED CONTRACT below is absolute — never substitute colors, fonts, formulas, units, or schema.
- If something is truly unspecified, pick the SIMPLEST choice consistent with the locked contract and record it under README > Assumptions.
- Production-grade quality only. Follow ANTI-AI-LOOK rules. Do NOT ship generic boilerplate.
- You cannot run code; self-verify by careful static reasoning and keep code type-safe.

LOCKED CONTRACT (global):
- Colors: turquoise #40E0D0 = positive/support ; crimson #E0183C = negative/resistance ; dark base #000000.
- Heatmap ramp: dark = turquoise->black->crimson ; light = turquoise->white->crimson ; perceptual interpolation (OKLab/LCH).
- Fonts: Space Grotesk (UI/display) + JetBrains Mono (all numbers). NEVER Inter. NEVER wedding-style/decorative fonts.
- Instruments: /ES multiplier $50/pt, /NQ multiplier $20/pt. Strike step: /ES = 5, /NQ = 10.
- Session: RTH 09:30-16:00 America/New_York (half-days auto from CME calendar). Cadence: 1 minute. Replay retention: 90 days rolling, derived-only.
- Pricing model: Black-76. Forward F = futures price. r = ln(1+SOFR). IV from option mid (Newton-Raphson, fallback bisection, tol 1e-6).
- Dealer convention: dealer long calls, short puts. Net GEX>0 -> pinning/stabilizing (turquoise). Net GEX<0 -> trending/volatile (crimson).
- GEX unit: GEX_strike = gamma * VOL * M * F^2 * 0.01  (USD per 1% move). VOL = cumulative volume since RTH open.
- Key levels: Call/Put Wall = by OI, STATIC all day, Top 3 (user picks 1/2/3, MUST match SpotGamma EXACTLY). Gamma Flip + Largest GEX/DEX = by VOL, dynamic.
- Regime v1 = sign of net gamma + stability %.
- Access: Discord OAuth2 (scopes: identify guilds.members.read). Truth = member of guild Flowjob.id holding role "DESK". Re-check at login + daily(>24h). Cookie HttpOnly+Secure+SameSite=Lax, 7d.
- Snapshot schema (schema_version 1): { schema_version, instrument, session_date, ts, minute_index, state, stale, expired, forward, rate, axis{strike_min,strike_max,step}, regime{net_gamma,sign,stability_pct}, profile[]{strike,net_gex,net_dex,interpolated}, field{price_grid[],gamma[],delta[]}, levels{call_walls[],put_walls[],gamma_flip,largest_gex,largest_dex} }.
- Env keys: DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_GUILD_ID, DISCORD_DESK_ROLE_ID, SESSION_SECRET, CORS_ORIGINS, FEED_MODE(historical|live), DATABENTO_API_KEY, DATA_DIR, TIMESCALE_DSN, REDIS_URL, SOFR_RATE.

ANTI-AI-LOOK RULES:
- No generic SaaS purple gradients, no Inter, no rounded-everything, no emoji-as-icons, no centered hero with one button cliche.
- Intentional spacing, real data-art aesthetic, monospaced numbers, restrained motion, dark futuristic minimal.
- Every UI number uses JetBrains Mono. Tabular alignment for figures.

STACK (locked):
- Frontend: Next.js (App Router) + React + TypeScript. Heatmap = WebGL (regl or raw WebGL2). Tailwind for layout, CSS vars for tokens.
- Backend: Python 3.11 + FastAPI + a worker. Data: TimescaleDB (Postgres) + Redis.
- Monorepo: pnpm workspaces (web) + python package (engine/api). Docker Compose for backend.
- Landing extras (Phase 5 only): Lenis (smooth scroll) + GSAP ScrollTrigger + Three.js (data-art hero).

When I say "PRD #N" I mean the corresponding sub-page; I will paste it if you need more detail. Acknowledge the locked contract, then produce the deliverable.
```

## Konvensi ZIP & README (berlaku semua prompt)

| Hal | Aturan |
| --- | --- |
| Nama ZIP | `flowdesk-<fase>-<slug>.zip` (mis. `flowdesk-p1-engine-black76.zip`) |
| README wajib berisi | 1) prasyarat & versi, 2) langkah setup lokal, 3) cara verifikasi manual, 4) daftar file, 5) Assumptions |
| Tidak boleh | `...`, TODO, stub, "rest unchanged", dependency tanpa versi |
| Struktur | Hormati layout repo di PRD #8; tiap ZIP menaruh file di path final yang benar |

---

# Fase 0 · Fondasi & Kontrak

> 🧱 **Tujuan fase:** menyiapkan kerangka monorepo, **kontrak Snapshot Schema** (dipakai FE & BE), dan **paket design-token**. Semua fase berikutnya bergantung pada output fase ini. Referensi: PRD #8 (Arsitektur), #2 (Design System), #0 (Glosarium).

## Prompt 0.1 — Monorepo scaffold + tooling
**Deliverable:** `flowdesk-p0-monorepo.zip` · **PRD:** #8
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Create the empty monorepo skeleton for FlowDesk. No business logic yet.

PRODUCE:
- Root: package.json (pnpm workspaces), pnpm-workspace.yaml, .gitignore, .editorconfig, .nvmrc (node 20), README.md, .env.example (ALL env keys from locked contract with placeholder values + comments).
- apps/web/         -> Next.js App Router + TS placeholder (package.json only + minimal app/layout.tsx, app/page.tsx that renders "FlowDesk" wordmark in Space Grotesk; tailwind config + postcss; tsconfig).
- services/engine/  -> Python package (pyproject.toml, src/engine/__init__.py, README) pinned to Python 3.11.
- services/api/      -> Python FastAPI package (pyproject.toml, src/api/__init__.py, src/api/main.py with a /api/health endpoint returning {status:"ok"}).
- packages/contracts/ -> empty TS package placeholder (filled in 0.2).
- packages/tokens/    -> empty TS package placeholder (filled in 0.3).
- infra/             -> empty folder with .gitkeep (compose added later).

REQUIREMENTS:
- pnpm workspaces must include apps/* and packages/*.
- Pin exact versions: next, react, typescript, tailwindcss, fastapi, uvicorn, pydantic v2. List them in README.
- tsconfig uses strict:true, paths alias @contracts/* and @tokens/*.
- Python uses ruff + mypy config (strict). Add Makefile with targets: dev-web, dev-api, lint, typecheck.
- README explains the full folder tree, prerequisites (node 20, pnpm, python 3.11, docker), and how to run web + api locally.

ACCEPTANCE: folder tree matches PRD #8 repo layout; .env.example lists every locked env key; no business logic; everything type-checks by inspection.
```

## Prompt 0.2 — Kontrak Snapshot Schema (TS + Pydantic, satu sumber)
**Deliverable:** `flowdesk-p0-contracts.zip` · **PRD:** #8 (Snapshot Schema), #0
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement the SHARED Snapshot data contract as the single source of truth, in BOTH TypeScript (packages/contracts) and Python (services/engine/src/engine/schema.py), kept byte-for-byte equivalent in field names and semantics.

PRODUCE (TypeScript, packages/contracts/src/):
- snapshot.ts: exact types for schema_version(1), instrument("ES"|"NQ"), session_date(ISO date), ts(ISO datetime UTC), minute_index(int), state("PREMARKET"|"LIVE"|"STALE"|"CLOSED"|"HOLIDAY"), stale(boolean), expired(boolean), forward(number), rate(number), axis{strike_min,strike_max,step}, regime{net_gamma,sign(-1|0|1),stability_pct}, profile: Array<{strike,net_gex,net_dex,interpolated:boolean}>, field{price_grid:number[],gamma:number[],delta:number[]}, levels{call_walls:number[],put_walls:number[],gamma_flip:number|null,largest_gex:number|null,largest_dex:number|null}.
- index.ts re-exports. Add JSDoc on EVERY field stating unit + meaning from the glossary.
- A runtime validator (zod) `parseSnapshot()` that enforces array-length invariants: field.gamma.length === field.delta.length, and field.price_grid defines the grid.

PRODUCE (Python, services/engine/src/engine/schema.py):
- Pydantic v2 models mirroring the TS types EXACTLY (same field names/casing). Include validators for the same array-length invariants. Add a to_json() that emits keys identical to the TS contract.

PRODUCE:
- packages/contracts/CONTRACT.md: a table mapping each field -> type -> unit -> source PRD section. State that schema_version MUST be bumped on any breaking change.
- A tiny fixture: examples/snapshot.example.json that validates under BOTH validators (document the values).

ACCEPTANCE: TS and Python field names match 1:1; both validators accept the example and reject a deliberately malformed one (show the malformed case in README). No field omitted vs locked contract.
```

## Prompt 0.3 — Paket design-token (warna, font, spacing)
**Deliverable:** `flowdesk-p0-tokens.zip` · **PRD:** #2 (Design System), #0 §7
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Build the design-token package (packages/tokens) that EVERY UI imports. Tokens are the only allowed source of colors/spacing/type. Hard-coded hex in components is forbidden later.

PRODUCE:
- tokens.ts: exported constants for colors (turquoise #40E0D0, crimson #E0183C, dark base #000000, plus a neutral monochrome ramp gray-50..gray-950 you define for dark UI chrome), semantic aliases (positive=turquoise, negative=crimson, support, resistance, bg, surface, border, text-primary, text-muted), spacing scale (4px base: 4,8,12,16,24,32,48,64), radius scale (2,4,8 — NOT pill-everything), type scale (display/h1/h2/body/caption/mono sizes in rem), font families (ui: "Space Grotesk", mono: "JetBrains Mono"), motion (durations 120/180/240ms, easing cubic-bezier values), shadows/glows (subtle turquoise/crimson glow for data states).
- tokens.css: the SAME tokens as CSS custom properties under :root (dark) and [data-theme="light"]. Include the heatmap ramp stops for dark (turquoise->black->crimson) and light (turquoise->white->crimson) as CSS vars + a documented OKLab interpolation note.
- tailwind-preset.ts: a Tailwind preset that maps these tokens into theme.extend (colors, spacing, borderRadius, fontFamily, transitionDuration). apps/web will consume this preset.
- fonts/: instructions in README to self-host Space Grotesk + JetBrains Mono (list exact weights: Space Grotesk 400/500/600/700; JetBrains Mono 400/500). Provide @font-face CSS referencing /fonts/*.woff2 (note: user adds the actual woff2 files locally; list the filenames).

ANTI-AI-LOOK: include a USAGE.md with explicit DO/DON'T (no Inter, no generic purple gradient, numbers always mono, tabular-nums on figures, restrained radius).

ACCEPTANCE: importing tokens gives turquoise/crimson exactly; tailwind preset compiles by inspection; CSS vars cover dark+light; no decorative fonts.
```

---

# Fase 1 · Compute Engine (akurasi-kritis)

> 🧮 **Tujuan fase:** jantung produk — perhitungan greeks, IV, GEX/DEX, field, dan key levels. **Akurasi adalah fitur.** Setiap prompt WAJIB menyertakan unit test. Referensi: PRD #7 (Model Data), #12 (Testing), #0.

## Prompt 1.1 — Black-76 pricing + greeks
**Deliverable:** `flowdesk-p1-black76.zip` · **PRD:** #7 §Black-76, #0 §3
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement the Black-76 model for options on futures, in services/engine/src/engine/black76.py, with full unit tests.

PRODUCE:
- black76.py with pure functions: price(call|put, F, K, T, r, sigma), and greeks delta, gamma, vega, theta. Use exact Black-76 formulas (discounting by exp(-rT); d1=(ln(F/K)+0.5*sigma^2*T)/(sigma*sqrt(T)), d2=d1-sigma*sqrt(T)). Handle T->0 and sigma->0 edge cases gracefully (return well-defined limits, never NaN).
- Use math/numpy only (numpy pinned).
- tests/test_black76.py: verify price+greeks for ATM/ITM/OTM calls & puts vs hand-computed reference values you include as constants in the test (document how you derived them). Tolerance < 1e-6. Include put-call parity test.

ACCEPTANCE (maps to PRD #12 T-01): all reference cases within 1e-6; parity holds; no NaN at boundaries. README shows the reference table.
```

## Prompt 1.2 — IV solver (Newton-Raphson + bisection fallback)
**Deliverable:** `flowdesk-p1-ivsolver.zip` · **PRD:** #7 §IV
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement implied-vol solver in services/engine/src/engine/iv.py using option MID price, with Newton-Raphson primary and bisection fallback.

PRODUCE:
- implied_vol(option_type, mid_price, F, K, T, r) -> float|None. Newton-Raphson seeded by Brenner-Subrahmanyam approximation; switch to bisection on non-convergence/negative vega; bracket [1e-4, 5.0]. Convergence: |price(sigma)-mid| < 1e-6 OR step < 1e-8, max 100 iters. Return None if mid violates arbitrage bounds (document the checks).
- A helper to mark a strike's IV as needing INTERPOLATION when liquidity is thin (mid missing/zero/crossed) -> the caller (1.3) interpolates from neighbors. Provide a documented predicate is_iv_reliable().
- tests/test_iv.py: round-trip test (price -> iv -> price reconstructs within 1e-6) across a grid of inputs; test thin-liquidity path returns None/flag; test convergence < 50 iters on normal inputs.

ACCEPTANCE (PRD #12 T-02,T-03): round-trip < 1e-6; thin-liquidity does not crash; converges < 50 iters typical.
```

## Prompt 1.3 — GEX/DEX aggregation (dealer sign + units)
**Deliverable:** `flowdesk-p1-exposure.zip` · **PRD:** #7 §GEX/DEX, #0 §5§6
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement per-strike GEX/DEX aggregation in services/engine/src/engine/exposure.py.

INPUT MODEL: a per-strike option chain row {strike, call_gamma, put_gamma, call_delta, put_delta, call_vol, put_vol, call_oi, put_oi, multiplier M, forward F} after IV+greeks computed.

RULES (locked):
- Dealer convention: dealer LONG calls, SHORT puts.
- net_gex per strike = sum over calls/puts of (dealer_sign * gamma * VOL * M * F^2 * 0.01), where VOL = cumulative volume since RTH open for that option. Calls contribute +, puts contribute - per the dealer convention. State the exact sign math in comments.
- net_dex per strike analogously using delta (define the dealer-delta sign convention explicitly and document it).
- Interpolate IV-derived gamma/delta for strikes flagged thin (from 1.2) using neighboring strikes; mark profile entries interpolated=true.

PRODUCE:
- exposure.py: build_profile(chain, M, F) -> list of {strike, net_gex, net_dex, interpolated}.
- aggregate net_gamma (sum of net_gex) for regime.
- tests/test_exposure.py: T-04 sign test (a synthetic chain where dealer long call/short put yields the documented sign); units test (a known input yields expected USD magnitude); interpolation test.

ACCEPTANCE (PRD #12 T-04): signs match locked convention; units in USD-per-1%; interpolation flagged.
```

## Prompt 1.4 — Field projection + key levels
**Deliverable:** `flowdesk-p1-field-levels.zip` · **PRD:** #7 §Field/#Levels
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement the TRACE-style field projection and key-level detection in services/engine/src/engine/field.py and levels.py.

FIELD (field.py):
- Given the per-strike profile + an axis {strike_min,strike_max,step} and a price grid, compute a 2D gamma field and delta field as the projected dealer exposure across the price grid (document the projection: for each hypothetical price, recompute net exposure response). Output field{price_grid[], gamma[], delta[]} flattened consistently with the contract; document row/col ordering.
- Smooth via interpolation across strikes; keep arrays aligned to the contract.

LEVELS (levels.py):
- Call/Put Wall: by OI, STATIC for the day (computed once at/after RTH open from OI), Top 3 strikes above (call) and below (put) the forward. Return ordered lists. MUST be deterministic and match SpotGamma logic exactly (largest OI).
- Gamma Flip: by VOL, the zero-crossing strike of cumulative net gamma (interpolate the crossing). Dynamic intraday.
- Largest GEX / Largest DEX: by VOL, the strike with max |net_gex| / |net_dex|. Dynamic.
- tests: T-05 zero-crossing interpolation correctness; T-06 walls Top-3 above/below forward exactness vs a golden fixture.

ACCEPTANCE (PRD #12 T-05,T-06): flip interpolated correctly; walls exact vs fixture; field arrays satisfy contract invariants.
```

## Prompt 1.5 — Snapshot builder (rakit per-menit)
**Deliverable:** `flowdesk-p1-snapshot.zip` · **PRD:** #7, #8, #9
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement services/engine/src/engine/snapshot.py that assembles ONE Snapshot (schema_version 1) for a given instrument + minute, by orchestrating iv -> greeks -> exposure -> field -> levels, and stamping session state.

PRODUCE:
- build_snapshot(instrument, ts_utc, chain, forward, rate, session_state, axis) -> Snapshot (validated by engine/schema.py from 0.2).
- Compute minute_index from RTH open. Set stale/expired per #9 rules (engine receives session_state; do not re-implement calendar here).
- Must output an object that passes the Pydantic validator AND, when serialized, passes the TS zod validator (same keys).
- tests/test_snapshot.py: feed a golden fixture chain -> assert the produced snapshot equals a stored golden snapshot JSON within tolerances (walls EXACT; VOL levels within 1-2 strikes; regime sign exact) per PRD #12 §2.

ACCEPTANCE: snapshot validates under both contracts; golden comparison passes tolerances.
```

## Prompt 1.6 — Feed Adapter + Databento ingest (batched, anti-blok)
**Deliverable:** `flowdesk-p1-feed.zip` · **PRD:** #8 §Feed/#Ingest
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement the FeedAdapter interface with TWO implementations: HistoricalSimAdapter (reads cached Databento files from DATA_DIR) and a LiveAdapter stub interface (no live calls in sandbox). Plus a Databento batch-ingest script.

PRODUCE:
- feed/base.py: FeedAdapter ABC with get_chain(instrument, ts) -> chain rows + get_forward(instrument, ts).
- feed/historical.py: reads pre-downloaded Databento files (GLBX.MDP3) for /ES & /NQ from DATA_DIR, builds the per-minute chain (definition + statistics(OI) + trades(VOL) + mbp-1/bbo(mid)). Document the file layout it expects.
- feed/live.py: interface-compatible stub that documents where the live Databento subscription would attach (FEED_MODE=live). No network in sandbox.
- scripts/ingest_databento.py: BATCHED ingest — ONE schema = ONE full date-range pull (e.g. 5 days at once), NOT a per-day loop. Caches raw to DATA_DIR. Document rate-limit-safe behavior and that it must be run by the user with their API key (no network here). Include 5 dev days + note 2-3 extreme days for golden dataset.
- tests/test_historical.py: using a small bundled fixture (synthetic Databento-shaped files you generate), assert get_chain returns a well-formed chain for a sample minute.

ACCEPTANCE: adapters share one interface; historical adapter parses fixture; ingest script is batched (single range pull per schema) and documented; engine (1.5) can consume the chain.
```

---

# Fase 2 · Storage & API

> 🗄️ **Tujuan fase:** persist snapshot ke TimescaleDB, state "now" di Redis, lalu sajikan via REST + WebSocket, dengan scheduler per-menit. Referensi: PRD #8 (API/WS/DDL), #10 (Replay), #9 (Sesi).

## Prompt 2.1 — TimescaleDB schema + migrations + repo
**Deliverable:** `flowdesk-p2-timescale.zip` · **PRD:** #8 §DDL, #10
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement TimescaleDB storage for derived snapshots in services/api (or a shared db package), with migrations and a repository layer.

PRODUCE:
- db/migrations/0001_init.sql: a hypertable `snapshots` keyed by (instrument, ts), storing the full snapshot JSON (jsonb) plus extracted columns for fast filter: session_date, minute_index, state, regime_sign. Create indexes for (instrument, session_date, minute_index). Add a retention policy comment: keep 90 days (derived-only).
- db/repo.py: async repository with: save_snapshot(snapshot), get_snapshot(instrument, session_date, minute_index), list_sessions(instrument) -> available replay dates, get_range(instrument, session_date, from_minute, to_minute).
- Use asyncpg (pinned) + a thin query layer (no heavy ORM).
- tests/test_repo.py: use a SQLite-or-mock or documented test-double since no DB in sandbox; assert SQL strings + parameter binding shapes are correct (table/columns quoted). Document how to run real integration test locally against Timescale.

ACCEPTANCE: migration matches PRD #8 DDL; repo covers replay queries from PRD #10; 90-day retention documented.
```

## Prompt 2.2 — Redis state layer (LIVE now)
**Deliverable:** `flowdesk-p2-redis.zip` · **PRD:** #8 §Redis
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement the Redis "current state" layer in services/api/src/api/state.py.

PRODUCE:
- Redis key scheme (document it): flowdesk:now:{instrument} -> latest snapshot JSON; flowdesk:session:{instrument} -> current session state; pub/sub channel flowdesk:updates:{instrument} for WS fan-out.
- set_now(instrument, snapshot) publishes to the channel; get_now(instrument); subscribe helper for the WS layer.
- Use redis-py asyncio (pinned).
- tests/test_state.py: use fakeredis (pinned) to verify set/get/publish round-trip and key names.

ACCEPTANCE: keys match PRD #8; publish triggers a message consumable by a subscriber; fakeredis tests pass by inspection.
```

## Prompt 2.3 — FastAPI REST endpoints
**Deliverable:** `flowdesk-p2-rest.zip` · **PRD:** #8 §REST, #6, #10
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement the REST API in services/api with these endpoints (exact paths from PRD #8):
- GET /api/health -> {status, feed_mode, version}
- GET /api/snapshot?instrument=ES|NQ -> latest snapshot (from Redis); 404 if none.
- GET /api/replay/sessions?instrument=ES|NQ -> available replay dates (from Timescale).
- GET /api/replay?instrument&date&from_minute&to_minute -> ordered snapshots for playback.
- GET /api/me -> current user {discord_id, has_desk, last_checked} (wired in Phase 3; here return 401 if no session).
- POST /api/me/recheck -> re-run access check (stub that Phase 3 fills; here return 401 if no session).

REQUIREMENTS:
- All data endpoints (snapshot, replay) MUST be gated: 403 if the request has no valid DESK session. Provide a dependency `require_desk()` placeholder that Phase 3 implements; for now it reads a session and 401/403s. Document the seam.
- Pydantic response models reuse the contract from packages/contracts mirror (engine/schema.py).
- CORS from CORS_ORIGINS env. Structured error responses {error, code}.
- tests/test_rest.py: FastAPI TestClient covering 200/401/403/404 paths with mocked repo+state.

ACCEPTANCE: paths exactly match PRD #8; gating seam present (T-09: non-DESK -> 403); responses validate against the contract.
```

## Prompt 2.4 — WebSocket live push
**Deliverable:** `flowdesk-p2-ws.zip` · **PRD:** #8 §WS, #9 (STALE)
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement the WebSocket endpoint /ws?instrument=ES|NQ in services/api that streams the latest snapshot on connect and on every new minute.

PROTOCOL (document precisely):
- On connect (after DESK gating): send {type:"snapshot", data:<Snapshot>} with current state.
- On each engine update (via Redis pub/sub): push {type:"snapshot", data:<Snapshot>}.
- Heartbeat: server sends {type:"ping"} every 15s; client replies {type:"pong"}.
- On feed gap -> snapshots arrive with state="STALE"/stale=true; client holds last frame (document this contract for FE).
- Close codes: 4401 (no session), 4403 (no DESK).

PRODUCE:
- ws.py endpoint + a connection manager subscribing to flowdesk:updates:{instrument}.
- tests/test_ws.py: TestClient websocket test (mocked pub/sub) verifying connect-snapshot, push on publish, ping/pong, and gating close codes.

ACCEPTANCE: protocol documented + matches FE expectations; gating enforced; STALE passthrough defined.
```

## Prompt 2.5 — Scheduler/worker per-menit
**Deliverable:** `flowdesk-p2-scheduler.zip` · **PRD:** #7 (siklus), #9 (state)
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement the per-minute worker in services/api/src/api/worker.py (or services/worker) that drives the whole cycle.

LOOP (every minute, aligned to wall clock minute in ET):
1. Determine session state (implement the calendar/state machine from PRD #9 here: PREMARKET/LIVE/STALE/CLOSED/HOLIDAY using CME calendar; half-days; feed-gap 1-2min -> STALE + hold).
2. If LIVE: pull chain via FeedAdapter (FEED_MODE selects historical/live) -> build_snapshot (engine) -> save to Timescale + set_now in Redis (publishes WS).
3. If STALE: re-publish last snapshot with stale=true.
4. If CLOSED/HOLIDAY: idle.

PRODUCE:
- session.py: the state machine + a determine_state(now, calendar) pure function with unit tests (T-07 boundaries: 09:30 open, 16:00 close, half-day 13:00, holiday).
- worker.py: the scheduler loop (asyncio), wired to engine + repo + state. Make the loop testable (inject clock + feed + repo).
- tests/test_session.py (T-07) and tests/test_worker.py (one tick produces+stores+publishes a snapshot, with mocks).

ACCEPTANCE (PRD #12 T-07,T-08): state machine correct at boundaries; gap -> STALE + hold; one worker tick yields a stored+published snapshot.
```

---

# Fase 3 · Auth (Discord OAuth + Gating)

> 🔐 **Tujuan fase:** akses = role DESK di server Discord Flowjob.id. Implementasi OAuth + sesi + gating yang mengisi seam dari Fase 2. Referensi: PRD #6 (Auth), #0 §8§9.

## Prompt 3.1 — Discord OAuth + sesi + check_access
**Deliverable:** `flowdesk-p3-oauth.zip` · **PRD:** #6
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement Discord OAuth2 + session in services/api, filling the require_desk() seam from Phase 2.

FLOW (document exactly, per PRD #6):
- GET /api/auth/login -> redirect to Discord authorize (scopes: identify guilds.members.read), with state (CSRF) stored signed.
- GET /api/auth/callback -> exchange code for token, fetch the user's guild member object for DISCORD_GUILD_ID, check if roles include DISCORD_DESK_ROLE_ID -> has_desk. Create a signed session.
- POST /api/auth/logout -> clear session.
- check_access(session) -> {discord_id, has_desk, last_checked}. Re-check rule: at login + daily(>24h). If role revoked -> grace until end of day ET (document the grace computation in ET).

PRODUCE:
- auth.py (routes), session.py (signed cookie: HttpOnly+Secure+SameSite=Lax, 7d, signed with SESSION_SECRET), discord_client.py (HTTP calls abstracted behind an interface so they can be mocked; NO network in sandbox — provide a FakeDiscordClient for tests).
- require_desk() dependency now fully implemented: 401 no session, 403 session-without-DESK, allow if has_desk (respecting grace).
- Wire /api/me and /api/me/recheck (recheck forces an immediate Discord re-check via the client interface).
- tests/test_auth.py: callback happy path (has DESK), no-DESK path (403), revoked+grace path, recheck path — all using FakeDiscordClient.

ACCEPTANCE (PRD #12 T-09): non-DESK blocked at all data endpoints; grace logic correct in ET; cookie flags exact; secrets only from env.
```

## Prompt 3.2 — Gating response contract untuk FE (preview-blur)
**Deliverable:** `flowdesk-p3-gating-contract.zip` · **PRD:** #6 (denied), #4
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Define and implement the backend contract the FE uses to render the denied/preview-blur experience and onboarding, so Phase 4 can build UI against it.

PRODUCE:
- Extend /api/me to return an enum access_state: "ANON" | "NO_DESK" | "DESK" plus cta{join_url, buy_url:"https://flowjob.id", recheck_supported:true}.
- A documented FE contract doc (FE_AUTH_CONTRACT.md) describing: ANON -> show login CTA; NO_DESK -> blurred preview + join/buy CTA + "Saya sudah punya DESK — cek ulang" button (calls POST /api/me/recheck); DESK -> full app. Include all 6 error states from PRD #6 with HTTP codes + FE copy (Indonesian) for each.
- A tiny mock server fixture (or recorded JSON responses) for each access_state so the FE can develop without a live Discord.
- tests/test_me_contract.py: assert /api/me shape for each state.

ACCEPTANCE: access_state covers ANON/NO_DESK/DESK; 6 error states documented with copy; mock fixtures provided for FE.
```

---

# Fase 4 · Dashboard Frontend (layar utama)

> 📈 **Tujuan fase:** layar utama — heatmap WebGL + profil garis + sumbu bersama + topbar + toolbar glass + scrubber/replay + settings + auth UI. Patuhi token desain (Fase 0.3) dan layout terkunci. Referensi: PRD #4 (Dashboard), #2 (Desain), #5 (Settings), #8 (kontrak data), #0.

> ⚠️ **Penting untuk SEMUA prompt Fase 4:** FE harus bisa dikembangkan TANPA backend hidup. Tiap prompt WAJIB meminta agent menyertakan **mock data** (snapshot fixture valid sesuai kontrak #8) + **Storybook/preview route** agar komponen bisa dilihat tanpa server. Angka selalu JetBrains Mono. Tidak ada hex hard-coded — hanya token.

## Prompt 4.1 — App shell + design system components
**Deliverable:** `flowdesk-p4-shell.zip` · **PRD:** #2, #4
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Build the Next.js app shell + base component library in apps/web consuming packages/tokens (0.3) and packages/contracts (0.2).

PRODUCE:
- App Router layout with theme provider (dark default, light toggle via [data-theme]), self-hosted fonts wired (@font-face from tokens), global CSS importing tokens.css + tailwind preset.
- Primitive components (all token-driven, no hard-coded hex): Button, IconButton, SegmentedControl (for ES|NQ), Toggle, Pill, Tooltip, Panel/Surface, Divider, NumberReadout (JetBrains Mono, tabular-nums), Spinner, BlurOverlay.
- A mock-data module: a valid Snapshot fixture (ES + NQ) matching contract, plus a small store (zustand) holding {snapshot, instrument, theme, connectionState}.
- A /preview route (or Storybook config) rendering every primitive in dark+light.
- ANTI-AI-LOOK enforced: spacing from scale, restrained radius, monochrome chrome + turquoise/crimson only for data.

ACCEPTANCE: shell renders in dark+light; primitives match tokens exactly; mock snapshot validates against contract; numbers are mono+tabular.
```

## Prompt 4.2 — WebGL heatmap renderer (field projection)
**Deliverable:** `flowdesk-p4-heatmap.zip` · **PRD:** #4 (heatmap), #2 (ramp), #8 (field)
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Build the core WebGL heatmap component (apps/web) that renders snapshot.field as a TRACE-style gamma/delta field. This is the centerpiece — it must look like premium data-art, not a chart library default.

REQUIREMENTS:
- Input: snapshot.field {price_grid[], gamma[], delta[]} + axis. X = intraday time, Y = price/strike, color = exposure magnitude/sign.
- Color ramp from tokens: dark turquoise->black->crimson, light turquoise->white->crimson, interpolated in OKLab/LCH inside the shader (implement the conversion in GLSL; document it). Smooth (interpolated) rendering with an optional block toggle.
- Use regl or raw WebGL2 (pin version). Upload field as a texture; fragment shader maps value->ramp. 60fps target; handle resize + devicePixelRatio.
- Basis toggle Gamma/Delta switches which array is rendered.
- Colorbar component labeled "Gamma ($ Notional)" / "Delta" accordingly.
- Must render from the mock snapshot with NO backend.
- Graceful WebGL-unavailable fallback message.

ACCEPTANCE: renders mock field smoothly; ramp matches tokens exactly in both themes; gamma/delta toggle works; colorbar labeled; no chart-lib default look.
```

## Prompt 4.3 — Profil garis kiri + sumbu harga bersama
**Deliverable:** `flowdesk-p4-profile-axis.zip` · **PRD:** #4 (layout terkunci), #0
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Build the LEFT profile line panel + the SINGLE shared centered price/strike axis, per the locked layout.

LOCKED LAYOUT (from PRD #4):
- Single full-width screen: LEFT = one profile line (~22% width), RIGHT = heatmap (4.2), sharing ONE centered Strike/Price axis.
- Profile line: a SINGLE line, color-coded turquoise (positive) / crimson (negative), crossing zero; NO numbers on it, NO gradient fill. Toggle Net GEX / Net DEX (VOL-based; no 0DTE toggle).
- Shared axis: vertical strike axis labeled every 5 points once (ES) / 10 (NQ); current price = dashed line with a SINGLE price tag. The axis is shared by both panels (aligned Y).

PRODUCE:
- ProfileLine component (SVG or canvas) reading snapshot.profile, drawing net_gex or net_dex as one signed line, color by sign, zero baseline.
- SharedAxis component owning the Y-scale; both ProfileLine and Heatmap consume the same scale (lift scale to the store/context). Dashed current-price line + single tag.
- Render from mock snapshot; verify alignment between profile and heatmap rows.

ACCEPTANCE: exactly one shared axis; profile is one signed line w/o numbers/gradient; GEX/DEX toggle; price tag single + dashed; left ~22% width.
```

## Prompt 4.4 — Topbar + segmented ES|NQ + regime bar
**Deliverable:** `flowdesk-p4-topbar-regime.zip` · **PRD:** #4 (regime), #0
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Build the thin topbar (44px) with instrument switch and the regime indicator.

REQUIREMENTS (PRD #4):
- Topbar height 44px: left = FlowDesk wordmark (Space Grotesk); center/left = SegmentedControl ES|NQ; right = connection state dot (LIVE/STALE/REPLAY) + settings icon.
- Regime indicator = a BAR/PILL that goes turquoise<->crimson by net-gamma sign (NOT a speedometer/gauge — explicitly avoid the norak look), with a stability % rendered in JetBrains Mono. Positive=pinning (turquoise), negative=volatile (crimson). Include a tiny label ("PINNING"/"VOLATILE").
- All values from snapshot.regime. Render from mock.

ACCEPTANCE: topbar 44px; ES|NQ switches instrument in store; regime is bar/pill (no gauge) with mono stability %; colors by sign.
```

## Prompt 4.5 — Floating glass toolbar (auto-fade) + toggles
**Deliverable:** `flowdesk-p4-toolbar.zip` · **PRD:** #4 (toolbar)
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Build the floating glass toolbar overlaying the chart, with the view toggles.

REQUIREMENTS (PRD #4):
- Floating, glassmorphism-lite (subtle, not cheesy), positioned over the chart; AUTO-FADE after 2.5s idle, reappears on pointer move/hover.
- Controls: Net GEX/Net DEX toggle (profile), Gamma/Delta toggle (heatmap basis), Heatmap smooth/block toggle, theme toggle, and a Key-Levels selector (Wall Top 1/2/3 picker per PRD #4 — user chooses how many walls to show).
- Toolbar state persists to the store; reflects current snapshot.
- Keyboard accessible; respects reduced-motion.

ACCEPTANCE: auto-fade 2.5s + reappear; all toggles wired to store; Top 1/2/3 wall picker present; subtle glass (anti-AI-look).
```

## Prompt 4.6 — Scrubber + replay controls
**Deliverable:** `flowdesk-p4-scrubber.zip` · **PRD:** #10 (Replay), #4
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Build the bottom scrubber (56px) + replay controls, against the replay contract (PRD #10 / API 2.3).

REQUIREMENTS:
- Bottom bar 56px: a timeline scrubber spanning the session minutes; current position marker; time readout (mono, ET).
- Controls: play/pause, speed 1x/2x/4x, step +/-1 minute, a session/date selector (from GET /api/replay/sessions), REPLAY badge when not live, and a "Kembali ke LIVE" button.
- Modes: LIVE (scrubber tracks newest minute) vs REPLAY (pauses live, plays stored snapshots from GET /api/replay). Entering replay sets store mode + badge.
- Availability rules from PRD #10 (today available >1hr after open; prior sessions; past dates if data). Use mock list of sessions + mock snapshot frames.

ACCEPTANCE: scrubber 56px; play/pause/speed/step work on mock frames; REPLAY badge + back-to-LIVE; date selector from sessions; matches PRD #10 availability.
```

## Prompt 4.7 — WebSocket client + STALE handling
**Deliverable:** `flowdesk-p4-realtime.zip` · **PRD:** #8 (WS), #9 (STALE)
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement the realtime data layer in apps/web connecting to /ws (protocol from API 2.4) and feeding the store.

REQUIREMENTS:
- WS client: connect with instrument, handle {type:"snapshot"} -> update store; respond to ping with pong; auto-reconnect with backoff; map close 4401->re-login, 4403->no-DESK state.
- STALE handling: when snapshot.state=="STALE"/stale=true, KEEP showing last good frame + show a STALE indicator (per PRD #9). Connection dot reflects LIVE/STALE/REPLAY.
- A dev toggle to switch between live WS and mock-feed (replays bundled fixtures on a timer) so FE works with no backend.
- Unit tests for the reducer logic (snapshot apply, stale hold, reconnect state) using a fake socket.

ACCEPTANCE: applies snapshots to store; ping/pong; STALE holds last frame + indicator; mock-feed mode works offline; close codes mapped.
```

## Prompt 4.8 — Settings slide-in panel
**Deliverable:** `flowdesk-p4-settings.zip` · **PRD:** #5 (Settings)
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Build the Settings slide-in panel (right, 360px) per PRD #5.

REQUIREMENTS:
- Slide-in from right, width 360px, glass surface, ESC/overlay to close, focus-trap.
- Sections: Tampilan (theme Dark/Light default Dark; profile basis Net GEX/Net DEX default Net GEX; heatmap basis Gamma/Delta default Gamma; smooth/block; default instrument ES; timezone display ET) and Akun (DESK status badge, Discord linked indicator, "Kelola langganan -> flowjob.id" link, last role-check timestamp).
- Persist all prefs to localStorage key `flowdesk.prefs` (document the schema); hydrate on load; no server presets in v1.
- Account section reads /api/me (use mock fixtures from 3.2 for offline dev).

ACCEPTANCE: 360px right slide-in; defaults exactly Dark/Gamma/Net GEX/ES/ET; prefs persist to flowdesk.prefs; Akun shows DESK + last check; no presets.
```

## Prompt 4.9 — Auth UI (login, preview-blur, recheck)
**Deliverable:** `flowdesk-p4-authui.zip` · **PRD:** #6, #3 (CTA), #4
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Build the auth-aware UI states in apps/web against the FE_AUTH_CONTRACT (3.2).

REQUIREMENTS (PRD #6):
- ANON: a login screen with "Masuk dengan Discord" (-> /api/auth/login) over a blurred dashboard preview.
- NO_DESK: full dashboard rendered but BLURRED behind a BlurOverlay with: join Flowjob.id CTA + beli DESK CTA (https://flowjob.id) + "Saya sudah punya DESK — cek ulang" button (POST /api/me/recheck, with loading + success/fail toast).
- DESK: full unblurred app.
- Render all 6 error states (from 3.2) with Indonesian copy. Drive everything from /api/me mock fixtures so it works offline.
- Route guard: wrap the dashboard so access_state controls blur/CTA.

ACCEPTANCE: three states render from mocks; recheck button calls endpoint + handles result; CTAs point to flowjob.id; copy in Indonesian; preview genuinely blurred (not hidden).
```

---

# Fase 5 · Landing Page Sinematik

> 🚀 **Tujuan fase:** landing page premium yang storytelling → showcase → edukasi → konversi (CTA Discord/DESK). Pakai **Lenis (smooth scroll) + GSAP ScrollTrigger (sinematik) + Three.js (hero data-art)**. Estetika harus data-art futuristik, BUKAN template SaaS generic. Referensi: PRD #3 (Landing), #2 (Desain), #0.

> ⚠️ **Anti hasil buruk:** wajib pakai token warna terkunci (turquoise/crimson, dark base #000), font Space Grotesk + JetBrains Mono. DILARANG: gradient ungu SaaS, Inter, hero "satu tombol di tengah" klise, animasi norak. Hormati prefers-reduced-motion.

## Prompt 5.1 — Scaffold landing + Lenis smooth scroll + struktur seksi
**Deliverable:** `flowdesk-p5-landing-scaffold.zip` · **PRD:** #3, #2
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Scaffold the marketing landing page (apps/web route group e.g. (marketing)/page) with Lenis smooth scroll and the full section skeleton. No heavy 3D yet (added in 5.2).

REQUIREMENTS:
- Install + wire Lenis (pin version) for buttery smooth scroll; respect prefers-reduced-motion (disable smoothing). Document setup.
- Section skeleton in this narrative order (PRD #3): (1) Hero, (2) "Apa itu FlowDesk" / masalah->solusi, (3) Showcase fitur (heatmap, profil, regime, replay) , (4) Cara kerja (3 langkah), (5) Kredibilitas/akurasi (validasi vs SpotGamma/GEXBOT), (6) Pricing/CTA (DESK via flowjob.id), (7) FAQ, (8) Footer (with financial disclaimer placeholder).
- Use design tokens only; dark base; Space Grotesk headings; JetBrains Mono for any figures.
- Indonesian copy throughout (write real, persuasive copy — not lorem). Provide a copy.ts with all strings.
- Fully responsive; semantic HTML; accessible landmarks.

ACCEPTANCE: Lenis smooth scroll works + reduced-motion fallback; all 8 sections present with real Indonesian copy; tokens only; no 3D yet.
```

## Prompt 5.2 — Three.js hero data-art (reaktif kursor)
**Deliverable:** `flowdesk-p5-hero-threejs.zip` · **PRD:** #3 (hero), #2 (warna)
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Build the Three.js hero background for the landing page — a "painted"/data-art gamma-field texture that subtly reacts to the cursor, themed turquoise<->crimson.

REQUIREMENTS:
- Three.js (pin version), a full-bleed shader plane behind the hero headline. A custom fragment shader generates a flowing field reminiscent of a gamma heatmap: turquoise (positive) blending through dark to crimson (negative), evolving slowly (time uniform).
- Cursor reactivity: mouse position feeds a uniform that warps/ripples the field gently (no jarring motion). On mobile, fall back to slow autonomous motion.
- Colors strictly from tokens (#40E0D0 / #E0183C / #000). Perceptual blend in shader.
- Performance: cap DPR, pause rendering when tab hidden / when hero off-screen (IntersectionObserver). Respect prefers-reduced-motion (render a static frame).
- The hero headline + subcopy (Indonesian) + primary CTA ("Gabung & ambil DESK") sit above the canvas with strong contrast.
- Must degrade gracefully if WebGL unavailable (static gradient-from-tokens fallback, NOT a generic purple).

ACCEPTANCE: hero shader runs 60fps, reacts to cursor subtly, colors exact, pauses off-screen/hidden, reduced-motion + no-WebGL fallbacks present.
```

## Prompt 5.3 — GSAP ScrollTrigger sinematik per seksi
**Deliverable:** `flowdesk-p5-gsap-scenes.zip` · **PRD:** #3
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Add GSAP + ScrollTrigger so each landing section animates in as a cinematic scene as the user scrolls (integrating with Lenis from 5.1).

REQUIREMENTS:
- GSAP + ScrollTrigger (pin versions), synced to Lenis scroll (use Lenis' scroll event to drive ScrollTrigger.update).
- Per-section choreography (document each): hero text reveal; problem->solution color transition (turquoise->crimson accent shift); feature showcase items that pin + step through (heatmap, profile, regime, replay) with captions; "cara kerja" 3-step horizontal/stepped reveal; numbers (akurasi/stats) count-up in JetBrains Mono; CTA section emphasis.
- Motion must be tasteful & restrained (premium, not flashy). Use the motion durations/easings from tokens. Respect prefers-reduced-motion (animations become instant/opacity-only).
- No layout shift / CLS; cleanup ScrollTriggers on unmount.

ACCEPTANCE: each section animates on scroll synced with Lenis; reduced-motion path; count-ups mono; no CLS; cleanup on unmount.
```

## Prompt 5.4 — Mini demo heatmap interaktif + pricing/CTA/FAQ
**Deliverable:** `flowdesk-p5-demo-cta.zip` · **PRD:** #3 (demo, konversi), #4, #10
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Build the interactive proof section + conversion blocks for the landing page.

REQUIREMENTS:
- Mini interactive heatmap demo embedded in the showcase: reuse the WebGL heatmap (Fase 4.2) fed by a BUNDLED 30-minute replay fixture (no backend), with a tiny scrubber the visitor can drag to feel the product. Label it clearly as a demo. Works fully offline.
- Pricing/CTA block: DESK tier card. IMPORTANT: price + benefits are placeholders pulling from copy.ts constants (PRICE, BENEFITS[]) — leave them clearly marked TODO-FROM-OWNER in copy.ts so the owner fills real numbers; render them nicely. Primary CTA -> https://flowjob.id ; secondary CTA -> join Discord.
- FAQ accordion (Indonesian, real questions: apa itu 0DTE, kenapa /ES & /NQ, akurasi, cara akses DESK, apakah ini saran finansial->no).
- Footer with a financial disclaimer (Indonesian): data informasional, bukan saran investasi.
- Tokens only; mono numbers.

ACCEPTANCE: demo heatmap interactive offline from fixture; pricing card renders with owner-fillable PRICE/BENEFITS; CTAs to flowjob.id + Discord; FAQ + disclaimer present.
```

---

# Fase 6 · Ops, Testing & CI/CD

> 🛡️ **Tujuan fase:** rakit semua jadi satu sistem yang bisa di-deploy, tervalidasi akurasinya, terpantau, dan punya pipeline rilis. Referensi: PRD #11 (Ops), #12 (Testing), #13 (CI/CD), #8 (infra).

## Prompt 6.1 — Docker Compose full-stack + env templates
**Deliverable:** `flowdesk-p6-compose.zip` · **PRD:** #8 (compose), #11
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Assemble the deployable backend stack with Docker Compose + env templates, wiring engine/worker + api + TimescaleDB + Redis (FE deploys to Vercel separately).

PRODUCE:
- infra/docker-compose.yml: services for api (FastAPI/uvicorn), worker (the per-minute scheduler), timescaledb, redis. Healthchecks, restart: unless-stopped, named volumes for TimescaleDB + DATA_DIR. Networks. Document ports.
- Dockerfiles for api + worker (multi-stage, python 3.11-slim, pinned deps).
- infra/.env.example consolidating ALL env keys (from locked contract) with comments; document which are secrets.
- infra/README.md: how to bring the stack up locally (historical FEED_MODE) and on the Hetzner CPX31 prod / CPX21 dev VPS; how to run DB migrations; how the FE (Vercel) points at the API via CORS_ORIGINS.
- A Makefile target `stack-up` / `stack-down`.

ACCEPTANCE: compose defines api+worker+timescale+redis with healthchecks+volumes; Dockerfiles pinned; env template complete; bring-up documented for dev + Hetzner.
```

## Prompt 6.2 — Golden dataset regression harness
**Deliverable:** `flowdesk-p6-regression.zip` · **PRD:** #12
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Build the accuracy regression harness that locks engine correctness against a golden dataset (PRD #12).

PRODUCE:
- tests/golden/: a few committed golden snapshot JSONs generated from fixture chains (5 plumbing-day samples + 2-3 extreme-day samples: trending, pinning/range, OPEX/high-vol, half-day). Document provenance + that the owner regenerates from real Databento later.
- A regression runner that recomputes snapshots from the fixture chains and compares to golden with the LOCKED tolerances: Call/Put Wall (OI) EXACT; Gamma Flip / Largest GEX/DEX (VOL) within 1-2 strikes; regime sign EXACT; greeks vs Black-76 < 1e-6.
- A clear diff report on failure (which field, expected vs actual, by how much).
- pytest integration so it runs in CI (Fase 6.4). A `make regression` target.
- A REGRESSION.md explaining how to add/refresh golden cases and the eyeball checklist vs SpotGamma/GEXBOT.

ACCEPTANCE: harness compares to golden with exact locked tolerances; emits readable diffs; runnable via make + pytest; docs for refreshing goldens.
```

## Prompt 6.3 — Monitoring, heartbeat & auto-restart
**Deliverable:** `flowdesk-p6-monitoring.zip` · **PRD:** #11
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement operational reliability for RTH hours per PRD #11.

PRODUCE:
- A heartbeat: the worker emits a heartbeat each successful minute cycle; a watchdog detects a missed cycle during RTH and (a) attempts auto-restart of the worker (document via compose restart + an in-process supervisor) and (b) posts an alert to a Discord webhook (DISCORD_OPS_WEBHOOK env — add to env template).
- Health/metrics: extend /api/health with feed_mode, last_snapshot_ts, worker_alive, db_ok, redis_ok. A lightweight /metrics (text) for uptime checks.
- Alert thresholds (document): missed cycle > 2 min during RTH; DB/Redis unreachable; feed gap > 2 min.
- Weekly TimescaleDB backup script (pg_dump) + cron example + restore doc.
- A RUNBOOK.md: what each alert means + remediation steps.

ACCEPTANCE: heartbeat + watchdog + Discord alert on missed RTH cycle; /api/health expanded; backup script + runbook; thresholds documented. (No network in sandbox: webhook call is behind an interface with a Fake for tests.)
```

## Prompt 6.4 — CI/CD pipeline (staging + prod, tests-gate)
**Deliverable:** `flowdesk-p6-cicd.zip` · **PRD:** #13
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Implement the CI/CD pipeline per PRD #13 using GitHub Actions (yaml files), gating deploy on tests.

PRODUCE (.github/workflows/):
- ci.yml: on push/PR -> lint + typecheck (ts + python ruff/mypy) -> unit tests -> regression tests (Fase 6.2). MUST fail-closed: if greeks/regression fail, pipeline stops.
- deploy.yml: on push to release branch -> build images (api, worker) -> deploy to STAGING (FEED_MODE=historical) via SSH/compose on the dev VPS -> smoke test (/api/health, snapshot valid) -> MANUAL APPROVAL gate -> deploy to PRODUCTION (FEED_MODE=live).
- Image tagging :sha + :latest; documented rollback (redeploy previous sha).
- A deploy notification step posting success/fail to the Discord ops webhook.
- DEPLOY.md documenting branches, secrets needed in CI (names only), and the promotion flow.

ACCEPTANCE (PRD #12 AC-C1..C6): full pipeline stages present; regression/greeks failure blocks deploy; staging->approval->prod; rollback + Discord notify documented; secrets only by name.
```

## Prompt 6.5 — Error tracking + telemetri + hardening checklist
**Deliverable:** `flowdesk-p6-telemetry-hardening.zip` · **PRD:** #13, #11
```text
[TEMPEL MASTER PREAMBLE DI SINI]

TASK: Add privacy-aware telemetry + error tracking + a final hardening pass.

PRODUCE:
- Error tracking integration (Sentry-compatible SDK, pinned) for FE + BE behind an interface (DSN from env SENTRY_DSN; no-op if unset). Capture exceptions w/ stack; scrub PII.
- Lightweight telemetry: key events only (login, switch instrument, enter replay, error) sent to a pluggable sink (interface + a console/no-op default; document how to point to PostHog/self-host). NO sensitive PII.
- Security hardening checklist applied + documented (HARDENING.md): session cookie flags, rate limiting on auth + recheck endpoints, CORS allowlist from env, security headers (CSP appropriate for WebGL + Three.js, HSTS), input validation, secrets only in env.
- Add the financial disclaimer surface (onboarding + footer) wiring (copy in Indonesian).
- tests for the telemetry/error interfaces using fakes (no network).

ACCEPTANCE: error tracking + telemetry behind interfaces (no-op offline); HARDENING.md checklist complete; rate limit + CORS + security headers present; disclaimer wired; PII scrubbed.
```
