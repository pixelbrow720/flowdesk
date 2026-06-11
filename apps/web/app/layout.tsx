import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Space_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "../components/theme-provider";

// Locked typography: Space Grotesk (UI/display) + JetBrains Mono (numbers).
// Loaded via next/font so we never ship Inter or a decorative fallback. The
// CSS variables below are bound to the token font stacks in tailwind.config.ts.
const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600", "700"],
  variable: "--font-space-grotesk",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500"],
  variable: "--font-jetbrains-mono",
});

export const metadata: Metadata = {
  title: "FlowDesk",
  description:
    "Real-time 0DTE GEX/DEX dealer exposure terminal for /ES and /NQ futures.",
};

// Set the persisted theme before first paint to avoid a dark->light flash.
// Reads the single flowdesk.prefs key (PRD #5).
const NO_FLASH = `(function(){try{var p=JSON.parse(localStorage.getItem("flowdesk.prefs")||"{}");if(p&&p.theme==="light"){document.documentElement.setAttribute("data-theme","light");}}catch(e){}})();`;

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${jetbrainsMono.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: NO_FLASH }} />
      </head>
      <body className="min-h-screen bg-bg font-display text-fg antialiased">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
