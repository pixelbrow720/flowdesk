"use client";

/**
 * TerminalShell — the common page frame every lens (Fog / Flux / Arc) renders
 * inside. It owns the shared chrome (feed badge, ES/NQ + LIVE/REPLAY toggles,
 * the awaiting-data overlay, the replay transport, the corner glyph) and leaves
 * three slots for the lens:
 *
 *   - `toolbarExtra` : lens-specific controls placed left of the shared toggles
 *                       (e.g. Fog's GEX/DEX + IV-smile, Flux's series toggles).
 *   - `header`       : the top-center readout strip (price · regime · …).
 *   - `children`     : the lens body (charts/panels), given the full viewport
 *                       minus the top toolbar + bottom transport gutters.
 *
 * Wiring the shell once means a new lens only writes its body + a couple of
 * toggles, and automatically inherits identical controls + replay behaviour.
 */

import { type ReactNode } from "react";
import {
  AwaitingDataOverlay,
  FeedBadge,
  FlashIcon,
  ReplayControlBar,
  SegToggle,
} from "@/components/terminal/chrome";
import type { Instrument } from "@/lib/api";
import type { TerminalFeed } from "@/lib/useTerminalFeed";

export function TerminalShell({
  feed,
  toolbarExtra,
  header,
  children,
}: {
  feed: TerminalFeed;
  toolbarExtra?: ReactNode;
  header?: ReactNode;
  children: ReactNode;
}) {
  const { mode, setMode, instrument, setInstrument, status, awaitingData, replay } = feed;

  return (
    <div className="relative min-h-screen w-full overflow-x-hidden bg-black text-bone-0">
      {/* Toolbar — top-right: lens controls + shared toggles + feed status. */}
      <div className="fixed right-6 top-[4.5rem] z-40 flex items-center gap-2 font-mono text-[11px] tracking-[0.16em]">
        <FeedBadge status={status} />
        {toolbarExtra}
        <SegToggle
          options={["ES", "NQ"]}
          value={instrument}
          onChange={(v) => setInstrument(v as Instrument)}
        />
        <SegToggle
          options={["LIVE", "REPLAY"]}
          value={mode === "live" ? "LIVE" : "REPLAY"}
          onChange={(v) => setMode(v === "LIVE" ? "live" : "replay")}
        />
      </div>

      {/* Top-center readout strip (lens-provided). */}
      {header}

      {/* Lens body. */}
      {children}

      {/* Empty-state overlay — connected to a real source but no frame yet. */}
      {awaitingData ? <AwaitingDataOverlay status={status} /> : null}

      {/* Replay transport — only in REPLAY mode. */}
      {mode === "replay" ? (
        <ReplayControlBar
          playing={replay.playing}
          playhead={replay.playhead}
          total={replay.total}
          speed={replay.speed}
          tsLabel={replay.frames.length > 0 ? replay.frames[replay.frames.length - 1].ts : undefined}
          onToggle={replay.toggle}
          onStepBack={replay.stepBack}
          onStepForward={replay.stepForward}
          onSeek={replay.seek}
          onSpeed={replay.setSpeed}
        />
      ) : null}

      {/* Bottom-left flash glyph. */}
      <button
        type="button"
        aria-label="Quick action"
        className="fixed bottom-7 left-8 z-40 text-bone-3 transition-colors duration-150 hover:text-brick-glow"
      >
        <FlashIcon />
      </button>
    </div>
  );
}
