#!/usr/bin/env bash
# arm_live.sh — supervised live-feed arming launcher (operator procedure).
#
# WHY THIS EXISTS: the code reads os.environ directly; nothing auto-loads .env
# (python-dotenv is not a dependency). So `make dev-api` / `python -m api.worker`
# would boot historical even with FEED_MODE=live in .env. This script exports
# .env, hard-verifies the two-key arming gate is CLEANLY set, then runs the
# worker in the FOREGROUND (no auto-restart — a crash must NOT loop the
# definition seed; that pattern locked the account twice).
#
# USAGE (run from repo root, at ~09:28 ET, with an operator watching):
#   ./scripts/arm_live.sh
# ABORT at any time: Ctrl-C. To disarm afterwards, set LIVE_FEED_ARMED back to
# unset/0 in .env.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

ENV_FILE="$REPO/.env"
VENV_PY="$REPO/.venv/bin/python"

[[ -f "$ENV_FILE" ]] || { echo "FATAL: $ENV_FILE not found"; exit 1; }
[[ -x "$VENV_PY"  ]] || { echo "FATAL: venv python not found at $VENV_PY"; exit 1; }

# --- Load .env into the environment (strip comments/blank lines) ------------- #
set -a
# shellcheck disable=SC1090
source <(grep -vE '^\s*(#|$)' "$ENV_FILE")
set +a

# --- Hard preflight checks (refuse to boot on any ambiguity) ----------------- #
fail() { echo "PREFLIGHT FAIL: $*"; exit 1; }

[[ "${FEED_MODE:-}" == "live" ]]        || fail "FEED_MODE is '${FEED_MODE:-unset}', expected 'live'"
[[ "${LIVE_FEED_ARMED:-}" == "1" ]]     || fail "LIVE_FEED_ARMED is '${LIVE_FEED_ARMED:-unset}', expected exactly '1' (check for inline comments)"
[[ -n "${DATABENTO_API_KEY:-}" ]]       || fail "DATABENTO_API_KEY is empty (would fail silently on first tick)"
[[ -n "${TIMESCALE_DSN:-}" ]]           || fail "TIMESCALE_DSN unset (worker KeyErrors at boot)"
[[ -n "${REDIS_URL:-}" ]]               || fail "REDIS_URL unset (worker KeyErrors at boot)"

# Datastores reachable?
timeout 3 bash -c "cat < /dev/null > /dev/tcp/localhost/6379" 2>/dev/null || fail "Redis (6379) unreachable"
timeout 3 bash -c "cat < /dev/null > /dev/tcp/localhost/5432" 2>/dev/null || fail "Timescale (5432) unreachable"

# Current ET clock (informational): warn if pre-market.
"$VENV_PY" - <<'PY'
from datetime import datetime, timezone, timedelta
et = datetime.now(timezone.utc) - timedelta(hours=4)  # EDT
hm = (et.hour, et.minute)
print(f"[clock] ET {et:%Y-%m-%d %H:%M} (EDT)")
if hm < (9, 30):
    print("[clock] WARNING: pre-market. The definition seed may return 0 legs "
          "before 0DTE is listed. Prefer arming at ~09:28-09:30 ET.")
elif hm >= (16, 0):
    print("[clock] WARNING: after RTH close (16:00 ET). 0DTE has expired.")
PY

echo "=============================================================="
echo " PREFLIGHT OK. Quote schema = ${QUOTE_SCHEMA:-mbp-1}"
echo " About to boot the LIVE worker. First get_chain fires ONE"
echo " Historical definition-seed call (first real account contact)."
echo " Watch for: 'feed_mode=live live_armed=True' then"
echo "            'seeded N instrument definitions' with N > 0."
echo " Ctrl-C to abort. NO auto-restart is configured (by design)."
echo "=============================================================="
read -r -p "Type ARM to proceed: " confirm
[[ "$confirm" == "ARM" ]] || { echo "aborted."; exit 1; }

cd "$REPO/services/api"
exec env PYTHONPATH=src:../engine/src "$VENV_PY" -m api.worker
