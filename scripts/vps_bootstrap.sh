#!/usr/bin/env bash
# =============================================================================
# FlowDesk — one-shot VPS bootstrap (single-host Docker deploy, beta-safe).
# =============================================================================
# Run on a FRESH Ubuntu 22.04/24.04 VPS, from the repo root, as a sudo-capable
# user. Idempotent: safe to re-run. It installs Docker, locks down the firewall,
# and brings up the full backend behind a Caddy TLS proxy on HISTORICAL replay.
#
#   git clone <repo> flowdesk && cd flowdesk
#   cp .env.example .env          # then fill it in (see REQUIRED below)
#   bash scripts/vps_bootstrap.sh
#
# This script NEVER contains secrets. You must populate .env yourself first.
#
# REQUIRED in .env before running (the stack refuses to boot without these):
#   SESSION_SECRET           openssl rand -hex 32
#   DISCORD_CLIENT_ID        Discord OAuth app
#   DISCORD_CLIENT_SECRET    Discord OAuth app
#   DISCORD_GUILD_ID         Flowjob.id guild snowflake
#   DISCORD_DESK_ROLE_ID     DESK role snowflake
#   CORS_ORIGINS             https://flowjob.id (the site that embeds the terminal)
#   PUBLIC_BASE_URL          https://<FLOWDESK_API_DOMAIN>
#   COOKIE_INSECURE=0        MUST be 0 in production (cookies require HTTPS)
#   FLOWDESK_API_DOMAIN      e.g. api.flowdesk.flowjob.id  (A record -> this VPS IP)
#   FLOWDESK_TLS_EMAIL       email for Let's Encrypt expiry notices
#
# BEFORE you run: point an A record for FLOWDESK_API_DOMAIN at this VPS's public
# IP. Caddy needs the DNS resolving to issue the TLS cert on first boot.
#
# Live feed stays OFF (FEED_MODE=historical, LIVE_FEED_ARMED unset) — that is the
# only mode beta users see. Arming live is a separate operator procedure
# (docs/ops/deploy-runbook.md section 5).
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log()  { printf '\033[36m[bootstrap]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[bootstrap WARN]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[bootstrap FATAL]\033[0m %s\n' "$*" >&2; exit 1; }

# --- 0. Preconditions --------------------------------------------------------
[[ -f docker-compose.yml ]] || die "run from the repo root (docker-compose.yml not found)"
[[ -f .env ]] || die ".env not found. Run: cp .env.example .env  then fill it in (see header)."

# Fail fast if obvious placeholders are still in .env.
if grep -q 'change_me_to_a_long_random_string' .env; then
  die "SESSION_SECRET is still the placeholder. Set it: openssl rand -hex 32"
fi
for key in FLOWDESK_API_DOMAIN FLOWDESK_TLS_EMAIL; do
  grep -q "^${key}=" .env || die "$key missing from .env (needed for TLS). See header."
done

# --- 1. Docker + compose plugin ---------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker Engine + compose plugin via get.docker.com ..."
  curl -fsSL https://get.docker.com | sh
else
  log "Docker already installed: $(docker --version)"
fi

if ! docker compose version >/dev/null 2>&1; then
  die "docker compose v2 plugin not available. Install docker-compose-plugin and re-run."
fi

# Run the stack on boot.
sudo systemctl enable --now docker

# Let the current user run docker without sudo (takes effect on next login).
if ! id -nG "$USER" | grep -qw docker; then
  log "Adding $USER to the docker group (re-login required to take effect)."
  sudo usermod -aG docker "$USER" || warn "could not add $USER to docker group; continuing with sudo."
fi

# --- 2. Firewall (ufw) -------------------------------------------------------
# The API host port is bound to 127.0.0.1 in docker-compose.yml, so it is never
# publicly reachable. Only SSH + HTTP(S) for Caddy need to be open.
# NOTE: Docker publishes ports via its own iptables chain which can BYPASS ufw.
# Here the only published ports are Caddy's 80/443 (which we WANT public), and
# the api's 8000 is loopback-only, so this is safe. Do not publish other ports.
if command -v ufw >/dev/null 2>&1; then
  log "Configuring ufw (allow OpenSSH, 80, 443)..."
  sudo ufw allow OpenSSH      || true
  sudo ufw allow 80/tcp       || true
  sudo ufw allow 443/tcp      || true
  yes | sudo ufw enable       || true
  sudo ufw status verbose || true
else
  warn "ufw not installed — skipping firewall config. Lock down 22/80/443 via your provider's firewall."
fi

# --- 3. Build + launch the production stack ----------------------------------
DC=(docker compose -f docker-compose.yml -f infra/docker-compose.prod.yml)
if ! docker info >/dev/null 2>&1; then DC=(sudo "${DC[@]}"); fi

log "Building images + starting the stack (api + worker + redis + timescale + caddy)..."
"${DC[@]}" up -d --build

# --- 4. Verify ---------------------------------------------------------------
log "Waiting for the API healthcheck (up to ~90s)..."
ok=0
for i in $(seq 1 18); do
  # API is loopback-bound on the host; curl it locally.
  if curl -fsS --max-time 5 http://127.0.0.1:8000/healthz >/dev/null 2>&1; then ok=1; break; fi
  sleep 5
done

echo
"${DC[@]}" ps
echo
if [[ "$ok" == "1" ]]; then
  log "API /healthz is green on 127.0.0.1:8000."
  log "Checking the worker booted in historical mode..."
  "${DC[@]}" logs worker 2>&1 | grep -m1 'feed_mode=historical' \
    && log "Worker boot OK (feed_mode=historical)." \
    || warn "Did not see 'feed_mode=historical' in worker logs yet — check: ${DC[*]} logs worker"
  echo
  domain="$(grep '^FLOWDESK_API_DOMAIN=' .env | cut -d= -f2-)"
  log "DONE. Once DNS for ${domain} points here, Caddy will issue TLS automatically."
  log "Verify from your laptop:  curl https://${domain}/healthz"
  log "Then set NEXT_PUBLIC_API_BASE_URL=https://${domain} on the Vercel frontend."
else
  die "API did not pass /healthz in time. Inspect: ${DC[*]} logs api"
fi
