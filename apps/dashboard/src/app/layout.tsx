import type { Metadata, Viewport } from "next";
import { Fraunces, Space_Grotesk, JetBrains_Mono } from "next/font/google";
import { DashboardShell } from "@/components/shell/dashboard-shell";
import { BackgroundLayer } from "@/components/atoms/background-layer";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  weight: "variable",
  style: ["normal", "italic"],
  axes: ["opsz", "SOFT"],
  variable: "--font-display",
  display: "swap",
});

const grotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-grotesk",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "FlowDesk · Terminal",
    template: "%s · FlowDesk",
  },
  description:
    "FlowDesk dashboard — 0DTE dealer positioning for /ES & /NQ. FOG · FLUX · ARC.",
  robots: { index: false, follow: false }, // dashboard = private
};

export const viewport: Viewport = {
  themeColor: "#000000",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${fraunces.variable} ${grotesk.variable} ${mono.variable}`}
    >
      <body className="antialiased">
        <BackgroundLayer />
        <DashboardShell>{children}</DashboardShell>
      </body>
    </html>
  );
}
