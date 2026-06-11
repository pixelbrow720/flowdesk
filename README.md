# FlowDesk — Task 0.8 (PRD step 1.3): Snapshot builder

Implements `services/engine/src/engine/snapshot.py` — `build_snapshot(...)` — which
assembles ONE canonical **Snapshot** (`schema_version` 1) for a given instrument
+ minute by orchestrating the whole compute pipeline:

```
raw chain quotes
    -> IV solve            (engine.iv.implied_vol / is_iv_reliable)
    -> greeks              (engine.black76.delta / gamma)
    -> per-strike exposure (engine.exposure.build_profile / net_gamma)
    -> heatmap field       (engine.field.build_field)
    -> key levels          (engine.levels.compute_levels)
    -> regime + session stamping
    -> validated Snapshot  (engine.schema.parse_snapshot)
```

> **Release note:** this is release **0.8** in the sequential `0.1 … 0.7 → 0.8`
> deliverable numbering. "1.3" is only the PRD's internal pipeline step ID for
> the snapshot builder — it is **not** the release number. The package version
> in `pyproject.toml` is `0.8.0`.

## Patch contents (file tree)

```
flowdesk-0.8-snapshot/
└── services/
    └── engine/
        ├── pyproject.toml                     # flowdesk-engine → 0.8.0 (+ tzdata pin)
        ├── src/
        │   └── engine/
        │       ├── __init__.py
        │       ├── snapshot.py                # NEW — build_snapshot orchestrator
        │       ├── schema.py                  # Snapshot contract (pydantic, from 0.2)
        │       ├── black76.py                 # from 0.4
        │       ├── iv.py                      # from 0.5
        │       ├── exposure.py                # from 0.6
        │       ├── field.py                   # from 0.7
        │       └── levels.py                  # from 0.7
        └── tests/
            ├── __init__.py
            ├── test_snapshot.py               # golden + invariants (PRD #12 §2)
            ├── gen_golden.py                  # regenerate the golden fixture
            └── golden/
                └── snapshot.golden.json       # frozen golden Snapshot
```

> This patch ships the **full** engine package (all sibling modules from 0.2–0.7
> are bundled) so the snapshot builder and its tests run standalone — no manual
> assembly across previous patch-sets required. Drop `services/engine/...` onto
> the monorepo, overwriting the older `pyproject.toml` (version bump) and the
> existing engine modules (byte-identical to their releases).

## Setup & run

```bash
cd services/engine
python -m venv .venv && source .venv/bin/activate   # Python >=3.11,<3.13
pip install -e ".[dev]"          # numpy, pydantic, tzdata (+ pytest, ruff, mypy) — all pinned

# Run the snapshot tests (golden + invariants)
pytest tests/test_snapshot.py -q

# Regenerate the golden fixture after an intentional contract change
PYTHONPATH=src python tests/gen_golden.py

# Lint / type-check (optional)
ruff check src/engine/snapshot.py
mypy src/engine/snapshot.py
```

`snapshot.py` imports only the standard library (`math`, `datetime`, `zoneinfo`)
plus the sibling `engine` modules and `engine.schema` (pydantic). `tzdata` is
pinned so `zoneinfo` resolves `America/New_York` even on minimal containers that
lack the system tz database.

## API

```python
from engine.snapshot import build_snapshot, ChainQuote

snap = build_snapshot(
    instrument="ES",                       # "ES" | "NQ"
    ts_utc="2026-06-10T13:31:00Z",         # ISO-8601 UTC (or datetime)
    chain=[ChainQuote(strike=5000.0, call_mid=..., put_mid=...,
                      call_vol=..., put_vol=..., call_oi=..., put_oi=...,
                      t_expiry=0.02)],       # year-fraction to 0DTE expiry
    forward=5000.0,                         # futures price F
    rate=math.log(1.0517),                  # r = ln(1 + SOFR)
    session_state="LIVE",                   # resolved PRD #9 state (engine owns no calendar)
    axis={"strike_min": 4980, "strike_max": 5020, "step": 5},
)                                           # -> engine.schema.Snapshot (validated)
```

Keyword-only extras: `t_expiry` (snapshot-level fallback), `smoothing_bw`,
`price_grid`, `top_n`, and explicit `stale` / `expired` overrides.

### What it computes

* **minute_index / session_date** — from `ts_utc` converted to America/New_York;
  `minute_index` = 0 at the 09:30 ET RTH open (floor of whole minutes).
* **stale / expired** — derived deterministically from `session_state` (PRD #9):
  `STALE → stale`, `CLOSED|HOLIDAY → expired`, `PREMARKET|LIVE → neither`;
  overridable via keyword args. The engine does **not** re-implement the
  calendar.
* **profile** — per-strike net GEX/DEX from VOL; thin strikes (unreliable quote
  or unsolvable IV) get greeks interpolated and `interpolated=true`.
* **regime** — `sign` = exact sign of aggregate net gamma; `stability_pct` =
  deterministic single-frame proxy in [0,100] (share of |net_gex| agreeing with
  the dominant sign).
* **field** — `build_field` projection (default grid = axis strike nodes).
* **levels** — walls from **OI** (static), gamma flip / largest GEX / largest
  DEX from **VOL** (dynamic).

The builder returns `parse_snapshot(payload)`, so the result is always validated
by the pydantic contract before it is returned.

## Manual verification checklist

- [x] `python -m py_compile src/engine/*.py tests/test_snapshot.py tests/gen_golden.py` → OK
- [x] **Validates under pydantic:** `parse_snapshot(snap.to_json())` round-trips.
- [x] **Passes the TS zod contract:** serialized object satisfies every
      `SnapshotSchema.strict()` constraint — strict key set, finite numbers,
      `ts` RFC-3339 `…Z`, ISO `session_date`, integer `minute_index`, enum
      `state`/`sign`, and `len(price_grid)==len(gamma)==len(delta)`.
- [x] **T-06 walls EXACT vs golden:** `call_walls=[5010,5015,5005]`,
      `put_walls=[4990,4985,4995]` (dictated by the fixture OI).
- [x] **Regime sign EXACT:** `-1`, matching the sign of `net_gamma` and of
      Σ `net_gex`.
- [x] **VOL levels within 1–2 strikes** (≤ 2·step) of the golden.
- [x] **Session stamping:** 09:31 ET → `minute_index=1`,
      `session_date=2026-06-10`, `ts=2026-06-10T13:31:00Z`; `CLOSED`→expired,
      `STALE`→stale.
- [x] **Thin strike:** missing-mid strike flagged `interpolated=true`; snapshot
      still validates.
- [x] **Field/profile invariants:** equal-length finite arrays, ascending strikes.
- [x] Inline harness (pytest not installed in sandbox): **10/10 tests PASS, EXIT=0**.

> `pytest` / `zod` are not installable offline in the authoring sandbox, so the
> tests were executed with an inline stdlib harness that imports and runs every
> `test_*` function, and the zod contract is mirrored field-by-field in Python
> with identical semantics. `tests/test_snapshot.py` is written for `pytest` and
> runs as-is wherever the pinned dev deps are installed.

## Assumptions

* **2D → 1D field collapse** follows the locked Snapshot contract (1D
  index-aligned arrays), consistent with release 0.7.
* **`t_expiry`** (year-fraction to the 0DTE expiry) is supplied per `ChainQuote`
  or via the snapshot-level `t_expiry=` keyword, keeping the engine calendar-free.
* **`stale` / `expired`** are mapped from `session_state` (PRD #9) since the
  engine does not own the calendar; explicit keyword overrides are available.
* **`stability_pct`** is a deterministic single-frame proxy; the full intraday,
  history-based stability lands in a later task.
* **Default field grid** = the axis strike nodes; an explicit `price_grid` and a
  Gaussian `smoothing_bw` are supported. Default `smoothing_bw = 0` (pure
  piecewise-linear across-strike interpolation).
* **Walls** use strikes strictly above (call) / below (put) the forward; the
  golden fixture's mids are produced by pricing Black-76 at a chosen IV smile so
  the IV solver round-trips and the whole snapshot is reproducible.
* **`tzdata`** is pinned for portable `zoneinfo` timezone resolution.
* No `TODO-FROM-OWNER` items for this task.
