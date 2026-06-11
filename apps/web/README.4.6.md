# FlowDesk — Fase 4.6: Scrubber + replay controls

The bottom scrubber bar (56px, PRD #10 / #4): a session timeline with a position
marker + ET time readout, transport controls (play/pause, ±1 minute step,
1x/2x/4x speed), a session/date selector, a REPLAY badge, and a "Kembali ke
LIVE" button. LIVE tracks the newest minute; REPLAY plays stored frames. Uses
mock sessions + frames offline — no backend.

## Prerequisites & run

- Node `>=20 <21` (machine Node 24), pnpm `9.7.0` via corepack. No new deps.

```bash
corepack pnpm@9.7.0 install
corepack pnpm@9.7.0 --filter @flowdesk/web dev      # http://localhost:3000
#   -> /preview/dashboard   pick a session date to enter REPLAY; play/step/scrub
```

## Manual verification checklist

- [x] `typecheck` — clean.  `lint` — clean.  `build` — `/preview/dashboard` prerenders.
- [x] **Scrubber height measured (Playwright) at exactly 56px.**
- [x] **Enter replay**: selecting a session date loads 390 RTH frames
      (`rangeMax = 389`), shows the REPLAY badge + "Kembali ke LIVE", and enables
      the transport buttons.
- [x] **Step ±1**: forward steps advance the frame index (0 → 2).
- [x] **Play at 4x**: ~1.2s of playback advances several frames (2 → 7) then
      can be paused.
- [x] **Back to LIVE**: returns to LIVE (badge gone, transport disabled, marker
      back at the live end).
- [x] Zero console errors (only `/favicon.ico` 404).

## Bug caught by browser verification

The first run threw a zod error: the replay mock set `snapshot.state = "REPLAY"`,
but the contract `SessionState` enum is `PREMARKET | LIVE | STALE | CLOSED |
HOLIDAY` — there is **no "REPLAY" state**. REPLAY is a frontend *mode*
(`store.mode` / `connectionState`), not a snapshot state; recorded frames are
past LIVE minutes, so their `state` is `"LIVE"`. Fixed in `replay-mock.ts`. This
is exactly why frames are validated via `parseSnapshot` and why the heatmap
build/render is exercised in a real browser.

## File list (added/changed)

```
apps/web/
  lib/replay-mock.ts                  # MOCK_SESSIONS + getReplayRange/getFullSession (validated frames)
  lib/store.ts                        # + mode, frames, frameIndex, replayDate, playing, speed + actions
  components/scrubber/
    scrubber.tsx                      # 56px bar: transport, speed, timeline, date select, badge, back-to-live
    index.ts                          # barrel
  app/preview/dashboard/page.tsx      # scrubber mounted at the bottom; manual connection switch removed
```

## How replay works

- `MOCK_SESSIONS[instrument]` lists available dates; `getFullSession` builds the
  390 RTH frames for a date by drifting the base mock field with a slow midday
  phase (deterministic — no `Math.random`, so SSR/client agree). Each frame is
  `parseSnapshot`-validated.
- Selecting a date (or scrubbing from LIVE) calls `enterReplay(date, frames)`,
  which sets `mode = "REPLAY"`, `connectionState = "REPLAY"`, and shows frame 0.
- The scrubber's `setInterval` advances one frame every `1000 / speed` ms while
  `playing`, stopping at the last frame.
- `exitToLive()` clears the frames and restores the live mock; switching
  instrument also returns to LIVE.
- Because `connectionState` now derives from the mode, the topbar dot shows
  REPLAY automatically and the manual dev switch was removed from the preview.

## Assumptions

- **Offline frames are synthesized** from the base mock (not engine-derived);
  they are contract-valid and evolve plausibly across the session. The real app
  will fetch `GET /api/replay/sessions` and `GET /api/replay` (4.7 wires HTTP).
- **Availability rules** (PRD #10: today available >1h after open, prior
  sessions, past dates) are represented by the mock session list; enforcing the
  exact time-window gating belongs with the live API integration.
- The native `<input type="range">` + `<select>` are styled with tokens (accent
  turquoise, surface/border) rather than fully custom widgets, to stay
  accessible and avoid reinventing keyboard behavior.
- No `TODO-FROM-OWNER` items for this task.
```
