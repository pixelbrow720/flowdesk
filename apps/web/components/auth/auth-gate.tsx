"use client";

import type { ReactNode } from "react";
import { deriveAuthView } from "../../lib/auth-copy";
import type { UseMe } from "../../lib/use-me";
import { BlurOverlay } from "../ui/blur-overlay";
import { Panel } from "../ui/panel";
import { Button } from "../ui/button";
import { Spinner } from "../ui/spinner";
import { AuthBanner } from "./auth-banner";
import { Toast } from "./toast";

export interface AuthGateProps {
  auth: UseMe;
  /** The full dashboard (rendered for DESK, and blurred underneath for NO_DESK). */
  children: ReactNode;
}

const DISCORD_LOGO = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
    <path d="M20.3 4.4A19.8 19.8 0 0 0 15.4 3l-.2.5c1.8.4 2.6.9 3.5 1.6a13.7 13.7 0 0 0-12-.5c-.5.2-.8.4-.8.4.9-.7 1.9-1.3 3.6-1.6L9.2 3c-1.8.2-3.5.7-5 1.4C1.6 8 .9 11.6 1.2 15.1a20 20 0 0 0 6 3l.6-1c-1-.3-1.8-.7-2.6-1.2l.6-.4c3.6 1.7 7.7 1.7 11.3 0l.6.4c-.8.5-1.7.9-2.6 1.2l.6 1a20 20 0 0 0 6-3c.4-4.2-.6-7.7-3-10.7ZM8.4 13c-.7 0-1.3-.7-1.3-1.5S7.7 10 8.4 10s1.3.7 1.3 1.5S9.1 13 8.4 13Zm7.2 0c-.7 0-1.3-.7-1.3-1.5S14.9 10 15.6 10s1.3.7 1.3 1.5S16.3 13 15.6 13Z" />
  </svg>
);

/**
 * Route guard for the dashboard (PRD #6). Drives the three access experiences
 * entirely from `/api/me`:
 *  - ANON: a login screen ("Masuk dengan Discord") over a blurred preview.
 *  - NO_DESK: the full dashboard rendered but BLURRED, with join/buy CTAs and a
 *    "Saya sudah punya DESK — cek ulang" button (with loading + result toast).
 *  - DESK: the full app (plus a grace banner when grace_until is set).
 */
export function AuthGate({ auth, children }: AuthGateProps) {
  const { me, recheckStatus, recheck, login, logout } = auth;
  const d = deriveAuthView(me);

  const toastOpen = recheckStatus === "success" || recheckStatus === "error";
  const toastMessage =
    recheckStatus === "success"
      ? "Status diperbarui."
      : "Gagal memperbarui status. Coba lagi.";

  // DESK: full app (+ optional grace banner). The preview-blur states layer on
  // top of the same children, so data components mount once.
  if (d.view === "DESK") {
    return (
      <div className="flex h-full flex-col">
        <AuthBanner kind={d.banner} graceUntil={me.grace_until} />
        <div className="min-h-0 flex-1">{children}</div>
        <Toast open={toastOpen} message={toastMessage} tone={recheckStatus === "success" ? "success" : "error"} />
      </div>
    );
  }

  // ANON / NO_DESK: render the shell blurred underneath, CTAs on top.
  return (
    <div className="relative h-full">
      {/* The dashboard preview underneath (inert, blurred). */}
      <div aria-hidden className="pointer-events-none h-full select-none">
        {children}
      </div>

      <BlurOverlay intensity={d.view === "ANON" ? "lg" : "md"}>
        <Panel variant="glass" className="flex w-[360px] flex-col gap-16 p-24">
          <div className="flex flex-col gap-8">
            <h2 className="font-display text-h2 font-semibold text-fg">{d.copy.title}</h2>
            <p className="font-display text-body text-muted">{d.copy.body}</p>
          </div>

          {d.view === "ANON" ? (
            <Button variant="primary" onClick={login} className="w-full">
              {DISCORD_LOGO}
              Masuk dengan Discord
            </Button>
          ) : (
            <div className="flex flex-col gap-8">
              {d.showJoin && (
                <a
                  href={me.cta.join_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex h-32 w-full items-center justify-center gap-8 rounded bg-turquoise px-16 font-display text-body font-medium text-base transition-opacity duration-base ease-standard hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-turquoise"
                >
                  {DISCORD_LOGO}
                  Join Discord
                </a>
              )}
              <a
                href={me.cta.buy_url}
                target="_blank"
                rel="noreferrer"
                className={`inline-flex h-32 w-full items-center justify-center rounded px-16 font-display text-body font-medium transition-[opacity,border] duration-base ease-standard focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-turquoise ${
                  d.showJoin
                    ? "border border-border text-fg hover:border-turquoise/60"
                    : "bg-turquoise text-base hover:opacity-90"
                }`}
              >
                Beli DESK
              </a>
              {d.showRecheck && (
                <Button
                  variant="secondary"
                  onClick={recheck}
                  disabled={recheckStatus === "loading"}
                  className="w-full"
                >
                  {recheckStatus === "loading" && <Spinner size="sm" />}
                  Saya sudah punya DESK — cek ulang
                </Button>
              )}
              <button
                type="button"
                onClick={logout}
                className="mt-4 font-display text-caption text-muted underline-offset-2 hover:text-fg hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-turquoise"
              >
                Keluar
              </button>
            </div>
          )}
        </Panel>
      </BlurOverlay>

      <Toast
        open={toastOpen}
        message={toastMessage}
        tone={recheckStatus === "success" ? "success" : "error"}
      />
    </div>
  );
}
