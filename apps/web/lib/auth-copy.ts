/**
 * Auth UX copy + view derivation (PRD #6 §7, FE auth contract 1.6).
 *
 * Indonesian copy for the six access/error states, plus `deriveAuthView` which
 * turns a MeResponse into the concrete UI decision (which screen + which CTAs +
 * which banner). Code/identifiers are English; user-facing copy is Indonesian.
 */
import type { MeResponse } from "./me-mock";

/** Which top-level experience to render. */
export type AuthView = "ANON" | "NO_DESK" | "DESK";

/** A banner shown above the app for grace / discord-down states. */
export type AuthBannerKind = "grace" | "discord_pending" | null;

export interface AuthCopy {
  title: string;
  body: string;
}

/** The six PRD #6 §7 states, keyed for lookup. */
export const AUTH_COPY = {
  /** #1 not logged in */
  ANON: {
    title: "Masuk dulu untuk mengakses FlowDesk.",
    body: "Verifikasi akses DESK lewat akun Discord kamu.",
  },
  /** #2 logged in, not a guild member */
  NOT_MEMBER: {
    title:
      "Kamu belum bergabung di server Discord FlowDesk.",
    body: "Gabung dulu untuk verifikasi akses DESK.",
  },
  /** #3 member, no DESK role */
  NO_DESK: {
    title: "Akun kamu belum punya akses DESK.",
    body: "Beli DESK di flowjob.id, atau cek ulang kalau kamu baru saja mendapatkannya.",
  },
  /** #4 revoked but in grace (banner) */
  GRACE: {
    title: "Akses DESK kamu dicabut.",
    body: "Kamu masih bisa pakai sampai akhir hari ini (waktu New York). Perpanjang di flowjob.id.",
  },
  /** #5 grace expired */
  GRACE_EXPIRED: {
    title: "Masa tenggang akses DESK kamu sudah berakhir.",
    body: "Perpanjang untuk lanjut.",
  },
  /** #6 discord down during recheck (banner) */
  DISCORD_PENDING: {
    title: "Verifikasi Discord tertunda.",
    body: "Kami pakai status terakhir kamu untuk sementara.",
  },
} as const satisfies Record<string, AuthCopy>;

export interface AuthDecision {
  view: AuthView;
  banner: AuthBannerKind;
  /** The card copy to show on the NO_DESK screen. */
  copy: AuthCopy;
  /** Whether the "Join Discord" CTA should be primary (not a guild member). */
  showJoin: boolean;
  /** Whether to offer the "cek ulang" button. */
  showRecheck: boolean;
}

/**
 * Derive the concrete UI decision from a MeResponse. Grace (DESK with
 * grace_until) renders the full app + a grace banner; NO_DESK splits into
 * not-member vs no-role copy via `is_member`.
 */
export function deriveAuthView(me: MeResponse): AuthDecision {
  if (me.access_state === "ANON") {
    return {
      view: "ANON",
      banner: null,
      copy: AUTH_COPY.ANON,
      showJoin: false,
      showRecheck: false,
    };
  }

  if (me.access_state === "DESK") {
    // Full app. If a grace window is open, show the grace banner.
    return {
      view: "DESK",
      banner: me.grace_until ? "grace" : null,
      copy: AUTH_COPY.GRACE,
      showJoin: false,
      showRecheck: false,
    };
  }

  // NO_DESK: not-member vs member-without-role.
  const notMember = !me.is_member;
  return {
    view: "NO_DESK",
    banner: null,
    copy: notMember ? AUTH_COPY.NOT_MEMBER : AUTH_COPY.NO_DESK,
    showJoin: notMember,
    showRecheck: me.cta.recheck_supported,
  };
}
