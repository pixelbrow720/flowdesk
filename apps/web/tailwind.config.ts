import type { Config } from "tailwindcss";
import flowdeskPreset from "@flowdesk/tokens/tailwind-preset";

// All design tokens come from the @flowdesk/tokens preset (colors, spacing,
// radius, type, motion, shadows). No hard-coded hex here — the preset maps
// theme-aware roles to the CSS variables defined in @flowdesk/tokens/tokens.css.
const config: Config = {
  presets: [flowdeskPreset],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      // Bind the locked font families to the next/font CSS variables wired in
      // layout.tsx, falling back to the token stacks.
      fontFamily: {
        sans: ["var(--font-space-grotesk)", "\"Space Grotesk\"", "system-ui", "sans-serif"],
        display: ["var(--font-space-grotesk)", "\"Space Grotesk\"", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "\"JetBrains Mono\"", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
