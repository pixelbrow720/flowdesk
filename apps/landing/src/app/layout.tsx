import type { Metadata, Viewport } from "next";
import { Fraunces, Space_Grotesk, JetBrains_Mono } from "next/font/google";
import { LenisProvider } from "@/components/providers/lenis-provider";
import { CursorTrigger } from "@/components/atoms/cursor-trigger";
import { LangProvider } from "@/lib/i18n";
import "./globals.css";

// DISPLAY — Fraunces variable serif (editorial, premium, NOT-AI feel).
// Soft optical-size 144 for headlines; expressive but restrained.
const fraunces = Fraunces({
  subsets: ["latin"],
  weight: "variable",
  style: ["normal", "italic"],
  axes: ["opsz", "SOFT"],
  variable: "--font-display",
  display: "swap",
});

// UI — Space Grotesk (geometric, neutral, no Inter family).
const grotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-grotesk",
  display: "swap",
});

// NUMERIC — JetBrains Mono (operator console).
const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "FlowDesk — Real-time 0DTE GEX terminal for /ES & /NQ",
    template: "%s · FlowDesk",
  },
  description:
    "FlowDesk is a real-time 0DTE dealer positioning terminal for /ES and /NQ. Futures-correct math, signed orderflow, gamma walls, regime flip — one validated read per instrument per minute. Built for operators who trade flow, not opinions.",
  metadataBase: new URL("https://flowdesk.app"),
  alternates: { canonical: "/" },
  openGraph: {
    title: "FlowDesk — 0DTE GEX terminal for /ES & /NQ",
    description: "Dealer positioning, minute by minute. FOG · FLUX · ARC.",
    url: "https://flowdesk.app",
    siteName: "FlowDesk",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "FlowDesk — 0DTE GEX terminal for /ES & /NQ",
    description: "Dealer positioning, minute by minute.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
  category: "finance",
};

export const viewport: Viewport = {
  themeColor: "#000000",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${grotesk.variable} ${mono.variable}`}>
      <body className="antialiased">
        <LangProvider>
          <LenisProvider>
            <CursorTrigger />
            {children}
          </LenisProvider>
        </LangProvider>
      </body>
    </html>
  );
}
