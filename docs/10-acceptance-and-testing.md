# 10 — Acceptance & Testing

## Acceptance gate (T-01 … T-10)

The release gate is a set of structural acceptance checks defined in the build
playbook and stitching guide ([`reference/Build-Playbook-PerFase.md`](reference/Build-Playbook-PerFase.md),
[`reference/Stitching-Guide.md`](reference/Stitching-Guide.md)). They verify the
system behaves correctly **structurally**, not that its numbers match any
external vendor.

The gate covers, end to end:

- **T-01..T-03 — Engine correctness & determinism:** Black-76/greeks vs.
  references; IV convergence (Newton→bisection, tol 1e-6); the golden Snapshot
  reproduces byte-for-byte.
- **T-04..T-05 — Contract integrity:** pydantic ↔ zod parity; the field invariant
  `len(price_grid)==len(gamma)==len(delta)`; `@flowdesk/contracts validate`
  accepts the example and rejects malformed input.
- **T-06..T-07 — Exposure & levels semantics:** dealer-sign convention
  (long call / short put) produces the expected GEX/DEX signs; walls / gamma flip
  / largest GEX-DEX extracted correctly from a known chain.
- **T-08 — Session/state:** PREMARKET→LIVE→CLOSED transitions; `stale` / `expired`
  flags set correctly.
- **T-09 — Auth/entitlement:** Discord OAuth + guild + `DESK_ROLE_ID` gate;
  unauthorized requests rejected.
- **T-10 — Transport:** REST latest/historical + WebSocket deliver validated
  Snapshots.

> Validation is **STRUCTURAL** (GLBX-/ES ≠ SpotGamma-SPX). Never "fix" the engine
> to match an external vendor's absolute numbers. See [`02-locked-contract.md`](02-locked-contract.md).

A regression in the T-gate is a hard blocker for any change.

## What the gate does NOT cover (intentionally, today)

- It does **not** prove the signal is *meaningful* (no ΔOI reconciliation, no
  price-predictivity test). That's the validation harness in
  [`08-status-and-gaps.md`](08-status-and-gaps.md) / [`09-roadmap.md`](09-roadmap.md), item A.

## Running everything

```bash
# Engine
cd services/engine && pytest && ruff check . && mypy

# API (install engine editable first)
cd services/api && pip install -e ../engine && pip install -e ".[dev]"
pytest && ruff check . && mypy

# TypeScript
pnpm install
pnpm -r typecheck && pnpm -r lint
pnpm --filter @flowdesk/contracts validate
pnpm --filter @flowdesk/web test
```

## Golden fixture

`services/engine/tests/golden/snapshot.golden.json` pins a full Snapshot.
Regenerate **only** after an intentional, reviewed change:

```bash
cd services/engine && PYTHONPATH=src python tests/gen_golden.py
```

An unexpected golden diff means you changed engine behaviour — investigate before
committing.

## Known baseline noise

Some `mypy`/`ruff` findings predate current work (engine strict-typing in locked
core modules; api stylistic lint incl. FastAPI `Depends` false positives). These
are documented in [`08-status-and-gaps.md`](08-status-and-gaps.md) §6 and are not
introduced by new changes. Don't blind-fix them mid-feature; scope separately and
re-run the gate.
