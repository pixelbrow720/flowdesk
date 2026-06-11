/**
 * Mock of the GET /api/me entitlement contract (release 1.6) for offline FE
 * development. Mirrors services/api/src/api/models.py::MeResponse and the
 * recorded fixtures in services/api/mocks/.
 *
 * The 4.9 auth UI consumes the same shape; here the Settings "Akun" section
 * reads it to show DESK status, the Discord link, and the last role-check time.
 */
export type AccessState = "ANON" | "NO_DESK" | "DESK";

export interface MeCta {
  join_url: string;
  buy_url: string;
  recheck_supported: boolean;
}

export interface MeResponse {
  access_state: AccessState;
  discord_id: string | null;
  has_desk: boolean;
  is_member: boolean;
  last_checked: string | null;
  grace_until: string | null;
  cta: MeCta;
}

const CTA: MeCta = {
  join_url: "https://flowjob.id",
  buy_url: "https://flowjob.id",
  recheck_supported: true,
};

/** Recorded fixtures (1:1 with services/api/mocks/me_*.json). */
export const ME_FIXTURES: Record<"anon" | "no_desk" | "desk" | "grace", MeResponse> = {
  anon: {
    access_state: "ANON",
    discord_id: null,
    has_desk: false,
    is_member: false,
    last_checked: null,
    grace_until: null,
    cta: CTA,
  },
  no_desk: {
    access_state: "NO_DESK",
    discord_id: "123456789012345678",
    has_desk: false,
    is_member: true,
    last_checked: "2026-06-10T05:00:00Z",
    grace_until: null,
    cta: CTA,
  },
  desk: {
    access_state: "DESK",
    discord_id: "123456789012345678",
    has_desk: true,
    is_member: true,
    last_checked: "2026-06-10T05:00:00Z",
    grace_until: null,
    cta: CTA,
  },
  grace: {
    access_state: "DESK",
    discord_id: "123456789012345678",
    has_desk: false,
    is_member: true,
    last_checked: "2026-06-10T05:00:00Z",
    grace_until: "2026-06-11T04:00:00Z",
    cta: CTA,
  },
};

/** Default fixture used by the Settings preview (DESK). */
export const DEFAULT_ME: MeResponse = ME_FIXTURES.desk;
