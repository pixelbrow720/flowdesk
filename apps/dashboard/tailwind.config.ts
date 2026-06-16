import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          0: "#000000",
          1: "#080809",
          2: "#0F0F12",
          3: "#16161A",
        },
        bone: {
          0: "#FAFAF7",
          1: "#EDEDE7",
          2: "#C9C9C2",
          3: "#8E8E88",
        },
        // Primary accent — toned-down crimson (brick / kiln)
        // Less saturation than #E63946, reads "considered" not "alarm"
        brick: {
          DEFAULT: "#B8333E",
          deep: "#8E232C",
          glow: "#D54452",
        },
        // Backwards-compat alias so old `crimson` classes still work
        crimson: {
          DEFAULT: "#B8333E",
          deep: "#8E232C",
          glow: "#D54452",
        },
        // NO secondary accent. Monochrome brick.
        // Legacy `teal-*` / `signal-*` classes resolve to brick to keep older
        // imports compiling — they will be migrated out as sections are rewritten.
        teal: {
          DEFAULT: "#B8333E",
          deep: "#8E232C",
          glow: "#D54452",
        },
        signal: {
          teal: "#B8333E",
          amber: "#B8333E",
        },
      },
      fontFamily: {
        // sans = UI body (Grotesk geometric, neutral)
        sans: ["var(--font-grotesk)", "ui-sans-serif", "system-ui"],
        // display = editorial headline (Fraunces variable serif — premium, NOT-AI)
        display: ["var(--font-display)", "ui-serif", "Georgia", "serif"],
        // mono = numbers, code, operator console
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      letterSpacing: {
        tightest: "-0.04em",
        snug: "-0.02em",
      },
      fontSize: {
        // Display sizes use display family (Fraunces). Tighter line-height for serif gravitas.
        "display-1": ["clamp(4rem, 12vw, 11rem)", { lineHeight: "0.88", letterSpacing: "-0.035em", fontWeight: "500" }],
        "display-2": ["clamp(3rem, 8vw, 7rem)", { lineHeight: "0.92", letterSpacing: "-0.025em", fontWeight: "500" }],
        eyebrow: ["0.75rem", { lineHeight: "1", letterSpacing: "0.22em", fontWeight: "500" }],
      },
      animation: {
        "marquee": "marquee 40s linear infinite",
      },
      keyframes: {
        marquee: {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
