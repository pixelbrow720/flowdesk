# FlowDesk Snapshot Contract — `schema_version` 1

The **Snapshot** is the canonical per-`(instrument, minute)` object produced by the
compute engine, served by the API, and rendered by the frontend. It has two
byte-for-byte equivalent implementations that MUST stay 1:1:

| Language | File | Validator |
| --- | --- | --- |
| TypeScript | `packages/contracts/src/snapshot.ts` | `zod` → `parseSnapshot()` / `safeParseSnapshot()` |
| Python | `services/engine/src/engine/schema.py` | `pydantic` v2 → `parse_snapshot()` |

> **Versioning rule (MUST):** `schema_version` MUST be bumped on **any breaking
> change** — renaming a field, changing a type, changing units/semantics, or
> removing a field. Bump it in **both** files in the same change. Additive,
> backward-compatible fields MAY be introduced without a bump only if every
> consumer treats unknown fields as optional (current validators are strict, so
> in practice a bump is required).

Sources: **PRD #0** = Glossary & Global Contract; **PRD #8 §3** = canonical
Snapshot schema; **PRD #4** = regime; **PRD #9** = session state machine.

## Top-level fields

| Field | Type | Unit / domain | Meaning | PRD source |
| --- | --- | --- | --- | --- |
| `schema_version` | `1` (literal) | — | Schema version tag; MUST equal `1`. | PRD #8 §3 |
| `instrument` | `"ES" \| "NQ"` | enum | Tradable future (/ES M=$50/pt step 5; /NQ M=$20/pt step 10). | PRD #0 §4 |
| `session_date` | `string` | ISO date `YYYY-MM-DD` (America/New_York) | Trading session day. | PRD #9 |
| `ts` | `string` | ISO-8601 datetime, UTC (`…Z`) | Snapshot timestamp. | PRD #8 §3 |
| `minute_index` | `number` | integer, minutes | Minutes since RTH open; `0` = 09:30 ET. | PRD #8 §3 |
| `state` | `"PREMARKET" \| "LIVE" \| "STALE" \| "CLOSED" \| "HOLIDAY"` | enum | Session state machine value. | PRD #9 |
| `stale` | `boolean` | — | Feed gap 1–2 min; last frame held. | PRD #0 §2 |
| `expired` | `boolean` | — | 0DTE contracts for the session have expired. | PRD #9 |
| `forward` | `number` | index points | Forward `F` = futures price. | PRD #0 §3 |
| `rate` | `number` | continuous annual | Risk-free rate `r = ln(1 + SOFR)`. | PRD #0 §3–§4 |
| `axis` | `Axis` | object | Shared strike axis. | PRD #8 §3 |
| `regime` | `Regime` | object | Regime summary. | PRD #4 |
| `profile` | `ProfileRow[]` | array | Net GEX/DEX profile (ascending by strike). | PRD #8 §3 |
| `field` | `FieldGrid` | object | Heatmap field projection arrays. | PRD #8 §3 |
| `levels` | `Levels` | object | Key levels overlay. | PRD #0 §2 |
| `ohlc` | `OHLC \| null` | object (optional) | Underlying futures OHLC for this minute (candle view). Absent/`null` when not captured; additive, no version bump. | PRD #4 |
| `hiro` | `Hiro \| null` | object (optional) | Cumulative dealer hedging flow (HIRO). Absent/`null` when not captured; additive, no version bump (Divergence #5 → option A). | FlowGreeks |

## `axis` (Axis)

| Field | Type | Unit | Meaning | PRD source |
| --- | --- | --- | --- | --- |
| `strike_min` | `number` | index points | Lowest strike on the shared axis. | PRD #8 §3 |
| `strike_max` | `number` | index points | Highest strike on the shared axis. | PRD #8 §3 |
| `step` | `number` | index points (`> 0`) | Strike increment (/ES = 5, /NQ = 10). | PRD #0 §4 |

## `regime` (Regime)

| Field | Type | Unit | Meaning | PRD source |
| --- | --- | --- | --- | --- |
| `net_gamma` | `number` | USD per 1% move | Aggregate dealer net gamma exposure. | PRD #0 §5–§6 |
| `sign` | `-1 \| 0 \| 1` | enum | Sign of `net_gamma` (−1 crimson/volatile, +1 turquoise/pinning). | PRD #0 §6 |
| `stability_pct` | `number` | percent `[0, 100]` | Regime stability. | PRD #0 §2 |

## `profile[]` (ProfileRow)

| Field | Type | Unit | Meaning | PRD source |
| --- | --- | --- | --- | --- |
| `strike` | `number` | index points | Strike of this row. | PRD #8 §3 |
| `net_gex` | `number` | USD per 1% move | Net dealer Gamma Exposure: `gamma * VOL * M * F^2 * 0.01`. | PRD #0 §5 |
| `net_dex` | `number` | USD notional | Net dealer Delta Exposure. | PRD #0 §2 |
| `interpolated` | `boolean` | — | True if values are synthetic (interpolated), not observed. | PRD #8 §3 |

## `field` (FieldGrid)

| Field | Type | Unit | Meaning | PRD source |
| --- | --- | --- | --- | --- |
| `price_grid` | `number[]` | index points | Price grid defining the field's axis. | PRD #8 §3 |
| `gamma` | `number[]` | USD per 1% move | Gamma field value at each grid point. | PRD #0 §5 |
| `delta` | `number[]` | USD notional | Delta field value at each grid point. | PRD #8 §3 |

**Invariant (enforced by both validators):** `price_grid` defines the grid, so
`gamma.length === delta.length === price_grid.length`.

## `levels` (Levels)

| Field | Type | Unit | Meaning | PRD source |
| --- | --- | --- | --- | --- |
| `call_walls` | `number[]` | index points | Call walls by GAMMA-DOLLAR (`gamma * OI` per side), STATIC all day, ordered by rank (index 0 = rank 1). Divergence #2 → option B. | PRD #0 §2 |
| `put_walls` | `number[]` | index points | Put walls by GAMMA-DOLLAR (`gamma * OI` per side), STATIC all day, ordered by rank (index 0 = rank 1). Divergence #2 → option B. | PRD #0 §2 |
| `gamma_flip` | `number \| null` | index points | Gamma flip strike (net-gamma zero-crossing) by VOL, dynamic. | PRD #0 §2 |
| `largest_gex` | `number \| null` | index points | Strike of the largest GEX by VOL, dynamic. | PRD #0 §2 |
| `largest_dex` | `number \| null` | index points | Strike of the largest DEX by VOL, dynamic. | PRD #0 §2 |

## `ohlc` (OHLC, optional)

Underlying (futures forward) OHLC for this minute. Optional/additive: absent or
`null` for snapshots produced before OHLC capture was wired — does **not** bump
`schema_version`.

| Field | Type | Unit | Meaning | PRD source |
| --- | --- | --- | --- | --- |
| `o` | `number` | index points | Open: first futures trade price in the minute. | PRD #4 |
| `h` | `number` | index points | High: max futures trade price in the minute. | PRD #4 |
| `l` | `number` | index points | Low: min futures trade price in the minute. | PRD #4 |
| `c` | `number` | index points | Close: last futures trade price (== forward). | PRD #4 |

## `hiro` (Hiro, optional)

Cumulative dealer **delta-notional hedging flow** since the RTH open (HIRO,
`engine.hiro`). Optional/additive (Divergence #5 → option A): absent or `null`
when not captured — does **not** bump `schema_version`. Units are USD
delta-notional; positive = net dealer BUYING pressure (bullish), negative =
selling pressure. These are the *current* cumulative values for the minute; the
intraday HIRO line is reconstructed FE-side from the per-minute frame sequence
(like the forward-price line), so no per-trade path is embedded per frame.

| Field | Type | Unit | Meaning | PRD source |
| --- | --- | --- | --- | --- |
| `total` | `number` | USD delta-notional | Cumulative HIRO, all legs, since RTH open. | FlowGreeks |
| `calls` | `number` | USD delta-notional | Cumulative HIRO from call trades only. | FlowGreeks |
| `puts` | `number` | USD delta-notional | Cumulative HIRO from put trades only. | FlowGreeks |
| `zerodte` | `number` | USD delta-notional | Cumulative HIRO from 0DTE trades (`T < 1/365`). | FlowGreeks |
| `retail` | `number` | USD delta-notional | Cumulative HIRO from the heuristic retail proxy (odd-lot size; indicative only). | FlowGreeks |
