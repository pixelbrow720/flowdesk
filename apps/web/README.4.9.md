# FlowDesk — Fase 4.9: Auth UI (login, preview-blur, recheck)

The auth-aware UI states (PRD #6, FE auth contract 1.6), driven entirely from
`GET /api/me`:
- **ANON** → a "Masuk dengan Discord" login screen over a blurred dashboard preview.
- **NO_DESK** → the full dashboard rendered but BLURRED, with join/buy CTAs and a
  "Saya sudah punya DESK — cek ulang" button (loading + result toast). Not-member
  vs no-role copy is split via `is_member`.
- **DESK** → the full unblurred app (+ a grace banner when `grace_until` is set).

All six PRD #6 §7 states have Indonesian copy. Works offline from `/api/me` mock
fixtures.

## Prerequisites & run

- Node `>=20 <21` (machine Node 24), pnpm `9.7.0` via corepack. No new deps.

```bash
corepack pnpm@9.7.0 install
corepack pnpm@9.7.0 --filter @flowdesk/web dev      # http://localhost:3000
#   -> /preview/auth   switch ANON / NOT MEMBER / NO DESK / GRACE / DESK; try "cek ulang"
```

## Manual verification checklist

- [x] `typecheck` / `lint` / `build` — clean; `/preview/auth` prerenders.
- [x] **Browser (Playwright)** — all states render from fixtures:
  - ANON: preview blurred + "Masuk dengan Discord".
  - NOT MEMBER: blurred + "Join Discord" + copy "belum bergabung di server Discord".
  - NO DESK: blurred + "Beli DESK" + "cek ulang" + copy "belum punya akses DESK".
  - GRACE: full app (chart visible) + banner "Akses DESK kamu dicabut".
  - DESK: full app, **not blurred**.
  - **Recheck flow**: NO DESK → click "cek ulang" → resolves to DESK → blur
    clears, full app shown.
- [x] Zero console errors (only `/favicon.ico` 404).
- [x] Preview is genuinely **blurred (not hidden)** — the dashboard mounts
      underneath the BlurOverlay (`aria-hidden`, `pointer-events-none`).

## File list (added in this task)

```
apps/web/
  lib/use-me.ts             # holds MeResponse; recheck (injectable) + login/logout nav
  lib/auth-copy.ts          # 6-state Indonesian copy + deriveAuthView(me) decision
  components/auth/
    auth-gate.tsx           # route guard: ANON login / NO_DESK blur+CTA / DESK full
    auth-banner.tsx         # grace + discord-pending banners (non-blocking)
    toast.tsx               # recheck result toast (aria-live)
    index.ts                # barrel
  app/preview/auth/page.tsx # state switcher exercising every fixture + recheck
```

## How it works

- **`deriveAuthView(me)`** (`auth-copy.ts`) turns a `MeResponse` into the concrete
  decision: `view` (ANON/NO_DESK/DESK), `banner` (grace/discord_pending/none),
  the card `copy`, and whether to show Join / recheck. Grace = DESK + banner;
  NO_DESK splits not-member vs no-role on `is_member`.
- **`AuthGate`** renders the dashboard `children` once and layers the experience:
  DESK shows them directly (+ banner); ANON/NO_DESK render them blurred and inert
  underneath a `BlurOverlay` with the CTA card on top — so data components mount
  in one place and the preview is truly blurred, not a separate screenshot.
- **`useMe`** holds the entitlement and drives recheck: `recheck()` flips
  loading → success/error and swaps in the new `MeResponse`. `doRecheck` is
  injectable (preview resolves to DESK after 600ms); the real app passes a
  `fetch("/api/me/recheck", { method: "POST", credentials: "include" })`.
- **Login/logout** are browser navigations (`/api/auth/login`,
  `/api/auth/logout`) — not XHR — because of the Discord OAuth redirect.

## Assumptions

- **Offline-first**: the preview drives everything from `me-mock.ts` fixtures
  (1:1 with `services/api/mocks/me_*.json`). The real app shell will call
  `GET /api/me` (credentials: include) on mount + after login + after recheck and
  feed the result into `useMe`/`AuthGate`.
- **Six states**: states #1–#3 and #5 map to the ANON/NO_DESK screens with the
  exact PRD copy; #4 (grace) and #6 (discord-down) are non-blocking banners over
  the full app via `AuthBanner`.
- The data-endpoint 401/403 handling (mapping fetch errors to these screens) is
  wired when the app shell composes the live `/api/me` + WS (4.7) together; the
  gate already covers the UX from `access_state` + `is_member`.
- No `TODO-FROM-OWNER` items for this task.
```
