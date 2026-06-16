"use client";

/**
 * AsciiEye — animated ASCII eye that scans and occasionally blinks.
 *
 * Behavior:
 *   - Iris position drifts horizontally (sinusoidal, ~6s cycle, ±3 chars).
 *   - Eye blinks ~once every 4-7 seconds (lid closes 200ms, opens 100ms).
 *   - Reduced-motion → static centered eye, no animation.
 *
 * Render strategy:
 *   - Pre-built character grid (ROWS × COLS) as the eye's open frame.
 *   - Per frame, we compute (irisX, blinkPhase) and stamp the iris into
 *     the open frame, OR replace mid-rows with a closed-lid line.
 *   - Output a single multi-line string into a <pre>; React only swaps the
 *     string each rAF tick, no per-character DOM nodes.
 *
 * Visual scale: ~30 cols × 11 rows. Tuned for hero top-right block.
 */

import { useEffect, useRef, useState } from "react";

// ────────────────────────────────────────────────────────────────────────────
// Eye art (open state, iris centered). 11 rows × 31 cols.
// '@' marks the iris cell (replaced per-frame). Lid rows above/below are
// the static eye outline.
const OPEN_FRAME = [
  "         .,;ooooooooooo;,.     ",
  "       ,;oooooooooooooooooo;,  ",
  "    .;oooooo;'.       .';oooo;.",
  "   ,oooooo'    .:::::.    'ooo,",
  "  oooooo    .::::OOOO::::.   oo",
  " ooooo    ::::OOO@@@OOO::::    o",
  "  oooooo    '::::OOOO::::'   oo",
  "   'oooooo,    ':::::'    ,ooo'",
  "    ':oooooo;,.       .,;oooo;'",
  "       ';oooooooooooooooooo;'  ",
  "         ''`;ooooooooooo;`''   ",
];
const COLS = OPEN_FRAME[0].length;
const ROWS = OPEN_FRAME.length;
// Iris row in the open frame (the row with '@@@'):
const IRIS_ROW = 5;
// Iris center col (the middle '@' of '@@@'):
const IRIS_CENTER_COL = 15;

// Scan motion
const SCAN_PERIOD_MS = 6000; // full left→right→left cycle
const SCAN_AMPLITUDE = 3; // ±3 chars from iris center

// Blink timing
const BLINK_MIN_GAP_MS = 4000;
const BLINK_MAX_GAP_MS = 7000;
const BLINK_CLOSE_MS = 200;
const BLINK_OPEN_MS = 100;

// Closed-lid line (replaces mid-rows during blink). Same width as COLS.
const CLOSED_LINE = "    ─────────────────────────    ";
// Pad / trim to COLS exactly:
const CLOSED_LID = CLOSED_LINE.padEnd(COLS, " ").slice(0, COLS);

function buildFrame(irisOffset: number, blinkAmount: number): string {
  // blinkAmount: 0 = fully open, 1 = fully closed.
  // We collapse rows from top and bottom toward the iris row as blink grows.
  const lines = OPEN_FRAME.slice();

  // Place iris.
  const irisCol = Math.round(IRIS_CENTER_COL + irisOffset);
  const irisLine = OPEN_FRAME[IRIS_ROW];
  // Replace the 3-char @@@ region with a moved iris.
  const before = irisLine.slice(0, IRIS_CENTER_COL - 1).replace(/@/g, "O");
  const after = irisLine.slice(IRIS_CENTER_COL + 2).replace(/@/g, "O");
  // Build new row with iris at irisCol.
  let mid = irisLine.slice(IRIS_CENTER_COL - 1, IRIS_CENTER_COL + 2);
  // Empty mid first.
  const emptyMid = mid.replace(/@/g, "O");
  let row = (before + emptyMid + after).split("");
  // Stamp iris (single char @) at irisCol if it falls within the open eye area.
  if (irisCol >= 4 && irisCol < COLS - 4) {
    row[irisCol] = "@";
    // Add a trailing softer pixel to fake the iris depth
    if (irisCol - 1 >= 4) row[irisCol - 1] = "O";
    if (irisCol + 1 < COLS - 4) row[irisCol + 1] = "O";
  }
  lines[IRIS_ROW] = row.join("").padEnd(COLS, " ").slice(0, COLS);

  if (blinkAmount > 0) {
    // Collapse rows. blinkAmount in [0,1].
    // At amount=1 we want only IRIS_ROW visible as a line (closed).
    const collapse = Math.round(blinkAmount * (ROWS / 2));
    for (let i = 0; i < ROWS; i++) {
      const distFromIris = Math.abs(i - IRIS_ROW);
      if (distFromIris > ROWS / 2 - collapse) {
        lines[i] = " ".repeat(COLS);
      }
    }
    if (blinkAmount > 0.85) {
      // Replace the iris row itself with the closed lid line.
      lines[IRIS_ROW] = CLOSED_LID;
    }
  }

  return lines.join("\n");
}

export function AsciiEye({ className = "" }: { className?: string }) {
  const [frame, setFrame] = useState<string>(() => buildFrame(0, 0));
  const rafRef = useRef<number | null>(null);
  const reducedRef = useRef(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    reducedRef.current = mq.matches;
    if (reducedRef.current) {
      setFrame(buildFrame(0, 0));
      return;
    }

    const start = performance.now();
    let nextBlinkAt =
      start + BLINK_MIN_GAP_MS + Math.random() * (BLINK_MAX_GAP_MS - BLINK_MIN_GAP_MS);
    let blinkStartedAt: number | null = null;

    const tick = (now: number) => {
      // Iris scan: sinusoidal between -SCAN_AMPLITUDE..+SCAN_AMPLITUDE.
      const scanT = ((now - start) % SCAN_PERIOD_MS) / SCAN_PERIOD_MS;
      const irisOffset = Math.sin(scanT * Math.PI * 2) * SCAN_AMPLITUDE;

      // Blink state machine.
      let blinkAmount = 0;
      if (blinkStartedAt !== null) {
        const elapsed = now - blinkStartedAt;
        if (elapsed < BLINK_CLOSE_MS) {
          blinkAmount = elapsed / BLINK_CLOSE_MS;
        } else if (elapsed < BLINK_CLOSE_MS + BLINK_OPEN_MS) {
          blinkAmount = 1 - (elapsed - BLINK_CLOSE_MS) / BLINK_OPEN_MS;
        } else {
          blinkStartedAt = null;
          nextBlinkAt =
            now +
            BLINK_MIN_GAP_MS +
            Math.random() * (BLINK_MAX_GAP_MS - BLINK_MIN_GAP_MS);
        }
      } else if (now >= nextBlinkAt) {
        blinkStartedAt = now;
      }

      setFrame(buildFrame(irisOffset, blinkAmount));
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <pre
      aria-hidden="true"
      className={`font-mono text-[11px] leading-[1.1] text-bone-2 select-none whitespace-pre ${className}`}
    >
      {frame}
    </pre>
  );
}
