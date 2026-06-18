"use client";

/**
 * Shared terminal chrome — the controls every lens (Fog / Flux / Arc) reuses so
 * they stay visually + behaviourally identical: the feed badge, the segmented
 * ES/NQ + LIVE/REPLAY toggles, a plain on/off toggle, the replay transport bar,
 * the awaiting-data overlay, and the corner flash glyph.
 *
 * These were lifted verbatim out of the Fog page so all three lenses share one
 * source of truth (locked color tokens, mono micro-type, hover → brick).
 */

import { useEffect, useRef, useState, type ReactNode } from "react";
import { SPEEDS, type Speed } from "@/lib/playback";
import type { FeedStatus } from "@/lib/useLiveSnapshots";

/* ------------------------------------------------------------------ */
/* DropdownChecklist — one button that opens a checklist popover       */
/* ------------------------------------------------------------------ */
/* Collapses a long row of toggle chips into a single labelled button  */
/* (`Label (n)`); the popover lists each item with a colored dot +     */
/* optional EXP tag. Closes on outside-click / Escape.                 */

export interface ChecklistItem {
  id: string;
  label: string;
  color: string;
  experimental?: boolean;
}

export function DropdownChecklist({
  label,
  items,
  active,
  onToggle,
  align = "left",
}: {
  label: string;
  items: ChecklistItem[];
  active: Set<string>;
  onToggle: (id: string) => void;
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const count = items.reduce((n, it) => (active.has(it.id) ? n + 1 : n), 0);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={`flex items-center gap-1.5 rounded-[3px] border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.12em] transition-colors duration-150 ${
          count > 0
            ? "border-bone-0/50 text-bone-0"
            : "border-rule text-bone-3 hover:border-brick-glow hover:text-brick-glow"
        }`}
      >
        {label}
        {count > 0 && <span className="text-bone-3">({count})</span>}
        <span aria-hidden className="text-bone-3">{open ? "▴" : "▾"}</span>
      </button>

      {open && (
        <div
          className={`absolute z-50 mt-1 max-h-[60vh] min-w-[180px] overflow-y-auto rounded-[4px] border border-rule bg-black/95 p-1 backdrop-blur-sm ${
            align === "right" ? "right-0" : "left-0"
          }`}
        >
          {items.map((it) => {
            const on = active.has(it.id);
            return (
              <button
                key={it.id}
                type="button"
                onClick={() => onToggle(it.id)}
                aria-pressed={on}
                className={`flex w-full items-center gap-2 rounded-[3px] px-2 py-1.5 text-left font-mono text-[10px] tracking-[0.08em] transition-colors duration-150 ${
                  on ? "bg-bone-0/[0.06] text-bone-0" : "text-bone-3 hover:bg-bone-0/[0.03] hover:text-bone-1"
                }`}
              >
                <span
                  className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
                  style={{ background: on ? it.color : "transparent", border: `1px solid ${it.color}` }}
                />
                <span className="grow">{it.label}</span>
                {it.experimental && <span className="text-[8px] text-bone-3/60">EXP</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* PanelRule — hairline separator between panels, with a micro-label   */
/* ------------------------------------------------------------------ */
export function PanelRule({ label }: { label: string }) {
  return (
    <div className="relative mx-3 w-px shrink-0 bg-rule" aria-hidden="true">
      <span className="absolute -top-6 left-1/2 -translate-x-1/2 whitespace-nowrap font-mono text-[8px] uppercase tracking-[0.25em] text-bone-3/70">
        {label}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Toggle — single on/off control (rule border, hover → brick)         */
/* ------------------------------------------------------------------ */
export function Toggle({
  label,
  on,
  onClick,
  disabled,
}: {
  label: string;
  on: boolean;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={on}
      className={`rounded-[3px] border px-2.5 py-1 transition-colors duration-150 ${
        disabled
          ? "cursor-not-allowed border-rule text-bone-3/40"
          : on
            ? "border-bone-0/60 bg-bone-0/[0.04] text-bone-0 hover:border-brick-glow hover:text-brick-glow"
            : "border-rule bg-bone-0/[0.02] text-bone-3 hover:border-brick-glow hover:text-brick-glow"
      }`}
    >
      {label}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* SegToggle — segmented multi-option toggle (ES/NQ, LIVE/REPLAY, …)    */
/* ------------------------------------------------------------------ */
export function SegToggle({
  options,
  value,
  onChange,
}: {
  options: readonly string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="inline-flex overflow-hidden rounded-[3px] border border-rule">
      {options.map((opt, i) => {
        const active = opt === value;
        return (
          <button
            key={opt}
            type="button"
            onClick={() => onChange(opt)}
            aria-pressed={active}
            className={`px-2.5 py-1 transition-colors duration-150 ${
              i > 0 ? "border-l border-rule" : ""
            } ${
              active
                ? "bg-bone-0/[0.06] text-bone-0"
                : "bg-bone-0/[0.01] text-bone-3 hover:text-brick-glow"
            }`}
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* FeedBadge — which data tier is feeding the terminal                 */
/* ------------------------------------------------------------------ */
export function FeedBadge({ status }: { status: FeedStatus }) {
  // Locked color tokens: turquoise = healthy live, amber = degraded-but-fresh,
  // crimson = offline, bone = neutral/transient.
  const spec: Record<FeedStatus, { label: string; dot: string; text: string }> = {
    connecting: { label: "CONNECTING", dot: "bg-bone-3", text: "text-bone-3" },
    waiting: { label: "WAITING", dot: "bg-amber-current", text: "text-amber-current" },
    live: { label: "LIVE", dot: "bg-turquoise-deep", text: "text-turquoise-deep" },
    polling: { label: "POLLING", dot: "bg-amber-current", text: "text-amber-current" },
    static: { label: "REPLAY", dot: "bg-bone-3", text: "text-bone-3" },
    error: { label: "OFFLINE", dot: "bg-crimson-deep", text: "text-crimson-deep" },
  };
  const s = spec[status];
  const pulse = status === "connecting" || status === "waiting" ? "animate-pulse" : "";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-[3px] border border-rule px-2.5 py-1 ${s.text}`}
      title={`Feed source: ${s.label.toLowerCase()}`}
      aria-live="polite"
    >
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot} ${pulse}`} aria-hidden="true" />
      {s.label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* AwaitingDataOverlay — connected, but no frame has arrived yet       */
/* ------------------------------------------------------------------ */
export function AwaitingDataOverlay({ status }: { status: FeedStatus }) {
  const line =
    status === "connecting"
      ? "Connecting to the live feed…"
      : status === "polling"
        ? "Polling the API for the latest snapshot…"
        : "Connected — waiting for the first snapshot of this minute.";
  return (
    <div className="pointer-events-none fixed inset-0 z-20 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3 text-center">
        <span className="h-2 w-2 animate-pulse rounded-full bg-amber-current" aria-hidden="true" />
        <p className="font-mono text-[12px] uppercase tracking-[0.28em] text-bone-3">Awaiting data</p>
        <p className="max-w-sm font-mono text-[11px] leading-relaxed tracking-wide text-bone-3/70">{line}</p>
        <p className="max-w-md font-mono text-[10px] leading-relaxed tracking-wide text-bone-3/40">
          No snapshot has been published yet. Confirm the worker is running and the feed has data for the
          current session.
        </p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* ReplayControlBar — VCR transport for REPLAY mode                    */
/* ------------------------------------------------------------------ */

/** Format a snapshot ts (ISO, UTC) as an ET wall-clock HH:MM for the readout. */
export function etClock(ts: string | undefined): string {
  if (!ts) return "--:--";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "--:--";
  return d.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "America/New_York",
  });
}

export interface ReplayTransport {
  playing: boolean;
  playhead: number;
  total: number;
  speed: Speed;
  tsLabel: string | undefined; // ts of the current frame for the ET clock
  onToggle: () => void;
  onStepBack: () => void;
  onStepForward: () => void;
  onSeek: (i: number) => void;
  onSpeed: (s: Speed) => void;
}

export function ReplayControlBar({
  playing,
  playhead,
  total,
  speed,
  tsLabel,
  onToggle,
  onStepBack,
  onStepForward,
  onSeek,
  onSpeed,
}: ReplayTransport) {
  const max = total > 0 ? total - 1 : 0;
  return (
    <div className="fixed bottom-7 left-1/2 z-40 w-[min(640px,calc(100vw-8rem))] -translate-x-1/2">
      <div className="flex items-center gap-4 rounded-[4px] border border-rule bg-black/80 px-4 py-2.5 backdrop-blur-sm">
        <TransportButton label="Step back 1 minute" onClick={onStepBack}>
          ⟨
        </TransportButton>
        <TransportButton label={playing ? "Pause" : "Play"} onClick={onToggle} accent>
          {playing ? "❚❚" : "▶"}
        </TransportButton>
        <TransportButton label="Step forward 1 minute" onClick={onStepForward}>
          ⟩
        </TransportButton>

        <input
          type="range"
          min={0}
          max={max}
          value={playhead}
          onChange={(e) => onSeek(Number(e.target.value))}
          aria-label="Replay position"
          className="fog-scrub h-1 grow cursor-pointer appearance-none rounded-full bg-bone-0/15 accent-[color:var(--brick-glow,#d1003a)]"
        />

        <div className="shrink-0 text-right font-mono text-[11px] leading-tight tracking-[0.12em] text-bone-2 tabular-nums">
          <div className="text-bone-0">{etClock(tsLabel)} ET</div>
          <div className="text-bone-3">
            m {total > 0 ? playhead + 1 : 0}/{total}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          {SPEEDS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onSpeed(s)}
              aria-pressed={s === speed}
              className={`rounded-[3px] border px-1.5 py-0.5 font-mono text-[10px] tracking-[0.1em] transition-colors duration-150 ${
                s === speed
                  ? "border-bone-0/60 text-bone-0"
                  : "border-rule text-bone-3 hover:text-brick-glow"
              }`}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function TransportButton({
  children,
  label,
  onClick,
  accent,
}: {
  children: ReactNode;
  label: string;
  onClick: () => void;
  accent?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-[3px] border font-mono text-[11px] transition-colors duration-150 ${
        accent
          ? "border-bone-0/50 text-bone-0 hover:border-brick-glow hover:text-brick-glow"
          : "border-rule text-bone-3 hover:border-brick-glow hover:text-brick-glow"
      }`}
    >
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* FlashIcon — corner glyph                                            */
/* ------------------------------------------------------------------ */
export function FlashIcon() {
  return (
    <svg
      width="18"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}
