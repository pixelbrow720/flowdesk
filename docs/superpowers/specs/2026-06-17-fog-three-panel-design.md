# Fog — Three-Panel Strike Terminal (Design Spec)

> Date: 2026-06-17 · Status: DRAFT (awaiting user review)
> Replaces the TRACE-style WebGL heatmap as the primary Fog view.
> Locked-contract colors and data contract unchanged (additive only).

## 1. Why this exists

Every competitor (SpotGamma TRACE, ConvexValue, Menthor Q, GFlows, Tier1Alpha,
Volland, TradingView GEX scripts) renders dealer positioning with the SAME
visual baseline: a diverging red/green price×time heatmap, horizontal profile
bars, a gamma-flip line, and call/put wall markers. Our previous heatmap, once
finished, just looked like TRACE — nothing distinctive.

This redesign drops the heatmap as the primary view and replaces it with three
strike-aligned profile panels that share one Y axis (strike price). The
distinctive idea — not used by any competitor — is the **center panel**: a
per-strike GEX *range band* (session memory) + *current line* (now) + animated
*flow* (momentum: is each wall building or decaying?). The user prototyped the
band/line idea by hand; this spec formalizes it and adds the flow layer.

Decisions already locked by the user:
- Three panels, all sharing Y = strike. (chosen 2026-06-17)
- Roles separated, NOT metric-duplicated: left = static structure, center =
  dynamics, right = directional. Full time axis is dropped; time lives through
  the band (memory) and flow (momentum).
- Right panel = DEX bidirectional bars (same visual language as left).
- Heatmap retired from the page but `GexHeatmap.tsx` + `glHeatmap.ts` kept in
  the repo, not imported (recoverable).
- Aesthetic bar: must read as hand-crafted, not "AI-generated". The user's
  existing left panel (`StrikePanel`/`GexCell` in `page.tsx`) is the reference
  for type, spacing, and restraint.

## 2. Non-goals (YAGNI)

- No full price×time evolution view in this iteration (the dropped heatmap was
  the only one; we accept losing "watch the whole session replay"). May return
  later as an optional thin time-strip — explicitly out of scope now.
- No VEX/CHEX/proprietary/DDOI panels yet. They stay EXPERIMENTAL and unwired.
- No new engine fields, no Snapshot/`schema_version` change. Pure frontend,
  consuming fields the engine already emits.
- No live websocket wiring — still reads the static session JSON as today.

## 3. Data available (all already emitted; verified in ES_2026-06-09.json)

Per-frame Snapshot fields this design consumes:
- `forward` (float) — futures price, the current-price marker.
- `ts`, `minute_index` — used only to order frames + compute the session
  history for the band; no time axis is drawn.
- `profile[]`: `strike`, `net_gex`, `net_dex`, `interpolated`.
- `regime.net_gamma` — drives the regime label (existing).
- `levels.gamma_flip`, `levels.call_walls[]`, `levels.put_walls[]` — currently
  PARSED BUT UNUSED; this design surfaces them as strike markers.
- `surface.atm_vol`, `surface.expected_move`, `surface.skew`, `surface.svi_*`
  — EXPERIMENTAL but populated 389/390; used for the optional IV-smile overlay
  on the left panel. Must carry an EXPERIMENTAL marker.
- Per-strike momentum (`diff5m`, already derived in `page.tsx` from history) —
  drives flow speed/direction in the center panel.

Fields intentionally NOT used here: `exposure_ext`, `proprietary`, `flux.*`
beyond the existing P/C ratio, `ohlc` (null in data), `synthetic_oi*`, `ddoi`.

## 4. Layout

```
 ┌─ price ─┬─ LEFT: GEX structure ─┬─ CENTER: dynamics ──────┬─ RIGHT: DEX ─┐
 │  7,450  │        ▏              │   ░░▏·······→            │      ▕       │
 │  7,400  │  ▏███████ (wall)      │ ░░░░░██▏··········→→→     │   ▕████      │
 │ [7,390] │  ███▏     (amber=now) │ ◀··░░░██▏                │      ███▕    │
 │  7,345  │  ████▏    (put wall)  │ ◀◀◀····░░░▏              │     ████▕    │
 └─────────┴───────────────────────┴──────────────────────────┴──────────────┘
   shared    bars + IV-smile curve    range band + line + flow    DEX bars
   Y axis      (zero axis at left)      (zero axis at center)      (zero at right edge)
```

- One shared CSS grid; `gridAutoRows` fixed so every strike row aligns across
  all panels and the price gutter (reuse the existing `StrikePanel` row model).
- Hairline `rule` (#161618) separators between panels — no heavy borders, match
  current minimalism.
- Price gutter stays leftmost (existing color logic: amber = current, turquoise
  = major long, crimson = major short).
- Scroll: the whole strike stack scrolls together (one `fog-scroll` container)
  so rows never desync between panels.

### 4.1 Left panel — GEX structure (static)
- Bidirectional bars from a left-anchored zero axis, `net_gex` per strike.
- Deep turquoise (`turquoise.deep`) positive, deep crimson (`crimson.deep`)
  negative — unchanged tokens.
- REMOVE the grey range hairline from here (it moves to center; that was the
  redundancy). Left becomes a clean magnitude read.
- Wall markers: small inline tick/label where `strike ∈ levels.call_walls`
  (resistance) or `put_walls` (support); gamma_flip drawn as a faint full-width
  horizontal rule across the row it falls on.
- Optional IV-smile overlay: a thin bone curve tracing `surface` vol vs strike,
  toggled off by default, labelled EXPERIMENTAL. It is a background curve, not a
  competing bar, to avoid double-X clutter. (May be deferred to a follow-up
  plan if it crowds the panel — flagged as the riskiest sub-feature.)

### 4.2 Center panel — dynamics (the original idea)
This is the differentiator. Per strike, three layers stacked in one row:
1. **Range band** — a filled, semi-transparent lozenge from the strike's
   session MIN to session MAX `net_gex` (signed; may cross the zero axis). This
   is the user's blue↔red idea, corrected: the band edges use the existing
   `tide` tokens — `tide.blue` (#5BA3D0) marks session MAX, `tide.red`
   (#D9534F) marks session MIN (opposite ends of the SAME range), not "longest
   vs shortest". Using `tide.*` (not turquoise/crimson) keeps the memory band
   visually distinct from the sign-colored current value.
2. **Current line** — a bright bone (`bone.0` #FAFAF7) marker at the current
   `net_gex`, "swimming" inside its band. Position in band = percentile of now
   within today's range.
3. **Flow** — short particles/streaks along the bar axis encoding `diff5m`:
   - GEX rising (wall building) → flow OUTWARD from zero toward the bar tip.
   - GEX falling (wall decaying) → flow INWARD back toward zero.
   - density ∝ |net_gex| now; speed ∝ |diff5m|. Particle color follows the
     sign of the current value (turquoise positive / crimson negative).
- Zero axis vertical line at panel center (bidirectional).
- Honesty note: flow encodes rate-of-change, not magnitude. Magnitude stays
  encoded by the band/line; flow is the motion layer on top, never the only cue.

### 4.3 Right panel — DEX directional (static)
- Same bidirectional-bar language as the left panel, metric = `net_dex`.
- Zero axis anchored so it reads as a mirror of the left (visually balances the
  three-panel composition). Same turquoise/crimson sign palette.
- No flow, no band — a clean directional-pressure read, deliberately quieter
  than the center.

## 5. Rendering approach

- Left + right panels: DOM/CSS bars (reuse `GexCell` geometry). Cheap, crisp,
  matches the hand-built reference look. No canvas needed.
- Center flow layer: ONE WebGL/regl canvas (or a single Canvas2D particle layer
  if perf allows) overlaid on the center column, driven by per-strike
  `{value, min, max, diff5m}`. Reuse the regl setup pattern from `glHeatmap.ts`
  (kept in repo) rather than re-installing anything. Band + current line can be
  DOM; only the particles need the canvas.
- Animation: requestAnimationFrame loop on the center canvas only; left/right
  are static DOM. Pointer/crosshair stays cheap.
- Respect `prefers-reduced-motion`: when set, freeze flow to static arrows.

## 6. Components (new + changed)

- `page.tsx` (`/fog`): replace the heatmap column with the three-panel grid;
  drop the `GexHeatmap` import. Keep snapshot fetch + `strikes` memo (already
  computes `diff5m/30m/60m` and per-strike low/high — exactly what center needs).
- `StrikePanel` → split into `StrikeGutter` (prices), `GexStructurePanel`
  (left), `DynamicsPanel` (center, owns the flow canvas), `DexPanel` (right).
- New `components/fog/flowField.ts` — the regl particle layer for the center
  panel (the only new GPU code).
- `GexHeatmap.tsx` + `glHeatmap.ts`: untouched, just no longer imported.

## 7. Testing / verification

- `npm run typecheck` + `npm run build` must pass (the real gate; lint unusable).
- Determinism: band min/max and `diff5m` are pure functions of the frames; add a
  small unit test for the band-range + percentile helper (extract it pure).
- Visual: Playwright screenshot of `/fog` (static frame) + one with reduced
  motion, read back the PNGs to confirm alignment across the three panels and
  that flow renders.
- Manual: confirm rows stay aligned across panels while scrolling.

## 8. Open risks (called out honestly)

- IV-smile overlay may clutter the left panel; it is the first thing to cut if
  the panel feels busy. Default OFF.
- Flow legibility is unproven until seen moving; if it reads as noise, fall back
  to a static directional arrow per strike (same data, no animation).
- "Losing the time axis" is a real trade-off the user accepted; revisit only if
  they later miss session replay.
