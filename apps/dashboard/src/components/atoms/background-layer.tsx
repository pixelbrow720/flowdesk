"use client";

/**
 * BackgroundLayer — sits behind dashboard chrome.
 * - Noise grain canvas: permanent subtle texture (operator terminal feel).
 * - EntranceVeil: animated WebGL "fog" yang fade-out sekali per session
 *   sebagai intro signature.
 *
 * Both fixed full-viewport, pointer-events-none, low z-index.
 */

import dynamic from "next/dynamic";
import { EntranceVeil } from "@/components/atoms/entrance-veil";

const Noise = dynamic(() => import("@/components/Noise"), { ssr: false });

export function BackgroundLayer() {
  return (
    <>
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 z-[1]"
      >
        <Noise
          patternSize={250}
          patternScaleX={1}
          patternScaleY={1}
          patternRefreshInterval={3}
          patternAlpha={7}
        />
      </div>
      <EntranceVeil />
    </>
  );
}

export default BackgroundLayer;
