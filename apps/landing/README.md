# @flowdesk/landing

FlowDesk public landing page — Astro 4 + GSAP, static output.

## Stack

- Astro 4.16 (static, no SPA runtime)
- GSAP 3.12 + ScrollTrigger (~27KB gz, lazy-loaded, skipped on `prefers-reduced-motion`)
- Native CSS with design tokens (`src/styles/tokens.css`); zero Tailwind, zero shadcn/Aceternity defaults
- Space Grotesk (display) + JetBrains Mono (numeric/UI labels)

## Structure

```
apps/landing/
├── astro.config.mjs            # static + lightningcss
├── tsconfig.json               # strict, with @-aliases
├── package.json
├── public/
│   └── favicon.svg
└── src/
    ├── styles/tokens.css       # locked palette + type scale
    ├── lib/data.ts             # exhibit data sourced from golden snapshot
    ├── layouts/Base.astro
    ├── components/
    │   ├── Hero.astro          # live tape + H1 + honesty subline
    │   ├── Manifesto.astro     # 001-004 numbered problem statements
    │   ├── Lenses.astro        # 7 lens cards, NOT-VALIDATED tagged
    │   ├── Exhibit.astro       # frozen 8-minute golden trace
    │   ├── Honesty.astro       # claim/status/note ledger
    │   ├── Performance.astro   # LCP/CLS/INP/JS budgets
    │   ├── Founder.astro       # operator note
    │   ├── Pricing.astro       # single tier, visible
    │   ├── Access.astro        # beta form, 1 screening question
    │   └── Footer.astro
    └── pages/index.astro
```

## Develop

```bash
cd apps/landing
npm install
npm run dev          # http://localhost:4321
```

## Build

```bash
npm run build        # astro check + astro build → dist/
npm run preview      # serve dist/
```

## Performance gates (locked)

| Metric | Target  |
|--------|---------|
| LCP    | ≤ 2.0s  |
| CLS    | ≤ 0.05  |
| INP    | ≤ 150ms |
| JS     | ≤ 100KB gz |

## Honesty rules (locked)

- Numbers on this page are sourced from `services/engine/tests/golden/snapshot.golden.json` (schema_version 2). No fabricated mock data.
- Three lenses (`SYNTHETIC_OI`, `EXPOSURE_EXT`, `SURFACE`) are surfaced with explicit `NOT-VALIDATED` tags both on landing AND in product.
- `schema_version` is part of the visible product surface — bumps are explicit (currently `2`).

## References

- Plan: `docs/design/landing-page-plan.md`
- Research synthesis: `docs/design/landing-page-research.md`
- Locked contract: `docs/02-locked-contract.md`
