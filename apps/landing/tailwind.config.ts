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
        crimson: {
          DEFAULT: "#E63946",
          deep: "#C12836",
          glow: "#FF4D5C",
        },
        signal: {
          green: "#4ADE80",
          amber: "#F59E0B",
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
