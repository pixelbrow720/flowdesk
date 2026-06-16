"use client";

/**
 * DashboardShell — chrome around all lens pages.
 *
 * Layout:
 *   ┌───────────────────────────────────────────────────────────┐
 *   │ TopBar: brand · lens switcher · instrument · clock · acct │
 *   ├───────────────────────────────────────────────────────────┤
 *   │ {children} — full-bleed lens content                       │
 *   ├───────────────────────────────────────────────────────────┤
 *   │ StatusBar: snapshot age · session · feed health            │
 *   └───────────────────────────────────────────────────────────┘
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const LENSES = [
  { href: "/fog", label: "FOG", hint: "Positioning" },
  { href: "/flux", label: "FLUX", hint: "Orderflow" },
  { href: "/arc", label: "ARC", hint: "Surface" },
  { href: "/settings", label: "SETTINGS", hint: "Account" },
] as const;

function TopBar() {
  const pathname = usePathname();
  const activePath = "/" + (pathname?.split("/")[1] || "fog");

  return (
    <header className="relative z-30 border-b border-[color:var(--hairline)] bg-ink-0/70 backdrop-blur-md">
      <div className="flex h-12 items-center px-5 gap-6">
        {/* Brand mark */}
        <Link
          href="/fog"
          className="flex items-center gap-2.5 font-mono text-[11px] uppercase tracking-[0.22em]"
        >
          <span className="grid h-3 w-3 place-items-center">
            <span className="h-2 w-2 bg-brick" />
          </span>
          <span className="text-bone-1">FlowDesk</span>
          <span className="text-bone-3">·</span>
          <span className="text-bone-3">Terminal</span>
        </Link>

        {/* Lens switcher */}
        <nav className="flex items-center gap-0.5 ml-4">
          {LENSES.map((l) => {
            const active = activePath === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                className={[
                  "group relative px-3.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.18em] transition-colors",
                  active ? "text-bone-0" : "text-bone-3 hover:text-bone-1",
                ].join(" ")}
              >
                <span className="relative z-10">{l.label}</span>
                {active && (
                  <span className="absolute inset-x-0 -bottom-[1px] h-px bg-brick" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Right cluster */}
        <div className="ml-auto flex items-center gap-5 font-mono text-[11px] tracking-[0.1em]">
          <InstrumentSelector />
          <Clock />
          <Account />
        </div>
      </div>
    </header>
  );
}

function InstrumentSelector() {
  const [inst, setInst] = useState<"ES" | "NQ">("ES");
  return (
    <div className="flex items-center gap-1">
      {(["ES", "NQ"] as const).map((s) => (
        <button
          key={s}
          onClick={() => setInst(s)}
          className={[
            "px-2 py-1 transition-colors",
            inst === s
              ? "bg-brick/15 text-brick-glow"
              : "text-bone-3 hover:text-bone-1",
          ].join(" ")}
        >
          /{s}
        </button>
      ))}
    </div>
  );
}

function Clock() {
  const [t, setT] = useState<string>("--:--:--");
  useEffect(() => {
    const fmt = () => {
      const d = new Date();
      // ET (America/New_York) — markets reference
      const et = new Intl.DateTimeFormat("en-US", {
        timeZone: "America/New_York",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }).format(d);
      setT(et + " ET");
    };
    fmt();
    const id = window.setInterval(fmt, 1000);
    return () => window.clearInterval(id);
  }, []);
  return <span className="text-bone-3 tabular-nums">{t}</span>;
}

function Account() {
  return (
    <button
      type="button"
      className="flex items-center gap-1.5 px-2 py-1 text-bone-3 hover:text-bone-1 transition-colors"
      aria-label="Account"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-brick" />
      <span>Operator</span>
    </button>
  );
}

function StatusBar() {
  return (
    <footer className="relative z-30 border-t border-[color:var(--hairline)] bg-ink-0/70 backdrop-blur-md">
      <div className="flex h-7 items-center px-5 gap-6 font-mono text-[10px] uppercase tracking-[0.2em] text-bone-3">
        <span>
          <span className="text-bone-2">snapshot</span>{" "}
          <span className="text-bone-1 tabular-nums">--:--</span>{" "}
          <span className="text-bone-3">ago</span>
        </span>
        <span>
          <span className="text-bone-2">session</span>{" "}
          <span className="text-bone-1">RTH</span>
        </span>
        <span>
          <span className="text-bone-2">feed</span>{" "}
          <span className="text-brick-glow">● historical-sim</span>
        </span>
        <span className="ml-auto">
          schema_v1 · build {process.env.NEXT_PUBLIC_BUILD || "dev"}
        </span>
      </div>
    </footer>
  );
}

export function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative z-10 flex min-h-screen flex-col">
      <TopBar />
      <main className="flex-1 relative">{children}</main>
      <StatusBar />
    </div>
  );
}
