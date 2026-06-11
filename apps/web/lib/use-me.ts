"use client";

import { useCallback, useState } from "react";
import type { MeResponse } from "./me-mock";

export type RecheckStatus = "idle" | "loading" | "success" | "error";

export interface UseMe {
  me: MeResponse;
  recheckStatus: RecheckStatus;
  /** Force a Discord re-check (POST /api/me/recheck). */
  recheck: () => Promise<void>;
  /** Navigate to the Discord login (browser redirect, not fetch). */
  login: () => void;
  /** Navigate to logout (browser POST is a real form/navigation in the app). */
  logout: () => void;
}

export interface UseMeOptions {
  /** Initial entitlement (from server or a mock fixture). */
  initial: MeResponse;
  /**
   * How to perform the re-check. Inject a fake in tests/preview; the real app
   * passes a fetch to POST /api/me/recheck (credentials: "include").
   */
  doRecheck?: () => Promise<MeResponse>;
  /** Login redirect target (default /api/auth/login). */
  loginUrl?: string;
}

/**
 * Auth/entitlement state for the UI (PRD #6, FE auth contract 1.6).
 *
 * Holds the current `MeResponse` and drives the "Saya sudah punya DESK — cek
 * ulang" flow: `recheck()` flips status loading → success/error and swaps in
 * the new entitlement. `doRecheck` is injectable so the preview/tests run with
 * no backend; the real app supplies a fetch to POST /api/me/recheck.
 */
export function useMe({ initial, doRecheck, loginUrl = "/api/auth/login" }: UseMeOptions): UseMe {
  const [me, setMe] = useState<MeResponse>(initial);
  const [recheckStatus, setRecheckStatus] = useState<RecheckStatus>("idle");

  const recheck = useCallback(async () => {
    if (!doRecheck) return;
    setRecheckStatus("loading");
    try {
      const next = await doRecheck();
      setMe(next);
      setRecheckStatus("success");
    } catch {
      setRecheckStatus("error");
    }
  }, [doRecheck]);

  const login = useCallback(() => {
    if (typeof window !== "undefined") window.location.href = loginUrl;
  }, [loginUrl]);

  const logout = useCallback(() => {
    if (typeof window !== "undefined") window.location.href = "/api/auth/logout";
  }, []);

  return { me, recheckStatus, recheck, login, logout };
}
