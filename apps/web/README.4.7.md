# FlowDesk — Fase 4.7: WebSocket client + STALE handling

The realtime data layer (PRD #8 §7, #9). A `RealtimeClient` connects to
`/ws?instrument=…`, applies `{type:"snapshot"}` frames to the store, replies
`pong` to `{type:"ping"}`, auto-reconnects on transient drops with exponential
backoff (1/2/4/…/max 30s), and maps close codes 4401→re-login, 4403→no-DESK.
STALE frames hold the last good frame + surface an indicator. A dev toggle
switches between the live WS and an offline mock feed, so the FE runs with no
backend. The decision logic is a pure reducer, unit-tested with a fake socket.

## Prerequisites & run

- Node `>=20 <21` (machine Node 24), pnpm `9.7.0` via corepack. New dev dep: `vitest@2.0.5`.

```bash
corepack pnpm@9.7.0 install
corepack pnpm@9.7.0 --filter @flowdesk/web dev      # http://localhost:3000
#   -> /preview/dashboard   defaults to MOCK feed; toggle LIVE WS in the dev strip
corepack pnpm@9.7.0 --filter @flowdesk/web test     # vitest: reducer + client (fake socket)
```

## Manual verification checklist

- [x] `typecheck` / `lint` / `build` — clean; `/preview/dashboard` prerenders.
- [x] **Unit tests pass**: `vitest run` → **18 passed** (12 reducer + 6 client).
      Covers snapshot apply, STALE hold + recovery, ping→pong, close-code map
      (4401/4403/4400/1011/1000), backoff sequence, transient reconnect (new
      socket), denial = no reconnect, and `stop()` cancels reconnect.
- [x] **Browser (Playwright, mock feed)**: snapshots advance (ET clock
      09:31 → 09:33), the injected STALE frame shows the "holding last frame"
      indicator (`staleSeen`), and the next good frame clears it (`recovered`).
- [x] Zero console errors (only `/favicon.ico` 404).

## File list (added/changed)

```
apps/web/
  lib/ws/
    reducer.ts          # PURE: parseFrame, reduce (apply/stale-hold/close-map), backoffMs
    reducer.test.ts     # 12 tests
    client.ts           # RealtimeClient (injectable socketFactory + setTimer), wsUrl
    client.test.ts      # 6 tests (FakeSocket + manual timer)
    mock-feed.ts        # mockFeedFactory: timer-driven fake socket replaying fixtures
  lib/use-realtime.ts   # hook bridging client state -> store (LIVE mode only)
  lib/store.ts          # + stale, authError + setters; reset on instrument/replay change
  vitest.config.ts      # node env, lib/**/*.test.ts
  package.json          # + "test": "vitest run", vitest devDep
  app/preview/dashboard/page.tsx   # MOCK/LIVE source toggle + STALE/auth pills
```

## Architecture: pure reducer + imperative shell

- **`reducer.ts`** owns ALL decisions and is pure (no sockets, no timers): given
  the current state and an event (`open`/`frame`/`close`/`error`), it returns the
  next state + effects (`sendPong`, `reconnectInMs`). This is what the tests
  exercise directly.
- **`client.ts`** is the thin imperative shell: it owns the socket + reconnect
  timer and delegates every decision to the reducer. Both the socket and the
  timer are injectable, so the fake-socket tests drive open/message/close and a
  manual timer deterministically (no real time, no flakiness).
- **`mock-feed.ts`** implements the same `RealtimeSocket` surface as a real
  WebSocket, so the EXACT same client + reducer drive offline mode — only the
  socket source differs. It replays a session's frames on a timer, emits a
  periodic `ping`, and can inject a STALE frame.
- **`use-realtime.ts`** connects the client and bridges its reduced state into
  the store: applies `lastSnapshot`, sets `stale`, maps `status` →
  `connectionState` (open→LIVE/STALE, connecting/reconnecting→CONNECTING,
  denied→OFFLINE + `authError`). It runs only in LIVE mode; REPLAY owns the
  snapshot itself.

## STALE behavior (PRD #9)

A snapshot with `stale === true` (or `state === "STALE"`) does NOT replace the
rendered frame — the reducer keeps `lastSnapshot` pointing at the last good
frame and flips `stale = true`. The topbar dot shows STALE (crimson) and the
preview shows a "holding last frame" pill. The next frame with `stale === false`
replaces the frame and clears the flag. (If no good frame exists yet, the stale
frame is shown so the UI isn't blank.)

## Assumptions

- **Default source is MOCK** in the preview so it works offline; LIVE WS points
  at `ws://localhost:8000/ws` (override via `baseUrl`). The real app shell will
  choose `live` and derive the base from `NEXT_PUBLIC_API_BASE`.
- **Auth on the socket**: the browser `WebSocket` sends the session cookie
  automatically (same-origin / credentialed), matching the server's
  cookie-gated `/ws`. No token is passed in the URL (the `?token=` multiplex is
  backlog per the stitching guide).
- **Reconnect policy**: 4401/4403 are terminal (set `authError`, no reconnect);
  4400 bad-instrument and 1000 normal are terminal-but-not-auth (no reconnect);
  everything else (incl. 1011, 1006) reconnects with backoff. The host clears
  `authError` on a fresh `start()`.
- No `TODO-FROM-OWNER` items for this task.
```
