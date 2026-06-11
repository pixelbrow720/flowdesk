# 09 — Roadmap

Mapped to current reality (see [`08-status-and-gaps.md`](08-status-and-gaps.md)).
The original phase-by-phase build playbook is preserved at
[`reference/Build-Playbook-PerFase.md`](reference/Build-Playbook-PerFase.md).

## Done (the frame)

- ✅ Engine: Black-76, IV, VOL-based exposure, field grid, levels, optional HIRO.
- ✅ Snapshot contract (pydantic ↔ zod), golden fixture, contract validate step.
- ✅ API: worker, session state machine, REST, WebSocket, Discord OAuth + role gate,
  Redis + Timescale repos.
- ✅ FE primitives: WebGL heatmap, exposure profiles, levels, auth UI, session JSON.
- ✅ Historical feed adapter + cost-aware Databento ingest.

## Next (highest leverage first)

### A. Validation / backtest harness — do this first
The roadmap is currently inverted: this should have come before more features.
- Reconstruct EOD dealer position; reconcile against next-day **ΔOI** (`statistics`).
- Test whether GEX structure (flip, walls) relates to /ES price intraday across
  the 90-day window.
- Output a short, repeatable report. Decide *empirically* whether VOL-GEX is good
  enough or whether DDOI is worth building.
- **Heavy item — confirm scope with the human first.**

### B. Finish the frontend dashboard
- Integrated TRACE-style layout to match `1.png`.
- Intraday **HIRO line** render (the `hiro` field is already produced).
- Timeline scrubber polish; end-to-end live-WS wiring.

### C. Wire in the surface
- Put SVI / expected-move (`surface.py`) into the Snapshot as **optional** fields.
- Aggregate **VEX / CHEX** from the existing `black76` vanna/charm.

### D. Live feed
- Implement `LiveAdapter` (replace the stub) behind `FEED_MODE=live`.

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
