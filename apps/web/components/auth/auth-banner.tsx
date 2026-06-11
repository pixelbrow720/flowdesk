"use client";

import { AUTH_COPY, type AuthBannerKind } from "../../lib/auth-copy";
import { cn } from "../../lib/cn";

export interface AuthBannerProps {
  kind: AuthBannerKind;
  /** Optional ISO grace end (rendered as a hint). */
  graceUntil?: string | null;
  className?: string;
}

function fmtEt(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return (
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      dateStyle: "medium",
      timeStyle: "short",
    }).format(d) + " ET"
  );
}

/**
 * Thin banner shown above the full app for non-blocking states (PRD #6 §7):
 *  - grace: DESK access revoked but usable until end of day ET (#4).
 *  - discord_pending: Discord down during re-check; using cached status (#6).
 * Neither locks access.
 */
export function AuthBanner({ kind, graceUntil, className }: AuthBannerProps) {
  if (kind === null) return null;
  const copy = kind === "grace" ? AUTH_COPY.GRACE : AUTH_COPY.DISCORD_PENDING;
  const until = kind === "grace" ? fmtEt(graceUntil) : null;

  return (
    <div
      role="status"
      className={cn(
        "flex items-center gap-12 border-b px-16 py-8",
        kind === "grace"
          ? "border-crimson/30 bg-crimson/10"
          : "border-border bg-surface",
        className,
      )}
    >
      <span
        className={cn(
          "font-display text-caption font-medium",
          kind === "grace" ? "text-crimson" : "text-muted",
        )}
      >
        {copy.title}
      </span>
      <span className="font-display text-caption text-muted">{copy.body}</span>
      {until && (
        <span className="ml-auto font-mono text-caption tabular-nums text-muted">
          s/d {until}
        </span>
      )}
    </div>
  );
}
