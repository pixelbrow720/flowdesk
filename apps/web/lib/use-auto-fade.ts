"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface UseAutoFadeOptions {
  /** Idle delay before fading, ms. PRD #4: 2.5s. */
  idleMs?: number;
  /** When true (e.g. hover/focus within the toolbar), never fade. */
  hold?: boolean;
}

export interface UseAutoFade {
  /** Whether the element should currently be visible. */
  visible: boolean;
  /** Attach to the tracked surface to wake on pointer activity. */
  onPointerMove: () => void;
  /** Force-show (e.g. on focus). */
  show: () => void;
}

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Auto-fade controller for the floating toolbar (PRD #4): visible on pointer
 * activity, fades after `idleMs` (2.5s) of no movement, reappears on the next
 * move. Under prefers-reduced-motion the toolbar stays permanently visible
 * (no fade). While `hold` is true (pointer over / focus within) it never fades.
 */
export function useAutoFade({ idleMs = 2500, hold = false }: UseAutoFadeOptions = {}): UseAutoFade {
  const [visible, setVisible] = useState(true);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reduced = useRef(false);

  useEffect(() => {
    reduced.current = prefersReducedMotion();
    if (reduced.current) setVisible(true);
  }, []);

  const clear = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const arm = useCallback(() => {
    clear();
    if (reduced.current || hold) return; // never fade
    timer.current = setTimeout(() => setVisible(false), idleMs);
  }, [clear, hold, idleMs]);

  const show = useCallback(() => {
    setVisible(true);
    arm();
  }, [arm]);

  const onPointerMove = useCallback(() => {
    setVisible(true);
    arm();
  }, [arm]);

  // Re-evaluate the timer whenever hold changes (e.g. pointer leaves the bar).
  useEffect(() => {
    if (hold) {
      clear();
      setVisible(true);
    } else {
      arm();
    }
    return clear;
  }, [hold, arm, clear]);

  return { visible, onPointerMove, show };
}
