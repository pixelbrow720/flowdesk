"use client";

import { useMemo } from "react";
import { useDashboardStore } from "../../lib/store";

/**
 * ET clock for the topbar. Derives from `snapshot.ts` (the snapshot's UTC
 * timestamp) formatted to America/New_York, so it is deterministic and tied to
 * the data frame (PRD #4.3: clock <- ts). Shows HH:MM:SS ET.
 */
export function EtClock({ className }: { className?: string }) {
  const ts = useDashboardStore((s) => s.snapshot.ts);

  const text = useMemo(() => {
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return "--:--:-- ET";
    const fmt = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
    return `${fmt.format(d)} ET`;
  }, [ts]);

  return (
    <span
      className={`font-mono text-[11px] tabular-nums text-muted ${className ?? ""}`}
      aria-label="Session time (Eastern)"
    >
      {text}
    </span>
  );
}
