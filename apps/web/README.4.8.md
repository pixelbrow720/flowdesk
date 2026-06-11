# FlowDesk — Fase 4.8: Settings slide-in panel

The Settings panel (PRD #5): slides in from the right, 360px, glass surface,
ESC/overlay to close, focus-trapped. Two sections — **Tampilan** (theme, profile
metric, heatmap basis, render, default instrument, timezone) and **Akun** (DESK
status, Discord linked, manage subscription → flowjob.id, last role-check,
re-check, logout). Display prefs persist to a single `flowdesk.prefs` key.

## Prerequisites & run

- Node `>=20 <21` (machine Node 24), pnpm `9.7.0` via corepack. No new deps.

```bash
corepack pnpm@9.7.0 install
corepack pnpm@9.7.0 --filter @flowdesk/web dev      # http://localhost:3000
#   -> /preview/dashboard   click the topbar gear to open Settings
```

## Manual verification checklist

- [x] `typecheck` / `lint` / `build` — clean; `/preview/dashboard` prerenders.
- [x] **Browser (Playwright)**:
  - panel is **360px** wide and slides on-screen from the right when the gear is clicked (off-screen when closed).
  - changing a pref (metric → NET DEX) persists to `flowdesk.prefs` (`profileMetric: "DEX"`).
  - **ESC closes** the panel.
  - **reload rehydrates** the pref (metric stays DEX after a full reload).
- [x] Zero console errors (only `/favicon.ico` 404).
- [x] Defaults (PRD #5): Dark / Net GEX / Gamma / smooth / ES / ET.

## File list (added/changed)

```
apps/web/
  lib/prefs.ts                          # flowdesk.prefs schema + safe read/write + DEFAULT_PREFS
  lib/use-prefs.ts                      # hydrate store+theme on mount; persist on change
  lib/me-mock.ts                        # MeResponse type + ANON/NO_DESK/DESK/grace fixtures
  components/theme-provider.tsx         # now persists theme INSIDE flowdesk.prefs
  app/layout.tsx                        # no-flash script reads flowdesk.prefs (was flowdesk.theme)
  components/settings/
    settings-panel.tsx                  # 360px right slide-in, ESC/overlay/focus-trap, Tampilan + Akun
    index.ts                            # barrel
  app/preview/dashboard/page.tsx        # gear -> open panel; usePrefs() mounted
```

## How persistence works

- **Single key** `flowdesk.prefs` (versioned). `readPrefs()` validates every
  field and falls back to defaults for anything missing/invalid (SSR-safe, never
  throws); `writePrefs()` is best-effort.
- **ThemeProvider** reads/writes only the `theme` field inside `flowdesk.prefs`
  (the old separate `flowdesk.theme` key is gone), and the layout's no-flash
  script reads the same key before first paint.
- **`usePrefs()`** (mounted once at the dashboard root) hydrates the store
  (instrument/metric/basis/smooth) + theme from prefs on mount, then persists on
  any change. A `hydrated` ref guards against clobbering during the initial
  hydrate.

## Account section (PRD #5)

Reads a `MeResponse` (the release-1.6 `/api/me` contract, mirrored in
`me-mock.ts`). Shows: DESK / DESK·GRACE / NO DESK / ANON status pill, the linked
Discord id (truncated), the last role-check time (ET), a "Kelola → flowjob.id"
link, a "Cek ulang role" button (`onRecheck` → POST /api/me/recheck), and
"Keluar" (`onLogout` → POST /api/auth/logout). In the preview these use the
DESK fixture; 4.9 wires the live `/api/me` + recheck/logout handlers.

## Assumptions

- **Timezone is ET-only in v1** (the session tz is locked); the field is shown
  read-only and kept in the schema for forward-compat.
- **No server presets in v1** (PRD #5): prefs are client-only localStorage.
- The panel renders persistently in the DOM (overlay + transform) and toggles
  `pointer-events` + `aria-hidden` when closed, so the slide animation works and
  the closed panel is inert and not focusable.
- `onRecheck` / `onLogout` are optional props (no-ops in the preview) so the
  panel is usable offline; 4.9 supplies the real handlers.
- No `TODO-FROM-OWNER` items for this task.
```
