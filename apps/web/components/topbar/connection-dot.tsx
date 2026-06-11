"use client";

import { useDashboardStore, type ConnectionState } from "../../lib/store";
import { cn } from "../../lib/cn";

const CONFIG: Record<
  ConnectionState,
  { label: string; dot: string; text: string; pulse: boolean }
> = {
  LIVE: { label: "LIVE", dot: "bg-turquoise", text: "text-turquoise", pulse: true },
  STALE: { label: "STALE", dot: "bg-crimson", text: "text-crimson", pulse: false },
  REPLAY: { label: "REPLAY", dot: "bg-fg", text: "text-fg", pulse: false },
  CONNECTING: { label: "CONNECTING", dot: "bg-muted", text: "text-muted", pulse: true },
  OFFLINE: { label: "OFFLINE", dot: "bg-muted", text: "text-muted", pulse: false },
};

/**
 * Connection-state indicator for the topbar: a small status dot + label driven
 * by the store. LIVE pulses turquoise; STALE is crimson; REPLAY is neutral.
 */
export function ConnectionDot({ className }: { className?: string }) {
  const state = useDashboardStore((s) => s.connectionState);
  const c = CONFIG[state];
  return (
    <span className={cn("inline-flex items-center gap-8", className)}>
      <span className="relative inline-flex h-8 w-8">
        {c.pulse && (
          <span
            className={cn(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-60",
              c.dot,
            )}
          />
        )}
        <span className={cn("relative inline-flex h-8 w-8 rounded-full", c.dot)} />
      </span>
      <span
        className={cn(
          "font-mono text-[11px] uppercase tracking-[0.08em] tabular-nums",
          c.text,
        )}
      >
        {c.label}
      </span>
    </span>
  );
}
