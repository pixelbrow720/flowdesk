"use client";

import { useState } from "react";
import { ThemeToggle } from "../../components/theme-toggle";
import {
  Button,
  IconButton,
  SegmentedControl,
  Toggle,
  Pill,
  Tooltip,
  Panel,
  Divider,
  NumberReadout,
  Spinner,
  BlurOverlay,
} from "../../components/ui";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-16">
      <h2 className="font-display text-h2 text-fg">{title}</h2>
      <Panel className="flex flex-wrap items-center gap-16 p-24">{children}</Panel>
    </section>
  );
}

export default function PreviewPage() {
  const [instrument, setInstrument] = useState<"ES" | "NQ">("ES");
  const [toggleA, setToggleA] = useState(true);
  const [toggleB, setToggleB] = useState(false);
  const [showBlur, setShowBlur] = useState(false);

  return (
    <main className="mx-auto flex max-w-[960px] flex-col gap-48 px-24 py-48">
      <header className="flex items-center justify-between">
        <div className="flex flex-col gap-4">
          <h1 className="font-display text-h1 text-fg">
            Flow<span className="text-turquoise">Desk</span> · Primitives
          </h1>
          <p className="font-display text-body text-muted">
            Token-driven component gallery. Toggle the theme to verify both ramps.
          </p>
        </div>
        <ThemeToggle />
      </header>

      <Section title="Button">
        <Button variant="primary">Primary</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="danger">Danger</Button>
        <Button variant="primary" size="sm">
          Small
        </Button>
        <Button variant="primary" disabled>
          Disabled
        </Button>
      </Section>

      <Section title="IconButton">
        <IconButton label="Settings">
          <span aria-hidden className="font-mono text-mono">
            {"⚙"}
          </span>
        </IconButton>
        <IconButton label="Close">
          <span aria-hidden className="font-mono text-mono">
            {"×"}
          </span>
        </IconButton>
      </Section>

      <Section title="SegmentedControl (ES | NQ)">
        <SegmentedControl
          ariaLabel="Instrument"
          value={instrument}
          onChange={setInstrument}
          options={[
            { value: "ES", label: "ES" },
            { value: "NQ", label: "NQ" },
          ]}
        />
        <span className="font-display text-caption text-muted">
          selected: {instrument}
        </span>
      </Section>

      <Section title="Toggle">
        <Toggle checked={toggleA} onChange={setToggleA} label="Smooth render" />
        <Toggle checked={toggleB} onChange={setToggleB} label="Block render" />
        <Toggle checked={false} onChange={() => {}} label="Disabled" disabled />
      </Section>

      <Section title="Pill (regime tones)">
        <Pill tone="neutral">Neutral</Pill>
        <Pill tone="positive" glow>
          Pinning
        </Pill>
        <Pill tone="negative" glow>
          Volatile
        </Pill>
      </Section>

      <Section title="Tooltip">
        <Tooltip content="Net dealer gamma, $ per 1% move" side="top">
          <Button variant="secondary">Hover top</Button>
        </Tooltip>
        <Tooltip content="Right side" side="right">
          <Button variant="secondary">Hover right</Button>
        </Tooltip>
      </Section>

      <Section title="NumberReadout (JetBrains Mono, tabular)">
        <NumberReadout value={5000.25} prefix="$" size="lg" />
        <NumberReadout value={63.5} suffix="%" colorBySign />
        <NumberReadout value={-812_000_000} compact colorBySign size="md" />
        <NumberReadout value={560_000_000} compact colorBySign size="md" />
      </Section>

      <Section title="Spinner">
        <Spinner size="sm" />
        <Spinner size="md" />
      </Section>

      <Section title="Divider">
        <div className="flex w-full flex-col gap-12">
          <span className="font-display text-caption text-muted">above</span>
          <Divider />
          <span className="font-display text-caption text-muted">below</span>
        </div>
      </Section>

      <Section title="BlurOverlay">
        <div className="relative h-[160px] w-full overflow-hidden rounded-lg border border-border">
          <div className="grid h-full grid-cols-8 gap-2 p-8">
            {Array.from({ length: 64 }).map((_, i) => (
              <div
                key={i}
                className={i % 2 === 0 ? "bg-turquoise/30" : "bg-crimson/30"}
              />
            ))}
          </div>
          {showBlur && (
            <BlurOverlay>
              <Panel variant="glass" className="flex flex-col items-center gap-12 p-24">
                <span className="font-display text-body text-fg">
                  Preview is blurred (not hidden)
                </span>
                <Button onClick={() => setShowBlur(false)}>Reveal</Button>
              </Panel>
            </BlurOverlay>
          )}
        </div>
        {!showBlur && (
          <Button variant="secondary" onClick={() => setShowBlur(true)}>
            Show blur overlay
          </Button>
        )}
      </Section>

      <Section title="Panel (surface vs glass)">
        <Panel className="p-24">
          <span className="font-display text-body text-fg">Surface panel</span>
        </Panel>
        <Panel variant="glass" className="p-24">
          <span className="font-display text-body text-fg">Glass panel</span>
        </Panel>
      </Section>
    </main>
  );
}
