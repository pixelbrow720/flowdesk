"use client";

import { useEffect, useRef } from "react";
import { useDashboardStore } from "../../lib/store";
import { useTheme } from "../theme-provider";
import { SegmentedControl } from "../ui/segmented-control";
import { Toggle } from "../ui/toggle";
import { Pill } from "../ui/pill";
import { Divider } from "../ui/divider";
import { IconButton } from "../ui/icon-button";
import type { MeResponse } from "../../lib/me-mock";
import { cn } from "../../lib/cn";

export interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
  /** Account entitlement (from /api/me; mock fixture offline). */
  me: MeResponse;
  /** Force a Discord re-check (POST /api/me/recheck). Optional in preview. */
  onRecheck?: () => void;
  /** Logout (POST /api/auth/logout). Optional in preview. */
  onLogout?: () => void;
}

const FOCUSABLE =
  'a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])';

function fmtEt(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    dateStyle: "medium",
    timeStyle: "short",
  }).format(d) + " ET";
}

/**
 * Settings slide-in panel (PRD #5): from the right, 360px, glass surface,
 * ESC/overlay to close, focus-trapped. Two sections:
 *  - Tampilan: theme, profile metric, heatmap basis, render, default instrument,
 *    timezone (ET, locked in v1). Defaults Dark / Net GEX / Gamma / smooth / ES / ET.
 *  - Akun: DESK status, Discord linked, manage subscription -> flowjob.id,
 *    last role-check timestamp, re-check, logout.
 *
 * All display prefs persist via the store + flowdesk.prefs (see use-prefs).
 */
export function SettingsPanel({ open, onClose, me, onRecheck, onLogout }: SettingsPanelProps) {
  const theme = useTheme();

  const instrument = useDashboardStore((s) => s.instrument);
  const setInstrument = useDashboardStore((s) => s.setInstrument);
  const profileMetric = useDashboardStore((s) => s.profileMetric);
  const setProfileMetric = useDashboardStore((s) => s.setProfileMetric);
  const heatmapBasis = useDashboardStore((s) => s.heatmapBasis);
  const setHeatmapBasis = useDashboardStore((s) => s.setHeatmapBasis);
  const heatmapSmooth = useDashboardStore((s) => s.heatmapSmooth);
  const setHeatmapSmooth = useDashboardStore((s) => s.setHeatmapSmooth);

  const panelRef = useRef<HTMLDivElement | null>(null);
  const lastFocused = useRef<HTMLElement | null>(null);

  // ESC to close + focus trap while open; restore focus on close.
  useEffect(() => {
    if (!open) return;
    lastFocused.current = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    // Focus the first focusable element.
    const focusables = panel?.querySelectorAll<HTMLElement>(FOCUSABLE);
    focusables?.[0]?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key === "Tab" && panel) {
        const items = panel.querySelectorAll<HTMLElement>(FOCUSABLE);
        if (items.length === 0) return;
        const first = items[0]!;
        const last = items[items.length - 1]!;
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      lastFocused.current?.focus?.();
    };
  }, [open, onClose]);

  return (
    <div
      aria-hidden={!open}
      className={cn(
        "fixed inset-0 z-50",
        open ? "pointer-events-auto" : "pointer-events-none",
      )}
    >
      {/* overlay */}
      <div
        onClick={onClose}
        className={cn(
          "absolute inset-0 bg-base/40 backdrop-blur-sm transition-opacity duration-base ease-standard",
          open ? "opacity-100" : "opacity-0",
        )}
      />

      {/* panel */}
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        className={cn(
          "absolute right-0 top-0 flex h-full w-[360px] flex-col border-l border-border bg-surface shadow-elevation-2",
          "transition-transform duration-base ease-standard",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <header className="flex h-[44px] shrink-0 items-center justify-between border-b border-border px-16">
          <span className="font-display text-h2 font-semibold text-fg">Settings</span>
          <IconButton label="Close settings" onClick={onClose}>
            <span aria-hidden className="font-mono text-mono">×</span>
          </IconButton>
        </header>

        <div className="flex-1 overflow-y-auto px-16 py-16">
          {/* ── Tampilan ── */}
          <Section title="Tampilan">
            <Row label="Tema">
              <SegmentedControl
                ariaLabel="Theme"
                value={theme.theme}
                onChange={theme.setTheme}
                options={[
                  { value: "dark", label: "DARK" },
                  { value: "light", label: "LIGHT" },
                ]}
              />
            </Row>
            <Row label="Metric profil">
              <SegmentedControl
                ariaLabel="Profile metric"
                value={profileMetric}
                onChange={setProfileMetric}
                options={[
                  { value: "GEX", label: "NET GEX" },
                  { value: "DEX", label: "NET DEX" },
                ]}
              />
            </Row>
            <Row label="Basis heatmap">
              <SegmentedControl
                ariaLabel="Heatmap basis"
                value={heatmapBasis}
                onChange={setHeatmapBasis}
                options={[
                  { value: "GAMMA", label: "GAMMA" },
                  { value: "DELTA", label: "DELTA" },
                ]}
              />
            </Row>
            <Row label="Render">
              <Toggle
                checked={heatmapSmooth}
                onChange={setHeatmapSmooth}
                label={heatmapSmooth ? "Smooth" : "Block"}
              />
            </Row>
            <Row label="Instrumen default">
              <SegmentedControl
                ariaLabel="Default instrument"
                value={instrument}
                onChange={setInstrument}
                options={[
                  { value: "ES", label: "ES" },
                  { value: "NQ", label: "NQ" },
                ]}
              />
            </Row>
            <Row label="Timezone">
              <span className="font-mono text-caption tabular-nums text-muted">
                ET (America/New_York)
              </span>
            </Row>
          </Section>

          <Divider className="my-16" />

          {/* ── Akun ── */}
          <Section title="Akun">
            <Row label="Status">
              {me.has_desk ? (
                <Pill tone="positive" glow>DESK</Pill>
              ) : me.grace_until ? (
                <Pill tone="positive">DESK · GRACE</Pill>
              ) : me.is_member ? (
                <Pill tone="negative">NO DESK</Pill>
              ) : (
                <Pill tone="neutral">ANON</Pill>
              )}
            </Row>
            <Row label="Discord">
              <span className="font-mono text-caption tabular-nums text-fg">
                {me.discord_id ? `linked · ${me.discord_id.slice(0, 6)}…` : "not linked"}
              </span>
            </Row>
            <Row label="Dicek terakhir">
              <span className="font-mono text-caption tabular-nums text-muted">
                {fmtEt(me.last_checked)}
              </span>
            </Row>
            <Row label="Langganan">
              <a
                href={me.cta.buy_url}
                target="_blank"
                rel="noreferrer"
                className="font-display text-caption text-turquoise underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-turquoise"
              >
                Kelola → flowjob.id
              </a>
            </Row>

            <div className="mt-12 flex flex-col gap-8">
              {me.cta.recheck_supported && (
                <button
                  type="button"
                  onClick={onRecheck}
                  className="h-32 rounded border border-border bg-bg px-12 font-display text-caption text-fg transition-[border] duration-base ease-standard hover:border-turquoise/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-turquoise"
                >
                  Cek ulang role
                </button>
              )}
              <button
                type="button"
                onClick={onLogout}
                className="h-32 rounded border border-crimson/40 bg-crimson/10 px-12 font-display text-caption text-crimson transition-[background] duration-base ease-standard hover:bg-crimson/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-crimson"
              >
                Keluar
              </button>
            </div>
          </Section>
        </div>
      </aside>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-12">
      <h3 className="font-display text-[11px] uppercase tracking-[0.08em] text-muted">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-12">
      <span className="font-display text-caption text-fg">{label}</span>
      {children}
    </div>
  );
}
