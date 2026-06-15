import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          0: "#0A0A0B",
          1: "#101012",
          2: "#16161A",
          3: "#1F1F25",
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
        // Secondary accent — deep teal (petrol)
        // For signal/info/secondary CTAs. NOT cyan, NOT mint.
        teal: {
          DEFAULT: "#1F8A8C",
          deep: "#155C5E",
          glow: "#3FB0B2",
        },
        signal: {
          teal: "#1F8A8C",
          amber: "#D4A445",
        },
      },
      fontFamily: {
        sans: ["var(--font-grotesk)", "ui-sans-serif", "system-ui"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      letterSpacing: {
        tightest: "-0.04em",
        snug: "-0.02em",
      },
      fontSize: {
        "display-1": ["clamp(4rem, 12vw, 11rem)", { lineHeight: "0.92", letterSpacing: "-0.04em", fontWeight: "600" }],
        "display-2": ["clamp(3rem, 8vw, 7rem)", { lineHeight: "0.95", letterSpacing: "-0.03em", fontWeight: "600" }],
        eyebrow: ["0.75rem", { lineHeight: "1", letterSpacing: "0.18em", fontWeight: "500" }],
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
