import type { Metadata, Viewport } from "next";
import { JetBrains_Mono } from "next/font/google";
import { Navbar } from "@/components/navbar";
import "./globals.css";

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "FlowDesk",
    template: "%s · FlowDesk",
  },
  description: "FlowDesk dashboard.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#000000",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={mono.variable}>
      <body className="bg-black text-bone-0 antialiased font-mono min-h-screen">
        <Navbar />
        <main>{children}</main>
      </body>
    </html>
  );
}
