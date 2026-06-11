# Auth test fixtures — modernization notes

This note records why `tests/test_rest.py` and `tests/test_ws.py` were updated
during the monorepo stitching pass, and what the current auth contract is. It is
the canonical explanation for anyone diffing these files against the original
release-1.2 patch.

## TL;DR

The data-endpoint tests (`test_rest.py`, `test_ws.py`) were written for the
**release 1.2** auth seam, which used a **plain-JSON session cookie**. Releases
**1.5** (Discord OAuth2 + signed cookie) and **1.6** (public `/api/me`)
superseded that seam but the two older test files were never updated, so 18
tests failed against the current production code. The production code was
verified correct; only the **test fixtures** were modernized.

Per `STITCHING_GUIDE.md` §0 ("menangkan rilis lebih baru") and §9 (the
`/api/me` 401 -> 200 divergence is intentional and recorded), the newer release
wins.

## What changed in the fixtures

| Before (release 1.2) | After (release 1.5 / 1.6) |
| --- | --- |
| `json.dumps({"discord_id","has_desk"})` as the cookie | `serialize_session(Session(...), SECRET)` — the signed (HMAC) cookie |
| no `SESSION_SECRET` in env | `SESSION_SECRET` set in `make_client` / `make_app` so the app can verify the cookie |
| `test_me_401_without_session` (expects 401) | `test_me_200_anon_without_session` (expects 200 `access_state="ANON"`) |
| recheck test relied on cached cookie state | injects `FakeDiscordClient` with DESK roles keyed by access token, so the forced re-check is network-free and deterministic |
| `assert "SameSite=Lax" in set_cookie` | `assert "samesite=lax" in set_cookie.lower()` — SameSite is case-insensitive (RFC 6265bis); Starlette emits `lax` |

**No production module was modified.** The proof that production was already
correct: with a signed cookie, `DESK -> 200`, `NO_DESK -> 403`, `ANON -> 401`
on data endpoints, and `/api/me` anonymous -> 200 ANON.

## The current auth contract (what the tests now assert)

Source of truth: `api/security.py`, `api/auth_session.py`, `api/auth.py`,
`api/entitlement.py`, and `api/FE_AUTH_CONTRACT.md`.

- **Session cookie** (`flowdesk_session`): signed with `SESSION_SECRET` (HMAC),
  7-day expiry, `HttpOnly` + `Secure` (unless `COOKIE_INSECURE=1` for local dev)
  + `SameSite=Lax`. A missing, tampered, or expired cookie reads as anonymous.
- **Data endpoints** (`/api/snapshot`, `/api/snapshot/latest`, `/api/replay*`,
  `/ws`) are **DESK-gated** (PRD #6 §5, acceptance T-09):
  - no/invalid session -> **401** (`UNAUTHENTICATED`; WS close **4401**)
  - valid session, no DESK and no active grace -> **403** (`FORBIDDEN`; WS **4403**)
  - DESK or active revocation grace -> **200** (WS streams)
  - invalid instrument -> **422** (WS close **4400**)
- **`/api/me`** is **PUBLIC** (release 1.6, PRD #6 §7): anonymous -> **200** with
  `access_state="ANON"`, never 401. It projects the session into
  `ANON | NO_DESK | DESK` so the FE renders the denied/preview-blur experience
  without hitting a 401. `POST /api/me/recheck` still requires a session (401 if
  anonymous) and forces an immediate Discord re-check.
- The not-member vs no-desk distinction is exposed **only** via `/api/me`
  (`access_state` + `is_member`); data endpoints return a generic 403 (§9).

## Running

```bash
cd services/api
pip install -e ".[dev]"
pytest                     # full suite
pytest tests/test_rest.py -q
pytest tests/test_ws.py -q
```
