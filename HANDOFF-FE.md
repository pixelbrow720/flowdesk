# FlowDesk Frontend — Handoff to Vision-Capable AI

You are taking over the FrontEnd build for FlowDesk. The previous agent had no vision capability — so visual decisions belong to YOU. This document is **technical context + hard rules**, not a build plan. You decide what to build, in what order, how it should look.

---

## What FlowDesk is (3 sentences)

A paid 0DTE GEX/DEX options terminal for **/ES** and **/NQ** futures (NOT SPX). The web app (Next.js 14 in `apps/web/`) consumes a per-minute `Snapshot` contract emitted by a Python engine via FastAPI. The product's value proposition is **honesty**: every experimental lens is labeled, locked VOL-GEX math is the foundation, and no metric is presented as "validated" without empirical proof.

---

## Visual reference: `1.png`

`1.png` (repo root) is a SpotGamma **SPX** dashboard screenshot — a structural reference the user wants you to draw inspiration from. Look at it, decide what's worth taking, what to ignore. Your call.

**Hard constraints when interpreting it** (from the locked contract — non-negotiable):

- FlowDesk is /ES and /NQ, not SPX. You will NOT have SPX-only data.
- 1.png inverts color semantics (purple for positive). FlowDesk's locked tokens are `TURQUOISE = "#40E0D0"` (stabilising/positive) and `CRIMSON = "#E0183C"` (destabilising/negative). **Locked. Do not invert. Do not replace.**
- 1.png has a "Market Makers" cohort dropdown. FlowDesk has no dealer-cohort data model. Don't add what doesn't exist in the contract.
- Per `docs/02-locked-contract.md`: no replicating SpotGamma numbers/methods/branding. Take layout inspiration; do not copy IP.

Beyond those constraints — visual choices are yours.

---

## Hard rules (locked, do not violate)

1. **Snapshot contract is mirrored** between Python (`services/engine/src/engine/schema.py`) and TypeScript (`packages/contracts/src/snapshot.ts`) and prose (`packages/contracts/CONTRACT.md`). If you need a new Snapshot field, edit ALL THREE atomically. New fields must be optional + nullable + additive. `schema_version` stays `1`.

2. **No live Databento data pulls.** The account was locked twice. All FE work uses offline session JSON in `apps/web/public/sessions/`.

3. **Color tokens are LOCKED.** TURQUOISE = stabilising/positive. CRIMSON = destabilising/negative. Never inverted. Two helper constants `BONE = "#E8E2D0"` and `COAL = "#0A0A0A"` live as component-private (NOT in `@flowdesk/tokens`); they're flagged with comments — leave them or promote them, your call.

4. **HIRO line is NOT colored by sign** (turquoise/crimson reserved for GEX semantics; HIRO is buy/sell pressure, different physics). Use `fg-muted` (theme-neutral chrome). Already implemented this way in `apps/web/components/heatmap/hiro-line.tsx`.

5. **EXPERIMENTAL labeling.** If you render any of these unvalidated lenses — `synthetic_oi`, `synthetic_oi_tiered`, `synthetic_oi_decay`, `total_hedging`, `ddoi`, `exposure_ext`, `surface`, `proprietary` — they MUST carry a visible "EXPERIMENTAL / not validated" disclaimer. The MVP-locked fields (`profile`, `levels`, `regime`, `field`, `hiro`, `ohlc`) need no badge.

6. **Engine purity.** The engine has no calendar, no clock, no state. The API owns time. The FE consumes whatever the contract says. Don't push UI concerns into the engine.

---

## Tech stack

- Next.js 14 App Router, React 18, TypeScript strict
- Zustand state (`apps/web/lib/store.ts` — `useDashboardStore`)
- Tailwind + `@flowdesk/tokens` CSS variables (themed dark/light)
- Contract: `import { Snapshot, parseSnapshot, safeParseSnapshot } from "@flowdesk/contracts"` — always validate WS frames via zod (see `apps/web/lib/ws/reducer.ts`)
- Package manager: pnpm 9.7.0 via corepack (NOT on PATH; use `corepack pnpm <cmd>`)
- Existing routes:
  - `app/page.tsx` — placeholder skeleton (the `/` route is currently empty)
  - `app/preview/dashboard/page.tsx` — assembled dashboard, mock or live WS
  - `app/preview/real/page.tsx` — REPLAY against `apps/web/public/sessions/*.json`
  - `app/preview/auth/page.tsx` — auth gate UI (NOT yet composed with dashboard)
- Testing:
  - Unit: `cd apps/web; corepack pnpm exec vitest run` (currently 19 tests)
  - E2E: `cd apps/web; corepack pnpm exec playwright test` (smoke only, hollow — see §below)
  - Typecheck: `node_modules/.bin/tsc -p apps/web --noEmit`
- Dev server: `cd apps/web; corepack pnpm dev` → `http://localhost:3000`

### PowerShell 5.1 caveat
Default Windows shell does NOT support `&&`. Use `;` separator or two commands.

---

## What's already there (so you don't rebuild)

- Heatmap canvas + WebGL2 shader (`apps/web/components/heatmap/`)
- Heatmap overlay (price line, OHLC candles, gamma_flip dot per candle, walls if data) — `heatmap-overlay.tsx`
- HIRO line overlay with right-axis $B (`hiro-line.tsx`, P0 wave, fg-muted)
- GEX-by-strike vertical profile (`components/chart/profile-line.tsx`)
- Scrubber/replay (`components/scrubber/`)
- Topbar, key-levels-bar, regime-bar, ET-clock, connection-dot
- Settings panel, AuthGate, UI primitives (Pill, Tooltip, SegmentedControl, NumberReadout)
- Time-evolving heatmap in REPLAY mode (P0 wave: `buildReplayField2D` projects per-bin frame.field)

LIVE-mode rolling buffer is NOT yet implemented (store keeps `frames=[]` in LIVE). REPLAY mode in `/preview/real` is the path that actually shows time-evolution today.

---

## Honest gaps you should know

- **Smoke test is hollow.** `apps/web/e2e/smoke.spec.ts` only checks shell exists — a heatmap that's NaN-filled or all-black would pass. Visual regression is undetectable today. Worth fixing if you'll iterate visually.
- **Some session JSONs broken.** `{ES,NQ}_2026-06-01.json` have `hiro=null` in all 390 frames. `{ES,NQ}_2026-06-09.json` are clean. Up to you whether to drop the broken ones, regenerate, or add UI fallback.
- **`heatmapBasis` toggle in store may be dead-wired** — `heatmap.tsx:95` derives basis from `profileMetric`, not from `heatmapBasis`. Verify before relying on it.
- **`/` route is a placeholder.** No production-grade root route yet. AuthGate is not yet composed with the assembled dashboard.

---

## What the contract gives you (Snapshot fields)

Always present (locked VOL-basis, no badge needed when rendered):
- `instrument`, `session_date`, `ts`, `minute_index`, `state` (PREMARKET/LIVE/STALE/CLOSED/HOLIDAY), `stale`, `expired`
- `forward`, `rate`
- `axis` (strike grid bounds + step)
- `regime` (net_gamma, sign, stability_pct)
- `profile` (per-strike net_gex / net_dex)
- `field` (price_grid, gamma, delta — TRACE-style projected exposure surface)
- `levels` (call_walls, put_walls, gamma_flip, largest_gex, largest_dex)

Optional (some present in session JSONs, some always null):
- `ohlc` (front-future minute OHLC) — present
- `hiro` (total/calls/puts/zerodte/retail signed dealer flow $B) — present in 06-09 sessions
- `synthetic_oi` / `synthetic_oi_tiered` / `synthetic_oi_decay` — null in session JSONs (worker-only)
- `total_hedging` (gamma/charm/vanna_hedge) — present
- `surface` (SVI a/b/rho/m/sigma + atm_vol + expected_move + variance_nonneg) — present
- `ddoi` (gex, sign) — null in session JSONs (worker-only)
- `proprietary` (oi_gamma_flip, abs_gamma_strike, hedge_wall) — null in session JSONs (worker-only)
- `exposure_ext` (net_vex, vex_sign, net_chex, chex_sign) — present

Read `packages/contracts/src/snapshot.ts` for the exact zod schema. Read `docs/04-engine.md` for what each field MEANS.

---

## Files worth reading first

- `AGENTS.md` (root) — agent/role rules + golden discipline
- `docs/02-locked-contract.md` — every locked value, why
- `docs/04-engine.md` — what the engine produces, every field explained
- `docs/08-status-and-gaps.md` — current state of every feature, lens, known gap
- `packages/contracts/src/snapshot.ts` — wire shape (single source of truth)
- `packages/tokens/src/tokens.ts` — locked design tokens
- `apps/web/lib/store.ts` — Zustand state shape
- `apps/web/components/heatmap/hiro-line.tsx` — newest component, reference for new-component patterns

---

## Verification commands

```powershell
# Frontend
cd apps/web; corepack pnpm exec vitest run               # should be 19 passed
cd apps/web; corepack pnpm exec playwright test          # 1 passed (smoke)
node_modules/.bin/tsc -p apps/web --noEmit               # exit 0

# Contracts (if you touch the mirror)
cd packages/contracts; node_modules/.bin/tsc --noEmit
cd packages/contracts; node_modules/.bin/tsx scripts/validate.ts

# Engine + API (only relevant if you touch backend)
cd services/engine; $env:PYTHONPATH="src"; ../../.venv/Scripts/python.exe -m pytest -q   # 199 passed
cd services/api; $env:PYTHONPATH="src;../engine/src"; ../../.venv/Scripts/python.exe -m pytest -q  # 84 passed

# Dev server
cd apps/web; corepack pnpm dev    # http://localhost:3000
```

---

End of handoff. Build the FE — visual and architectural decisions are yours. Just don't break the locked rules above.
