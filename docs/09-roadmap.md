# 09 — Roadmap

Mapped to current reality (see [`08-status-and-gaps.md`](08-status-and-gaps.md)).
The original phase-by-phase build playbook is preserved at
[`reference/Build-Playbook-PerFase.md`](reference/Build-Playbook-PerFase.md).

## Done (the frame)

- ✅ Engine: Black-76, IV, VOL-based exposure, field grid, levels, optional FLUX.
- ✅ Snapshot contract (pydantic ↔ zod), golden fixture, contract validate step.
- ✅ API: worker, session state machine, REST, WebSocket, Discord OAuth + role gate,
  Redis + Timescale repos.
- ✅ FE primitives: WebGL heatmap, exposure profiles, levels, auth UI, session JSON.
- ✅ Historical feed adapter + cost-aware Databento ingest.

## Next (highest leverage first)

### A. Validation / backtest harness — *mechanism complete, evidence pending*
- Harness wired (`analysis/harness/*`); 109 tests pass. Predictive evals
  (synthetic-OI, FLUX, DDOI, VT) all returned **UNDETERMINED at n=3–4** —
  the gap is statistical power, not method. The 90-day forward run that
  would close this was **dropped by the operator**, so the lensa-lensa
  remain `NOT-VALIDATED` and must NOT drive a regime classifier without
  caveat. See `docs/research/empirical/*` for the per-lens reports.

### B. Frontend rebuild — *in progress (Fog lens live, Flux/Arc next)*
The original frontend (`apps/web/`, `@flowdesk/tokens`) was deleted on
2026-06-15 and is being rebuilt from scratch as `apps/dashboard/`
(Next.js 15 + React 19 + lightweight-charts, port 4321). Current state:

- ✅ App shell, navbar, routing for `/fog /flux /arc /settings`.
- 🔨 **Fog lens** (state-based GEX/DEX positioning, TRACE-inspired):
  minimalist ladder + GEX profile + intraday candles. Synthetic data;
  API wiring deferred but planned alongside visual polish.
- ⏳ **Flux lens** (Hiro-style time-series flow): placeholder.
- ⏳ **Arc lens** (3D vol surface `σ(K,T)`): placeholder.
- ⏳ Wire `@flowdesk/contracts` zod parser to `/api/snapshot` + `/ws`.

Locked design rules (TURQUOISE `#0FB5A8` / CRIMSON `#B5002E`,
Space Grotesk + JetBrains Mono) remain in `02-locked-contract.md` and
the new FE must honor them. A separate `apps/landing/` (Next.js, on
Vercel) is already live.

### C. Wire in the surface — *done*
- ✅ SVI / expected-move (`surface.py`) emitted as optional Snapshot
  fields (commit `691a894`).
- ✅ VEX / CHEX aggregated from `black76` vanna/charm (commit
  `7eeac8b` series), labelled EXPERIMENTAL.

### D. Live feed — *done (kept disarmed)*
- ✅ `LiveAdapter` built with two-key arming (`FEED_MODE=live` AND
  `LIVE_FEED_ARMED=1`), circuit breaker, bounded reconnect; threat
  model in `docs/architecture/live-feed-threat-model.md`. Beta image
  intentionally ships without the second key.

## Later (gated on A)

### E. DDOI / signed-position layer (v3) — needs approval
- A parallel exposure module reconstructing dealer position from signed flow /
  ΔOI, runnable **alongside** VOL-GEX and measured against it via the harness (A).
- Do **not** remove VOL-GEX; this is additive and comparative.

### F. Proprietary metrics
- Deferred. Needs approval and, first, the validation harness to justify them.

## Guiding principle

Every new signal must ship with a way to measure whether it's real. Plumbing is
done; invest in **truth** (validation) before **more** (features).
