import type { Metadata, Viewport } from "next";
import { Space_Grotesk, JetBrains_Mono } from "next/font/google";
import { LenisProvider } from "@/components/providers/lenis-provider";
import { Cursor } from "@/components/atoms/cursor";
import "./globals.css";

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
    default: "FlowDesk — Operator-grade workspace for serious teams",
    template: "%s · FlowDesk",
  },
  description:
    "FlowDesk is the workspace for operators. Decisions, execution, and signal — without the bloat. FOG context engine, FLUX automation, ARC orchestration.",
  metadataBase: new URL("https://flowdesk.app"),
  alternates: { canonical: "/" },
  openGraph: {
    title: "FlowDesk — Operator-grade workspace",
    description: "Decisions, execution, signal. Without bloat.",
    url: "https://flowdesk.app",
    siteName: "FlowDesk",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "FlowDesk — Operator-grade workspace",
    description: "Decisions, execution, signal. Without bloat.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
  category: "technology",
};

export const viewport: Viewport = {
  themeColor: "#0A0A0B",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${grotesk.variable} ${mono.variable}`}>
      <body className="grain antialiased">
        <LenisProvider>
          {children}
          <Cursor />
        </LenisProvider>
      </body>
    </html>
  );
}
