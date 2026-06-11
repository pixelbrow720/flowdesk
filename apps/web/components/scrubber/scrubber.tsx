"use client";

import { useEffect, useMemo } from "react";
import { useDashboardStore, type Speed } from "../../lib/store";
import { MOCK_SESSIONS, getFullSession } from "../../lib/replay-mock";
import { IconButton } from "../ui/icon-button";
import { Pill } from "../ui/pill";
import { SegmentedControl } from "../ui/segmented-control";
import { cn } from "../../lib/cn";

export interface ScrubberProps {
  className?: string;
}

const SPEEDS: { value: string; label: string }[] = [
  { value: "1", label: "1x" },
  { value: "2", label: "2x" },
  { value: "4", label: "4x" },
];

/** Format an ET HH:MM label from a snapshot ts (America/New_York). */
function etTime(ts: string): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "--:--";
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

/**
 * Bottom scrubber bar (56px, PRD #10 / #4): a session timeline with a position
 * marker + ET time readout, transport controls (play/pause, ±1 minute step,
 * 1x/2x/4x speed), a session/date selector, a REPLAY badge, and a "Kembali ke
 * LIVE" button. Drives the store; uses mock sessions + frames offline.
 *
 * LIVE mode: scrubber tracks the newest minute (read-only position at the end).
 * REPLAY mode: scrubbing/stepping/playing moves through the loaded frames.
 */
export function Scrubber({ className }: ScrubberProps) {
  const instrument = useDashboardStore((s) => s.instrument);
  const mode = useDashboardStore((s) => s.mode);
  const frames = useDashboardStore((s) => s.frames);
  const frameIndex = useDashboardStore((s) => s.frameIndex);
  const replayDate = useDashboardStore((s) => s.replayDate);
  const playing = useDashboardStore((s) => s.playing);
  const speed = useDashboardStore((s) => s.speed);
  const snapshot = useDashboardStore((s) => s.snapshot);

  const enterReplay = useDashboardStore((s) => s.enterReplay);
  const exitToLive = useDashboardStore((s) => s.exitToLive);
  const setFrameIndex = useDashboardStore((s) => s.setFrameIndex);
  const stepFrame = useDashboardStore((s) => s.stepFrame);
  const setPlaying = useDashboardStore((s) => s.setPlaying);
  const setSpeed = useDashboardStore((s) => s.setSpeed);

  const sessions = MOCK_SESSIONS[instrument];
  const isReplay = mode === "REPLAY";

  // Position 0..1 along the timeline. In LIVE the marker sits at the end.
  const maxIndex = isReplay ? Math.max(0, frames.length - 1) : 1;
  const position = isReplay ? frameIndex : maxIndex;
  const minuteLabel = etTime(snapshot.ts);

  // Playback timer: advance one frame per (1000 / speed) ms while playing.
  useEffect(() => {
    if (!isReplay || !playing) return;
    const period = 1000 / speed;
    const id = setInterval(() => {
      const s = useDashboardStore.getState();
      if (s.frameIndex >= s.frames.length - 1) {
        s.setPlaying(false);
      } else {
        s.stepFrame(1);
      }
    }, period);
    return () => clearInterval(id);
  }, [isReplay, playing, speed]);

  const onSelectSession = (date: string) => {
    const f = getFullSession(instrument, date);
    enterReplay(date, f);
  };

  const onScrub = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!isReplay) {
      // Entering replay by scrubbing: load the most recent session first.
      const recent = sessions[0];
      if (recent) {
        const f = getFullSession(instrument, recent.session_date);
        enterReplay(recent.session_date, f);
      }
      return;
    }
    setPlaying(false);
    setFrameIndex(Number(e.target.value));
  };

  const pct = useMemo(
    () => (maxIndex > 0 ? (position / maxIndex) * 100 : 100),
    [position, maxIndex],
  );

  return (
    <div
      className={cn(
        "flex h-[56px] shrink-0 items-center gap-16 border-t border-border bg-surface px-16",
        className,
      )}
      role="group"
      aria-label="Replay scrubber"
    >
      {/* transport */}
      <div className="flex items-center gap-4">
        <IconButton
          label="Step back one minute"
          disabled={!isReplay || frameIndex <= 0}
          onClick={() => stepFrame(-1)}
        >
          <span aria-hidden className="font-mono text-mono">⏮</span>
        </IconButton>
        <IconButton
          label={playing ? "Pause" : "Play"}
          disabled={!isReplay}
          onClick={() => setPlaying(!playing)}
        >
          <span aria-hidden className="font-mono text-mono">{playing ? "⏸" : "▶"}</span>
        </IconButton>
        <IconButton
          label="Step forward one minute"
          disabled={!isReplay || frameIndex >= maxIndex}
          onClick={() => stepFrame(1)}
        >
          <span aria-hidden className="font-mono text-mono">⏭</span>
        </IconButton>
      </div>

      {/* speed */}
      <SegmentedControl
        ariaLabel="Playback speed"
        value={String(speed)}
        onChange={(v) => setSpeed(Number(v) as Speed)}
        options={SPEEDS}
      />

      {/* timeline */}
      <div className="relative flex min-w-0 flex-1 items-center">
        <input
          type="range"
          aria-label="Session timeline"
          min={0}
          max={maxIndex}
          step={1}
          value={position}
          onChange={onScrub}
          className="h-4 w-full cursor-pointer appearance-none rounded-full bg-border accent-turquoise"
          style={{
            background: `linear-gradient(to right, var(--color-turquoise) ${pct}%, var(--color-border) ${pct}%)`,
          }}
        />
      </div>

      {/* time readout */}
      <span className="font-mono text-mono tabular-nums text-fg">{minuteLabel} ET</span>

      {/* session selector */}
      <select
        aria-label="Replay session date"
        value={replayDate ?? ""}
        onChange={(e) => onSelectSession(e.target.value)}
        className="h-32 rounded border border-border bg-bg px-8 font-mono text-caption tabular-nums text-fg"
      >
        <option value="" disabled>
          Session…
        </option>
        {sessions.map((s) => (
          <option key={s.session_date} value={s.session_date}>
            {s.session_date}
          </option>
        ))}
      </select>

      {/* mode badge / back-to-live */}
      {isReplay ? (
        <button
          type="button"
          onClick={exitToLive}
          className="inline-flex items-center gap-8 rounded-full border border-turquoise/40 bg-turquoise/15 px-12 py-4 font-display text-caption uppercase tracking-[0.04em] text-turquoise transition-[background] duration-base ease-standard hover:bg-turquoise/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-turquoise"
        >
          Kembali ke LIVE
        </button>
      ) : (
        <Pill tone="positive" glow>
          LIVE
        </Pill>
      )}
      {isReplay && (
        <Pill tone="neutral" className="border-fg/30 text-fg">
          REPLAY
        </Pill>
      )}
    </div>
  );
}
