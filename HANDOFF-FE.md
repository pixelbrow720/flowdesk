# FlowDesk Frontend — Handoff to Vision-Capable AI

**Status:** P0 wave landed (commit `5cbf3d3`). Backend healthy. FE primitives present at `/preview/*`. Production route + auth-gate composition + visual fidelity polish remaining.

**Why this handoff:** the prior CLI agent was non-vision (couldn't read `1.png`). FE work from here benefits from a vision-capable AI that can: (a) actually look at `1.png` (the reference layout), (b) screenshot the running dev server and visually compare, (c) iterate on visual fidelity. This document is your full context — read it before touching code.

---

## 1. Project in 3 sentences

FlowDesk is a paid **0DTE GEX/DEX options terminal** for /ES & /NQ futures (NOT SPX). The project's entire value proposition is **honesty**: every experimental lens is labeled, the locked VOL-GEX math is the foundation, and no metric is presented as "validated" without empirical proof. The web app (Next.js 14 in `apps/web/`) consumes a per-minute `Snapshot` contract emitted by a Python engine via FastAPI; primary FE goal is rendering a dense trader terminal matching the structural reference at `1.png`.

---

## 2. CRITICAL: `1.png` is a SpotGamma SPX reference, NOT the FlowDesk target

**Read this twice before doing anything visual.**

`1.png` (in repo root) is a screenshot of SpotGamma's SPX dashboard, used as **structural inspiration only** — layout zones, density, panel composition. It is **NOT a pixel-replication target**. Reasons:

- Watermark says "SPOTGAMMA"; title says "SPX Gamma Exposure" (we're /ES /NQ, not SPX)
- 1.png inverts color semantics (uses purple/violet for positive). FlowDesk's locked tokens are turquoise=stabilising/positive, crimson=destabilising/negative — **DO NOT FOLLOW 1.png's inversion**.
- 1.png has a "Market Makers" cohort dropdown — FlowDesk has no dealer-cohort data model, **DO NOT ADD this**.
- Per `docs/02-locked-contract.md:88`: "do not 'fix' the engine to match SpotGamma."

**What to take from 1.png:** layout zones (top bar with controls, left vertical GEX-by-strike profile, central time×price heatmap with right-axis HIRO overlay, bottom scrubber), info density, scrubber pattern.

**What to reject:** vendor-specific elements above, color inversion, exact pixel match.

---

## 3. Current FE state (post-P0 commit `5cbf3d3`)

### What exists and works

- `apps/web/app/preview/dashboard/page.tsx` — assembled dashboard (mock or live WS)
- `apps/web/app/preview/real/page.tsx` — REPLAY against pre-captured session JSON in `apps/web/public/sessions/` ← **PRIMARY MVP path**
- `apps/web/app/preview/auth/page.tsx` — auth gate UI (NOT yet composed with dashboard)
- `apps/web/app/page.tsx` — placeholder skeleton (root `/`); NOT the production route yet

### Components landed

- Heatmap canvas + shader (WebGL2; `apps/web/components/heatmap/`)
- HIRO line overlay (`apps/web/components/heatmap/hiro-line.tsx` — single line, fg-muted color, right-axis $B)
- Heatmap overlay with OHLC candles + gamma_flip per-candle dot (`heatmap-overlay.tsx`)
- GEX-by-strike profile (`components/chart/profile-line.tsx`, left vertical)
- Scrubber/replay (`components/scrubber/`)
- Topbar + key-levels-bar + regime-bar + et-clock + connection-dot
- Settings panel + auth-gate + ui primitives (Pill, Tooltip, SegmentedControl, NumberReadout, etc.)

### What's missing (P1, P2, P3 priorities below)

---

## 4. Build priorities (post-P0)

### P1 — Production readiness (DO THESE NEXT)

1. **Production route** — `app/page.tsx` is a placeholder. Either rewrite it as the real assembled dashboard, OR move dashboard to `app/(app)/page.tsx` with proper grouping. Currently the only working dashboard is at `/preview/*` — that's a "dev preview" location, unfit for production.

2. **AuthGate composition with dashboard** — `AuthGate` exists (`components/auth/auth-gate.tsx`) and has its own preview page (`/preview/auth`), but is **NOT wrapped around the dashboard**. Production dashboard MUST gate on DESK entitlement (per the Discord-OAuth flow already wired in the API layer). See PRD reference doc #6.

3. **Session-state badge expansion** — currently only STALE has a Pill component (`dashboard/page.tsx:51-55`). The contract has 5 states: PREMARKET, LIVE, STALE, CLOSED, HOLIDAY. Plus the `expired:true` flag is unhandled. Extend the badge to cover all states with locked color/text mapping.

### P2 — Backend chores that block subsequent FE

4. **LIVE rolling buffer in store** — current store keeps `frames: Snapshot[]` only in REPLAY mode (`apps/web/lib/store.ts:43,107` — frames=[] in LIVE). The new time-evolving heatmap (P0a) currently only works in REPLAY. To make `/preview/dashboard` LIVE mode show actual evolution, extend the store to maintain a rolling buffer (e.g., last 180 frames in LIVE). State-machine concerns: when does buffer start filling (RTH open? first frame? on subscribe?), what happens at STALE, what happens on REPLAY→LIVE transition.

5. **Visual smoke test** — current Playwright smoke (`apps/web/e2e/smoke.spec.ts`) only checks shell exists. A heatmap that's NaN-filled, all-black, or wrong-dimensioned would pass. Add a pixel-diff or structural assertion (e.g., "canvas has non-uniform pixel data after frame[N] load"). This matters because FE iteration risks visual regression.

6. **2026-06-01 sessions broken** — `apps/web/public/sessions/{ES,NQ}_2026-06-01.json` have `hiro=null` in all 390 frames (silent fail in `/preview/real` if user picks them). Either:
   - Drop them from `REAL_SESSIONS` until regenerated, OR
   - Regenerate via `scripts/gen_session_snapshots.py` (requires Python env), OR
   - Add UI fallback `frame.hiro===null → "HIRO data unavailable for this session"`

### P3 — Deferred features (not in 1.png MVP scope; some require backend work)

- HIRO 5-series breakdown view (toggle-gated): contract has `total/calls/puts/zerodte/retail`; MVP renders only `total`
- Walls labels panel (call_walls / put_walls) — not in 1.png but in contract
- Key levels list panel (toggle exists in topbar but no panel)
- Stability gauge (already in contract via `regime.stability_pct`)
- Greek selector (toolbar UI exists but `heatmap.tsx:95` derives basis from `profileMetric` not `heatmapBasis` — toggle may be dead-wired)
- Render of synth-OI / ddoi / VEX-CHEX / surface / proprietary lenses + EXPERIMENTAL badge UX
- HIRO worker/generator unification (deferred backend MEDIUM)
- synth-OI session-gen wiring (deferred backend MEDIUM)

---

## 5. Tech stack & conventions

- **Next.js 14 App Router**, React 18, TypeScript strict
- **State**: Zustand (`apps/web/lib/store.ts` — `useDashboardStore`)
- **Styling**: Tailwind + `@flowdesk/tokens` CSS variables (themed dark/light). Tokens at `packages/tokens/src/tokens.ts`
  - LOCKED color tokens: `TURQUOISE = "#40E0D0"` (stabilising/support), `CRIMSON = "#E0183C"` (destabilising/resistance). DO NOT invert.
  - Local component constants `BONE = "#E8E2D0"` and `COAL = "#0A0A0A"` exist; comments mark them "promote to locked token when expansion approved" — do not use these for new components without same comment.
- **Contract types**: `import { Snapshot, parseSnapshot, safeParseSnapshot } from "@flowdesk/contracts"`. Always validate WS frames via zod (see `apps/web/lib/ws/reducer.ts` for the pattern).
- **Package manager**: pnpm 9.7.0 via corepack (pnpm NOT on PATH; use `corepack pnpm <cmd>`)
- **Dev server**: `cd apps/web; corepack pnpm dev` → `http://localhost:3000`
- **Playwright E2E**: `cd apps/web; corepack pnpm exec playwright test`
- **Vitest unit**: `cd apps/web; corepack pnpm exec vitest run`
- **TypeCheck**: `node_modules/.bin/tsc -p apps/web --noEmit` (from repo root)

### PowerShell 5.1 caveats

The repo dev environment uses PowerShell 5.1 by default on Windows, which **does not support `&&`** as a chain operator. Use either:
- Two separate commands, OR
- `;` as separator (runs second regardless of first's exit), OR
- Subshell `cmd /c "cd ... && ..."` if true short-circuit needed

---

## 6. Hard rules (locked discipline — do not violate)

These are from `docs/02-locked-contract.md` and `AGENTS.md`. Treat as immovable:

1. **Do NOT change the Snapshot contract** without coordinated lockstep edits to `services/engine/src/engine/schema.py` (Python pydantic) AND `packages/contracts/src/snapshot.ts` (zod+TS) AND `packages/contracts/CONTRACT.md` (docs). New experimental fields MUST be `optional + nullable + additive`. `schema_version` stays `1`.

2. **Do NOT pull live Databento data**. The account was locked twice. The CLI sandbox has no network for data. All FE work uses `apps/web/public/sessions/*.json` (offline replay).

3. **Do NOT replicate vendor numbers/UX** that imply FlowDesk has data it doesn't (e.g., the SpotGamma "Market Makers" cohort dropdown, vendor-specific level names).

4. **Color semantics are LOCKED**: turquoise=stabilising/positive, crimson=destabilising/negative. NEVER invert.

5. **EXPERIMENTAL labeling**: any unvalidated lens (synth-OI, ddoi, VEX-CHEX, surface, proprietary) when rendered MUST carry a visible "EXPERIMENTAL / not validated" disclaimer in UI. The MVP path renders only LOCKED-VOL fields (heatmap, levels, hiro, ohlc) so no badge needed yet — but if you start rendering experimental lenses, badge them.

6. **HIRO is NOT colored by sign** (turquoise/crimson reserved for GEX semantics). HIRO line uses `fg-muted` (theme-neutral chrome). This is intentional — buy/sell pressure ≠ stabilising/destabilising.

---

## 7. Honest gaps you should know about

The prior agent (the one that handed you this) ran in a non-vision model and made several decisions on defaults. The redteam attack on its memo found 13 issues; they were either resolved in P0 or deferred. The most relevant for you:

- **No PRD/research justification was found** for the `field-2d.ts` "no historical evolution" comment that was overturned in P0a. The decision was supported by mega-riset:309 + FlowGreeks-Riset:445 (which call for time-evolving exposure), but the original constant-mode rationale wasn't documented anywhere. If you find the reason, surface it.
- **Smoke test is a hollow gate** (P2 #5 above). Visual regression today is undetectable.
- **`heatmapBasis` toggle in store may be dead-wired** — `heatmap.tsx:95` derives from `profileMetric` not `heatmapBasis`. Worth investigating during P2 polish.

---

## 8. Recommended first move

1. **Open `1.png`** with your vision tool. Compare visually with what `corepack pnpm dev` renders at `/preview/real` (canonical session: ES or NQ 2026-06-09). Note structural-vs-cosmetic gaps.
2. **Decide your first priority** from §4 — recommendation: P1 #1 (production route) is highest-impact non-cosmetic; P2 #5 (visual smoke) is highest-leverage if you intend to iterate visually.
3. **Stay disciplined** about §6 hard rules, §2 (1.png is reference, not target), and the EXPERIMENTAL labeling discipline.

---

## 9. Useful files to read first

- `AGENTS.md` (root) — orchestrator/agent rules
- `docs/02-locked-contract.md` — non-negotiable values
- `docs/08-status-and-gaps.md` — current state of every feature, lens, and known gap
- `docs/04-engine.md` — what the engine produces (what your FE consumes)
- `apps/web/lib/store.ts` — Zustand state shape
- `apps/web/components/heatmap/heatmap.tsx` — entry point of the centerpiece
- `apps/web/components/heatmap/hiro-line.tsx` — newest component (P0c reference for new component patterns)
- `packages/contracts/src/snapshot.ts` — zod contract (single source of truth for the wire shape)
- `packages/tokens/src/tokens.ts` — locked color tokens

---

## 10. Verification commands cheat-sheet

```powershell
# Full check before any commit
cd apps/web; corepack pnpm exec vitest run                    # 19 should pass
cd apps/web; corepack pnpm exec playwright test               # 1 should pass (smoke)
node_modules/.bin/tsc -p apps/web --noEmit                    # exit 0
cd packages/contracts; node_modules/.bin/tsc --noEmit         # exit 0 (contracts compile)
cd packages/contracts; node_modules/.bin/tsx scripts/validate.ts  # example accepted, malformed rejected

# Run dev server
cd apps/web; corepack pnpm dev    # http://localhost:3000
```

Engine + API tests (Python) — only relevant if you touch backend:
```powershell
cd services/engine; $env:PYTHONPATH="src"; ../../.venv/Scripts/python.exe -m pytest -q   # 199 should pass
cd services/api; $env:PYTHONPATH="src;../engine/src"; ../../.venv/Scripts/python.exe -m pytest -q  # 84 should pass
```

---

End of handoff. Good luck — this is a real product with a real honesty discipline. Don't break it for visual flair.
