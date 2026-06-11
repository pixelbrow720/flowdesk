# 02 — The Locked Contract

These values are **frozen**. They define the product's identity and guarantee
reproducible numbers. **An AI agent must not change any of them without explicit
human approval.** If a task appears to require a change here, STOP and ask.

The original full text lives in [`reference/Stitching-Guide.md`](reference/Stitching-Guide.md)
§2 and the PRD; this is the working summary.

## Visual identity

- **Colors (OKLab-tuned):**
  - Turquoise (positive / call / dealer-long-gamma) `#40E0D0`
  - Crimson (negative / put / dealer-short-gamma) `#E0183C`
  - Base background `#000000`
- **Fonts:** Space Grotesk (display/UI) + JetBrains Mono (numbers/data).
  **Never Inter.**
- Tokens are enforced in code via `@flowdesk/tokens` (TS exports + Tailwind preset).

## Instruments

| Instrument | Multiplier `M` | Strike step |
|---|---|---|
| /ES (E-mini S&P 500 options) | $50 | 5 |
| /NQ (E-mini Nasdaq-100 options) | $20 | 10 |

No other instruments. 0DTE focus.

## Session & replay

- **RTH 09:30–16:00 ET**, 1-minute cadence.
- 90-day historical replay window.
- Day-count for 0DTE uses **real wall-clock** time to 16:00 ET
  (`t_expiry_from_clock`); the fixed `0.5/365` constant is used only in pinned tests.

## Math conventions

- **Black-76** on the future. Forward `F` from the future price.
- **Rate** `r = ln(1 + SOFR)` (continuous from `SOFR_RATE`).
- **IV** from mid price, **Newton → bisection** fallback, tolerance `1e-6`.
- **Dealer convention:** dealers are **long calls / short puts**.
  - `DEALER_SIGN_CALL = +1`, `DEALER_SIGN_PUT = -1` (hardcoded in `exposure.py`).
- **GEX basis = VOL** (cumulative volume since RTH open):
  `net_gex = (sign_c·γ_c·vol_c + sign_p·γ_p·vol_p) · M · F² · 0.01`.
- **Walls = gamma-dollar** (`gamma·OI` per side), static, Top-3.
- **Gamma flip / largest GEX / largest DEX** computed from the VOL-based profile.
- **HIRO** (optional): per-trade signed flow `Σ s·δ·q·M·F`, aggressor side from
  `trades.side` (B=+1, A=−1, N=0).

## Schema

- **`SCHEMA_VERSION = 1`.** Adding an **optional** field (precedent: `ohlc`,
  `hiro`) does **not** bump the version. Any breaking change does — and that's a
  human decision, not an agent one.
- Snapshot is mirrored in `schema.py` (pydantic) and `snapshot.ts` (zod); they
  must remain identical.

## Auth

- **Discord OAuth**, scopes `identify guilds.members.read`.
- Access requires membership of `DISCORD_GUILD_ID` **and** holding `DESK_ROLE_ID`.

## Environment — exactly 12 locked keys

```
DISCORD_CLIENT_ID
DISCORD_CLIENT_SECRET
DISCORD_GUILD_ID
DESK_ROLE_ID
SESSION_SECRET
CORS_ORIGINS
FEED_MODE
DATABENTO_API_KEY
DATA_DIR
TIMESCALE_DSN
REDIS_URL
SOFR_RATE
```

Do not add, rename, or remove ENV keys without approval. New configuration
should reuse these where possible.

## Validation philosophy

Validation is **STRUCTURAL**, not number-for-number. GLBX-based /ES exposure is
a different universe from an SPX-vendor's numbers; do not "fix" the engine to
match SpotGamma. Correctness = internal consistency + structural behaviour + the
T-01…T-10 acceptance gate (see [`10-acceptance-and-testing.md`](10-acceptance-and-testing.md)).
