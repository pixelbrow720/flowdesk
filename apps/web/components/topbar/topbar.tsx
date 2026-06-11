"use client";

import { useDashboardStore } from "../../lib/store";
import { SegmentedControl } from "../ui/segmented-control";
import { IconButton } from "../ui/icon-button";
import { ConnectionDot } from "./connection-dot";
import { EtClock } from "./et-clock";

export interface TopbarProps {
  /** Called when the settings gear is clicked (opens the 4.8 panel). */
  onOpenSettings?: () => void;
  className?: string;
}

/**
 * Thin 44px topbar (PRD #4.2): FlowDesk wordmark (left), the ES|NQ instrument
 * switch, and on the right the ET clock, connection state dot, and a settings
 * gear. Height is locked to 44px.
 */
export function Topbar({ onOpenSettings, className }: TopbarProps) {
  const instrument = useDashboardStore((s) => s.instrument);
  const setInstrument = useDashboardStore((s) => s.setInstrument);

  return (
    <header
      className={`flex h-[44px] shrink-0 items-center justify-between border-b border-border bg-surface px-12 ${className ?? ""}`}
    >
      <div className="flex items-center gap-16">
        <span className="font-display text-h2 font-semibold leading-none text-fg">
          Flow<span className="text-turquoise">Desk</span>
        </span>
        <SegmentedControl
          ariaLabel="Instrument"
          value={instrument}
          onChange={setInstrument}
          options={[
            { value: "ES", label: "ES" },
            { value: "NQ", label: "NQ" },
          ]}
        />
      </div>

      <div className="flex items-center gap-16">
        <EtClock />
        <ConnectionDot />
        <IconButton label="Settings" onClick={onOpenSettings}>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </IconButton>
      </div>
    </header>
  );
}
