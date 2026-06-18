"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Fog + Arc now live on ONE scrolling page (/fog); the tabs are scroll anchors
// into the two sections rather than separate routes.
const TABS = [
  { href: "/fog#fog", label: "Fog" },
  { href: "/fog#arc", label: "Arc" },
] as const;

export function Navbar() {
  const pathname = usePathname();
  const onTerminal = pathname === "/fog";

  return (
    <header className="fixed inset-x-0 top-0 z-50 pointer-events-none">
      <div className="flex items-center justify-between pt-8 px-8">
        {/* Tabs — left */}
        <nav className="pointer-events-auto flex items-center gap-7">
          {TABS.map((tab) => (
            <Link
              key={tab.href}
              href={tab.href}
              className={`font-mono text-sm tracking-wide transition-colors duration-150 ${
                onTerminal ? "text-bone-0 hover:text-brick-glow" : "text-bone-0 hover:text-brick-glow"
              }`}
            >
              {tab.label}
            </Link>
          ))}
        </nav>

        {/* Gear — right */}
        <Link
          href="/settings"
          aria-label="Settings"
          className={`pointer-events-auto transition-colors duration-150 ${
            pathname === "/settings"
              ? "text-brick-glow"
              : "text-bone-0 hover:text-brick-glow"
          }`}
        >
          <GearIcon />
        </Link>
      </div>
    </header>
  );
}

function GearIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

export default Navbar;
