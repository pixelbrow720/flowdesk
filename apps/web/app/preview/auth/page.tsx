"use client";

import { useMemo, useState } from "react";
import { ME_FIXTURES, type MeResponse } from "../../../lib/me-mock";
import { useMe } from "../../../lib/use-me";
import { AuthGate } from "../../../components/auth";
import { Topbar } from "../../../components/topbar";
import { ChartLayout } from "../../../components/chart";
import { SegmentedControl } from "../../../components/ui/segmented-control";

type FixtureKey = "anon" | "no_desk" | "not_member" | "desk" | "grace";

const FIXTURES: Record<FixtureKey, MeResponse> = {
  anon: ME_FIXTURES.anon,
  no_desk: ME_FIXTURES.no_desk,
  not_member: { ...ME_FIXTURES.no_desk, is_member: false },
  desk: ME_FIXTURES.desk,
  grace: ME_FIXTURES.grace,
};

const OPTS: { value: FixtureKey; label: string }[] = [
  { value: "anon", label: "ANON" },
  { value: "not_member", label: "NOT MEMBER" },
  { value: "no_desk", label: "NO DESK" },
  { value: "grace", label: "GRACE" },
  { value: "desk", label: "DESK" },
];

/** The dashboard content rendered under the gate (blurred for ANON/NO_DESK). */
function DashboardBody() {
  return (
    <div className="flex h-full flex-col">
      <Topbar />
      <div className="min-h-0 flex-1 p-12">
        <div className="relative h-full overflow-hidden rounded-lg border border-border">
          <ChartLayout />
        </div>
      </div>
    </div>
  );
}

/**
 * Standalone preview for the 4.9 auth UI. The state switcher loads each /api/me
 * fixture; the gate renders ANON (login over blur), NO_DESK / NOT MEMBER (blur +
 * CTAs + cek-ulang), GRACE (full app + banner), and DESK (full app). The cek
 * ulang button resolves to a DESK fixture after a short delay to demo the flow.
 */
export default function AuthPreviewPage() {
  const [fixture, setFixture] = useState<FixtureKey>("anon");

  // Re-create useMe whenever the fixture changes by keying the inner component.
  return (
    <main className="flex h-screen flex-col">
      <div className="flex items-center gap-16 border-b border-border px-12 py-8">
        <span className="font-display text-[10px] uppercase tracking-[0.08em] text-muted">
          /api/me
        </span>
        <SegmentedControl
          ariaLabel="Auth fixture"
          value={fixture}
          onChange={setFixture}
          options={OPTS}
        />
      </div>
      <div className="min-h-0 flex-1">
        <AuthScreen key={fixture} initial={FIXTURES[fixture]} />
      </div>
    </main>
  );
}

function AuthScreen({ initial }: { initial: MeResponse }) {
  // Mock recheck: resolves to DESK after 600ms to demonstrate the flow.
  const doRecheck = useMemo(
    () => () =>
      new Promise<MeResponse>((resolve) =>
        setTimeout(() => resolve(ME_FIXTURES.desk), 600),
      ),
    [],
  );
  const auth = useMe({ initial, doRecheck });
  return (
    <AuthGate auth={auth}>
      <DashboardBody />
    </AuthGate>
  );
}
