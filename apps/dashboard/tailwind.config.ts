import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          0: "#000000",
          1: "#080809",
        },
        bone: {
          0: "#FAFAF7",
          3: "#8E8E88",
        },
        brick: {
          DEFAULT: "#B8333E",
          glow: "#D54452",
        },
        // Heatmap gradient (Fog price-tape)
        turquoise: {
          deep: "#0FB5A8",
        },
        crimson: {
          deep: "#B5002E",
        },
        // Current-price marker (price ladder)
        amber: {
          current: "#F59E0B",
        },
        // Bar chart accents (positive / negative pressure)
        tide: {
          blue: "#5BA3D0",
          red: "#D9534F",
        },
        // Hairline frame separators
        rule: {
          DEFAULT: "#161618",
        },
      },
    },
  },
  plugins: [],
};

export default config;
