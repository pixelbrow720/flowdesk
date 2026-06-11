# STITCH_NOTES — FlowDesk monorepo stitching pass

Record of the stitching/verification pass per `STITCHING_GUIDE.md` §0 ("catat di
STITCH_NOTES"). Scope (agreed with owner): **backend only** — engine + api +
contracts + tokens — verify everything runs, fix conflicts, deep review. Frontend
Fase 4/5/6 explicitly deferred.

Date: 2026-06-11. Toolchain: Node v24.13.1, pnpm 9.7.0 (via corepack), Python
3.11.15 (venv at `.venv/`).

---

## 1. Final verification status (all green)

| Component | Check | Result |
| --- | --- | --- |
| engine | `pytest` | **92 passed** |
| engine | `ruff check .` | **clean** |
| engine | `python tests/gen_golden.py` parity | golden round-trips |
| api | `pytest` | **75 passed** |
| api | `python -m compileall src db` | OK |
| api | smoke (`/api/health`, `/api/me`, `/api/snapshot`) | 200 / 200 ANON / 401 |
| contracts | `tsc --noEmit` | clean |
| contracts | `validate` (zod) | example ACCEPTED, malformed REJECTED |
| engine | `scripts/validate.py` (pydantic) | byte-identical reject reason vs zod |
| tokens | `tsc --noEmit` | clean |
| web | `tsc --noEmit` + `next lint` | clean |

Cross-language contract parity confirmed: both zod (TS) and pydantic (Python)
reject the same malformed fixture with the identical reason
(`field.delta length (4) must equal field.gamma length (5)`).

---

## 2. Changes made (conflict resolutions)

Per guide §0/§2 "menangkan rilis lebih baru". No LOCKED CONTRACT value was
touched. Production engine/api logic was **not** modified except the two trivial
lint fixes noted below.

1. **Version pin conflict — `services/api/pyproject.toml`**
   `flowdesk-engine==0.1.0` -> `flowdesk-engine>=0.1`. The engine is now `0.9.0`;
   the hard `==0.1.0` pin made the editable workspace install unsatisfiable. Not
   a locked value. (engine `__init__` carries no `__version__`; the package
   version lives in `pyproject.toml` = `0.9.0`.)

2. **Stale auth test fixtures — `services/api/tests/test_rest.py`, `test_ws.py`**
   These were release-1.2 tests using a plain-JSON session cookie and expecting
   `/api/me` = 401. Releases 1.5 (signed cookie) and 1.6 (public `/api/me`)
   superseded that. 18 tests failed against current production code; production
   was proven correct (signed cookie -> DESK 200 / NO_DESK 403 / ANON 401,
   `/api/me` anon 200). Modernized the **fixtures only** to the signed-cookie
   scheme + public-`/api/me` contract. Full rationale + current auth contract in
   `services/api/tests/AUTH_TEST_NOTES.md`.

3. **Over-strict assertion — `services/api/tests/test_auth.py`**
   `assert "SameSite=Lax"` -> case-insensitive check. Starlette emits
   `SameSite=lax`; RFC 6265bis says the value is case-insensitive, and the
   sibling core test already asserts `samesite == "lax"`.

4. **Lint — `services/engine/scripts/ingest_databento.py`** (optional ingest
   script, not core engine): removed a dead `field` import; kept the
   availability-guard `import pandas as pd` with `# noqa: F401`.

5. **Type-guard unused-locals — `packages/contracts/src/snapshot.ts`**
   The 6 `_*Matches` compile-time drift guards tripped `noUnusedLocals`.
   Consolidated into one exported `SchemaContractInvariants` tuple — every zod
   vs interface equality check is preserved (drift still breaks the build) and
   it is now a "used" reference.

---

## 3. LOCKED CONTRACT audit (§2) — all conform

- Multiplier: `MULTIPLIER = {"ES": 50.0, "NQ": 20.0}` (engine/snapshot.py).
- Strike step: `STRIKE_STEP = {"ES": 5.0, "NQ": 10.0}` (api/worker.py).
- GEX formula: `gamma * VOL * M * F^2 * 0.01` (engine/exposure.py), dealer
  long-call/short-put sign convention present.
- IV solver tolerance: `PRICE_TOL = 1e-6`, Newton -> bisection (engine/iv.py).
- `SCHEMA_VERSION = 1`, `schema_version: Literal[1]` (engine/schema.py).
- Colors: `TURQUOISE = "#40E0D0"`, `CRIMSON = "#E0183C"` (tokens).
- Fonts: Space Grotesk (UI) + JetBrains Mono (numbers); "Inter" appears only in
  "never Inter" comments.
- ENV: exactly the **12** locked keys in `.env.example`. Code reads 4 extra,
  all documented optional dev toggles with defaults: `COOKIE_INSECURE`,
  `DISCORD_JOIN_URL` (default flowjob.id), `PUBLIC_BASE_URL`, `WS_HEARTBEAT_S`
  (default 15s). No mandatory 13th key.

---

## 4. Open findings (no code change — owner decision)

These are pre-existing in released code; left untouched to avoid unrequested
large refactors of locked/released modules. None block the test suites.

- **engine mypy**: `make typecheck`'s bare `mypy` fails (engine `pyproject.toml`
  declares no target package/`mypy_path`, unlike the api config). Running
  `MYPYPATH=src mypy -p engine` surfaces ~19 `strict` errors inside released,
  golden-tested modules (`exposure.py`, `field.py`, `levels.py`, `snapshot.py`)
  — mostly `dict`/`Sequence` missing type params and `float | None` passed where
  `float` is expected. The engine README treats mypy as optional/per-file.
  *Recommendation:* if strict engine typing is desired, scope it as its own task
  (touches released math; re-verify golden after).

- **api ruff/mypy**: `ruff check` reports ~158 findings across 21 files and
  `mypy` reports several, all pre-existing in released code. Dominant categories:
  `UP007` (`Optional[X]` -> `X | None`), `UP017` (`datetime.UTC`), `N818`
  (exception names without `Error` suffix — renaming risks cross-module import
  breakage), and `B008` (which is a **false positive** for the FastAPI
  `Query()`/`Depends()` default idiom). The api package has never passed its own
  `make lint`/`make typecheck`. *Recommendation:* a dedicated lint-modernization
  task, or relax the ruff rule selection in `pyproject.toml` to match the code's
  actual (pre-`UP`) style. Functional contract tests all pass.

- **Not a git repo**: no `.git` present, so guide §6 git steps are N/A. Consider
  `git init` if you want history/CI.

---

## 5. Manual actions for the owner

1. **`.env`**: copy `.env.example` -> `.env` and fill the 12 keys (Discord app
   credentials, `SESSION_SECRET`, `DATABENTO_API_KEY`, datastore DSNs, SOFR).
   Required to run the worker/API against real Redis + TimescaleDB + Discord.
2. **`pnpm` on PATH**: `corepack enable` failed with EPERM (needs admin to write
   shims into `C:\Program Files\nodejs`). I used `corepack pnpm@9.7.0 ...`
   directly. Either run `corepack enable` from an elevated shell once, or keep
   using the `corepack pnpm@9.7.0` prefix.
3. **Node version**: pnpm warns engines want Node `>=20 <21`; this machine runs
   v24. Everything passed, but for parity with the locked engine field consider
   Node 20 LTS (`.nvmrc` is present).
4. **Infra (Fase 6, deferred)**: `infra/` holds only `.gitkeep` — no
   `docker-compose.yml` yet (worker/api/timescale/redis). Needed to run the full
   stack locally end-to-end.
5. **Live datastores**: engine + api tests use fakes (fakeredis, injected
   repo/state). Running the real worker needs a reachable Redis + TimescaleDB.
