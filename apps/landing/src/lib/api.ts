/**
 * API host resolution for the landing page.
 *
 * The landing site (port 4321) and the FlowDesk API (port 8000) are separate
 * origins, so the "Login with Discord" CTA cannot use a relative `/api/...`
 * link — that would resolve against the landing origin and 404.
 *
 * `NEXT_PUBLIC_API_BASE_URL` overrides the host (for staging/production);
 * the default is the local-dev API at http://localhost:8000, matching
 * `PUBLIC_BASE_URL` in the repo `.env`.
 */

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

/** Absolute URL of the Discord OAuth login entrypoint on the API. */
export const DISCORD_LOGIN_URL = `${API_BASE_URL}/api/auth/discord/login`;
