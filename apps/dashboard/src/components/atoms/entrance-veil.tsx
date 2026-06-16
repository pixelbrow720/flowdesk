"use client";

/**
 * EntranceVeil — DarkVeil intro overlay yang muncul sekali per session
 * (sessionStorage flag), lalu fade-out. Skip total kalau prefers-reduced-motion.
 *
 * Konsep: di dashboard, "fog" adalah kondisi awal pasar — uncertain dealer
 * positioning sebelum data settle. Veil = visual representasi fog itu, hilang
 * setelah operator mulai membaca lensa.
 */

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";

const DarkVeil = dynamic(() => import("@/components/DarkVeil"), { ssr: false });

const SESSION_KEY = "fd:dash-veil-shown";
const FADE_OUT_MS = 1600;
const VISIBLE_MS = 1400;

export function EntranceVeil() {
  const [phase, setPhase] = useState<"idle" | "visible" | "fading" | "done">(
    "idle"
  );
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mq.matches) {
      setReducedMotion(true);
      return;
    }
    if (sessionStorage.getItem(SESSION_KEY) === "1") {
      setPhase("done");
      return;
    }
    sessionStorage.setItem(SESSION_KEY, "1");
    setPhase("visible");
    const t1 = window.setTimeout(() => setPhase("fading"), VISIBLE_MS);
    const t2 = window.setTimeout(
      () => setPhase("done"),
      VISIBLE_MS + FADE_OUT_MS
    );
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, []);

  if (reducedMotion || phase === "idle" || phase === "done") return null;

  const opacity = phase === "fading" ? 0 : 0.85;

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-[5] transition-opacity ease-out"
      style={{
        opacity,
        transitionDuration: `${FADE_OUT_MS}ms`,
      }}
    >
      <DarkVeil
        // Brick-side palette: shift CPPN purple toward red.
        hueShift={-95}
        noiseIntensity={0.04}
        scanlineIntensity={0.05}
        speed={0.35}
        scanlineFrequency={0.4}
        warpAmount={0.05}
        resolutionScale={1}
      />
    </div>
  );
}

export default EntranceVeil;
