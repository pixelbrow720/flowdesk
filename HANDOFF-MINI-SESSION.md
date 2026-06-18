# Handoff — Mini-Session: Bug-fix Fog + IV Smile Call/Put + UI Polish (2026-06-19)

> Companion to the main `HANDOFF.md` (FOG heatmap, 2026-06-17). Read BOTH
> before touching anything. This handoff covers the work done in a single
> shorter session (after the WebGL TRACE heatmap was committed) — three bug
> fixes in the existing Fog panel, an additive IV-smile call/put split that
> touches the locked Snapshot contract, and a major UI/layout rework that
> collapses Fog + Flux + Arc into ONE scrolling page with shared chrome.

## TL;DR — what's done

1. **Fog bug fixes (3)** — verified against real JSON data, root causes
   identified, all surface in `components/fog/levelsChart.ts`:
   - **Bug 1 (walls moving):** walls are STATIC at RTH open (locked contract);
     `resolveKeyLevels` now uses `firstNonNull` (frame 0) for all OI-based
     levels (`call_wall`, `put_wall`, `hedge_wall`, `abs_gamma`, `oi_gamma_flip`).
   - **Bug 2 (levels stale):** dynamic levels (`Zero γ`, `largest_gex`,
     `largest_dex`) now read the CURRENT playhead frame, not the most-recent
     non-null across the whole session (the old `latestNonNull` behaviour).
   - **Bug 3 (Zero γ at wrong strike):** Zero γ now = per-strike `net_gex`
     sign-change interpolation (where bars visibly flip color) → matches the
     user's mental model of "transition between + and − zones". The old
     cumulative-crossing `levels.gamma_flip` is no longer used by the FE.
2. **Additive IV smile call/put split** — engine already solved per-strike
   `call_iv` / `put_iv`; this session exposed them as a new optional Snapshot
   field `iv_smile` (gated by `with_iv_smile`, preseden `surface`). Touched:
   engine (`schema.py`, `snapshot.py`) ↔ zod mirror (`snapshot.ts`) ↔ worker
   ↔ generator ↔ golden fixture ↔ `_SNAPSHOT_KEYS` ↔ dashboard type ↔ FE
   helper `buildCallPutSmile` (shared scale) ↔ panel render (turquoise dots =
   call IV, crimson dots = put IV, dots are visually separable when
   call-vs-put divergence exists).
3. **Shared chrome + one-page layout** — `components/terminal/chrome.tsx`
   (FeedBadge, SegToggle, Toggle, ReplayControlBar, AwaitingDataOverlay,
   FlashIcon, new `DropdownChecklist`) + `components/terminal/TerminalShell.tsx`
   + `lib/useTerminalFeed.ts`. Fog is the first consumer. The standalone
   `/flux` page + `FluxChartPanel.tsx` are GONE; flux now lives as a LOWER
   PANE inside the price chart (lightweight-charts native panes, sumbu waktu
   sinkron otomatis — HIRO baseline turquoise/crimson, calls/puts/retail
   decomposition lines as a dropdown). Arc tab + route are GONE; replaced with
   a `#arc` section placeholder in the same scrolling page (`/fog#arc`,
   smooth-scroll, scroll-margin cleared for the fixed navbar).
4. **GEX ↔ DEX switch** for the left strike bars, moved to the left panel
   (was toolbar, crowded the top-right). Plus a SVI-derived IV-smile
   toggle. Both are local to `fog/page.tsx`.
5. **Taber rapi**: chip row on the chart collapsed into three dropdowns
   (Key Levels / Ratios / Flux) instead of ~12 chips. Pane separator
   darkened to `rgba(142,142,136,0.18)` (default `#2B2B43` reads almost
   white on black).

## What's in the working tree (NOT committed)

```
M  AGENTS.md                                                                 (no changes read by us)
M  README.md
M  apps/dashboard/src/app/fog/page.tsx                          (bug fixes + switch + layout)
M  apps/dashboard/src/components/fog/LevelsChartPanel.tsx      (HIRO pane + dropdowns + separator)
M  apps/dashboard/src/components/fog/levelsChart.ts             (bug fixes: perStrikeGammaFlip, firstNonNull)
M  apps/dashboard/src/components/fog/levelsChart.test.ts        (tests updated for new logic)
M  apps/dashboard/src/components/fog/panels.tsx                (call/put smile dots)
M  apps/dashboard/src/components/fog/strikeMath.ts             (buildCallPutSmile)
M  apps/dashboard/src/components/fog/strikeMath.test.ts        (3 new tests for call/put smile)
M  apps/dashboard/src/components/navbar.tsx                     (Fog/Arc scroll anchors)
M  apps/dashboard/src/lib/api.ts                                (iv_smile type)
M  apps/dashboard/src/lib/useLiveSnapshots.ts                  (added `enabled` param)
M  apps/dashboard/src/lib/useReplaySnapshots.ts                 (NEW)
M  apps/dashboard/src/lib/playback.ts                           (NEW)
M  apps/dashboard/src/lib/playback.test.ts                      (NEW, 8 tests)
M  apps/dashboard/src/components/terminal/chrome.tsx           (NEW — shared chrome)
M  apps/dashboard/src/components/terminal/TerminalShell.tsx    (NEW — page wrapper)
M  apps/dashboard/src/lib/useTerminalFeed.ts                    (NEW — shared feed hook)
M  apps/dashboard/src/components/flux/fluxSeries.ts            (NEW — pure helper)
M  apps/dashboard/src/components/flux/fluxSeries.test.ts       (NEW, 6 tests)
M  apps/dashboard/src/app/flux/page.tsx                         (now redirects to /fog)
M  apps/dashboard/src/app/arc/page.tsx                          (now redirects to /fog#arc)
M  apps/dashboard/public/data/ES_2026-06-09.json                (REGEN — now carries iv_smile)
M  apps/dashboard/public/data/NQ_2026-06-09.json                (REGEN — now carries iv_smile)
M  services/api/src/api/worker.py                              (pass with_iv_smile=True)
M  services/engine/scripts/gen_session_snapshots.py            (pass with_iv_smile=True)
M  services/engine/src/engine/schema.py                        (IvSmilePoint + iv_smile field)
M  services/engine/src/engine/snapshot.py                       (with_iv_smile param + payload)
M  services/engine/tests/test_snapshot.py                      (added iv_smile to _SNAPSHOT_KEYS)
M  services/engine/tests/golden/snapshot.golden.json            (REGEN — +iv_smile: null)
M  packages/contracts/src/snapshot.ts                          (mirror)
M  packages/contracts/examples/*                              (no change; nullish accepts absent)
```

**Still untracked from earlier sessions** (not touched here, still on disk):
`apps/dashboard/src/lib/` (new files are now tracked above), `infra/`,
`services/api/scripts/`, etc. — see `git status`.

## URL & how to verify locally

- `http://localhost:4325/fog` — main terminal (Fog strike ladder + price
  chart with embedded Flux pane below, time-synced). Switch GEX/DEX at the
  top of the left panel; toggle IV smile next to it; switch ES/NQ in the
  top-right toolbar; toggle LIVE/REPLAY next to it; in REPLAY the transport
  bar appears bottom-center. Scroll down for the Arc section.
- `http://localhost:4325/fog#arc` — scrolls to the Arc placeholder section.
- `http://localhost:4325/flux` and `/arc` → 307 redirect to `/fog`.

## Verify (run ALL, expect zero failures)

```bash
# engine (must use the .venv that has engine + api editable-installed)
cd services/engine
PYTHONPATH=src ../../.venv/Scripts/python.exe -m pytest -p no:warnings

# contracts (zod mirror)
cd ../../packages/contracts
node_modules/.bin/tsc --noEmit
node_modules/.bin/tsx scripts/validate.ts

# dashboard
cd ../apps/dashboard
npm run typecheck            # tsc --noEmit
node --test src/components/flux/fluxSeries.test.ts \
          src/components/fog/levelsChart.test.ts \
          src/lib/playback.test.ts \
          src/components/fog/strikeMath.test.ts
npm run build                # production build, must compile
```

After `npm run build`, you MUST restart the dev server (`taskkill` the
`next dev` PID + `rm -rf .next` + `npm run dev`) because the build rewrites
`.next` and breaks the dev server's CSS pipeline → "polos" (unstyled HTML).

## Decisions made this session (with user approval)

- **Replay is the verification mode for live-feed behaviour.** We don't have a
  live Databento feed; the historical session JSON files are the only way to
  exercise the dashboard end-to-end. Replay exposes the actual data flow
  without touching the locked live-feed rail (`docs/architecture/live-feed-
  threat-model.md`). The 10:50 ET / 14:50 UTC lompatan of +$656M in puts
  was investigated against the raw tape — it's a genuine 2,046-lot sell of
  ITM put P7475 (delta ≈ −0.88 → $670M ≈ observed $658M). NOT a bug.
- **Per-strike Zero γ (the bug-3 fix) replaces cumulative-crossing.** This is
  what visually matches the user's "transition between + and − zones"
  mental model. The engine still emits the cumulative-crossing value as
  `levels.gamma_flip`; the FE no longer surfaces it. If the engine team
  wants the cumulative one back, add a separate key in `resolveKeyLevels`.
- **IV smile call/put = additive, gated, shared scale.** Engine already
  computed per-strike `call_iv` / `put_iv`; we just exposed them. Consumer
  must be on the same scale to see call-vs-put divergence — that's what
  `buildCallPutSmile` enforces (test: `buildCallPutSmile: call+put share ONE
  scale (divergence preserved)`). Deep-ITM IV noise (~2.33 on a 7200
  strike when forward is 7370+) can stretch the scale; no clamping yet
  because that's a cosmetic decision and the user wanted to see the raw
  shape first.
- **NO NQ spike guarding.** The 27 single-minute jumps >150pt in NQ come from
  the forward falling back to put-call parity when futures quotes go
  sparse (NQ solvable minutes are ~103–171 vs ES ~360–379). Per user
  direction: "NQ biarkan saja as is" — that's an honest reflection of the
  data, smoothing would lie. Documented in `docs/research/empirical/` style
  reasoning, but no code guard.

## Outstanding (NOT this session, NOT a blocker, low priority)

- **`Arc` is a placeholder.** The `#arc` section only says "3D vol surface
  σ(K, session-time) — coming next". The user's intended approach is pure-
  math Canvas2D axonometric + drag-orbit (no three.js dep), reusing the
  `surface` field already in the snapshot (`svi_a/b/rho/m/sigma` per minute).
  Same data family as the call/put smile, just visualised differently.
- **Three backend metrics asked about, NONE built yet** (per user direction
  "stop, dokumentasikan" before Arc was picked):
  1. **Theta decay** — engine has `black76.theta()` already; just needs to
     be aggregated and exposed (same pattern as the `iv_smile` work).
     High value for 0DTE (theta cliff into 16:00 ET).
  2. **Max pain** — strike that minimises total option payoff (Σ OI·intrinsic).
     Pure OI computation, no new data needed. Methodologically controversial
     (user was warned).
  3. **Volatility expansion** — needs a definition first. Likely: change in
     `surface.atm_vol` vs realised, or expansion of `surface.expected_move`
     over time. Needs design before build.
  All three should be done as ONE contract-bump + ONE regen (don't repeat
  the per-feature regen cost). Recommend batching AFTER Arc.
- **`volatility_trigger` → `oi_gamma_flip` rename** — already DONE in
  earlier session (commit `e022fd7`), `schema_version` stayed 1. Worth
  noting because the rename audit predates this handoff.
- **HIRO / FLUX validation gap.** Project-level: still `NOT-VALIDATED` per
  `docs/08-status-and-gaps.md` (n=4 days, predictor null). The Flux pane is
  context/confirmation, not a predictor; do not promote to primary signal.
  This was the reason the auto-callout / divergence narrative layer was
  deferred to after Arc.
- **FE workaround for IV smile deep-ITM outlier.** One call_iv at 2.33
  (233%) on a deep-ITM strike currently dominates the shared scale. If
  the user finds the smile unreadable in the browser, the fix is a
  percentile-clamp on `buildCallPutSmile` (e.g. clamp lo/hi to 5th/95th
  percentile of non-null IVs) — pure FE, no contract change.

## Files added this session (all NEW)

```
apps/dashboard/src/lib/playback.ts                      (pure: speedToIntervalMs, clampPlayhead, advancePlayhead, stepPlayhead, playStartIndex)
apps/dashboard/src/lib/playback.test.ts                 (8 tests)
apps/dashboard/src/lib/useReplaySnapshots.ts            (React hook: load JSON, playhead, play/pause, speed, step, seek)
apps/dashboard/src/lib/useTerminalFeed.ts               (React hook: mode+instrument+live/replay, frames, status, latest, awaitingData, replay)
apps/dashboard/src/components/terminal/chrome.tsx       (FeedBadge, SegToggle, Toggle, ReplayControlBar, AwaitingDataOverlay, FlashIcon, DropdownChecklist, etClock)
apps/dashboard/src/components/terminal/TerminalShell.tsx (page wrapper: toolbar + header slot + children + transport + awaiting overlay + flash)
apps/dashboard/src/components/flux/fluxSeries.ts        (pure: buildFluxSeries, buildFluxMetrics, buildFluxModel)
apps/dashboard/src/components/flux/fluxSeries.test.ts   (6 tests)
```

## Files removed this session (still tracked or untracked? — check git)

- `apps/dashboard/src/components/flux/FluxChartPanel.tsx` — deleted (the
  standalone Flux chart is replaced by the lower pane in LevelsChartPanel).
  Verify with `ls apps/dashboard/src/components/flux/`.

## Convention reminders (don't violate)

- **Locked colors stay locked**: turquoise `#0FB5A8`, crimson `#B5002E`,
  fonts Space Grotesk + JetBrains Mono. Source of truth
  `docs/02-locked-contract.md`.
- **Two mirrors stay byte-for-byte equal**: `services/engine/src/engine/
  schema.py` (pydantic) and `packages/contracts/src/snapshot.ts` (zod).
  Each additive field requires touching both in the same commit + regen
  golden fixture.
- **Engine `build_snapshot` stays pure + deterministic + calendar-free**.
  The replay-mode verification path is the unit-test stand-in for "is
  build_snapshot deterministic for the same input?" — both worker and
  generator must produce byte-equal snapshots for the same tape.
- **Don't trust unverified evaluations.** The proprietary / synthetic-OI
  / DDOI / VT family is NOT-VALIDATED (project-level gap). Don't surface
  them as primary signals; always label EXPERIMENTAL.
- **No edit to `apps/web/` or `packages/tokens/`.** Both deleted 2026-06-15
  per user decision (see `PROGRESS.md` 2026-06-15 entry). The new
  `apps/dashboard/` is the only frontend target.

## Pointer to the bigger picture

- Project-wide truth: `docs/08-status-and-gaps.md` (gaps, validation
  status, methodology decisions locked in 2026-06-12).
- Architectural map: `docs/01-architecture.md`.
- Engine map: `docs/04-engine.md`.
- Build playbook per phase: `docs/reference/Build-Playbook-PerFase.md`.
- Long-running PROGRESS log: `docs/PROGRESS.md` (see the new checkpoint
  appended this session).
- Main HANDOFF (predecessor, FOG heatmap): `HANDOFF.md`.
