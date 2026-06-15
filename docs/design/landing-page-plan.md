# FlowDesk Landing Page — Build Plan

**Date:** 2026-06-15
**Status:** Plan v1, awaiting user approval before build
**Audience:** Serious quant traders (NOT retail, NOT crypto)
**Honesty stance:** Beta historical mode, lensa eksperimental NOT-VALIDATED — wajib di-surface.

---

## 1. Design Principles (locked sebelum build)

1. **Real data, never mockup.** Hero menampilkan symbol nyata (ES/NQ),
   exchange nyata (CME-GLOBEX), latency nyata, build hash nyata.
   Mockup Macbook + dashboard fake = banned.
2. **Mono-accent discipline.** Black background + 1 accent (TURQUOISE
   atau CRIMSON, pilih satu sebagai dominan). Gradient mesh banned.
3. **Animation = data narrative.** Setiap motion harus komunikasi data.
   Kalau bisa dihapus tanpa kehilangan info → hapus.
4. **Editorial gravitas, bukan SaaS marketing.** Section labeled
   `EXHIBIT A` / `FIG 0.2` / `§3` — bukan "Features" / "How it works".
5. **Honesty surface.** Beta status, historical mode, lensa NOT-VALIDATED
   harus visible — jangan over-promise. Trader serius cek ini.
6. **Performance is brand.** LCP ≤2s. Lambat = "founder bukan trader".
7. **Operator console aesthetic.** Hairline 1px border, 90° corner,
   tabular nums untuk semua angka. Bukan rounded-2xl SaaS.

## 2. Information Architecture (section-by-section)

Urutan **bukan** YC-canonical. Disisipkan case-study + changelog di
tengah supaya tidak terbaca template.

```
01. HERO — Live tape + opinionated H1 + latency stamp
02. MANIFESTO — 4 numbered problem (001-004) ala rig.ai
03. EXHIBIT A — DOM/GEX panel live (real data, historical replay)
04. CASE STUDY — 1 specific session timeline (e.g., FOMC day replay)
05. EXHIBIT B — 0DTE GEX/DEX engine spec sheet (numbered features)
06. HONESTY SECTION — what FlowDesk IS NOT (beta scope, NOT-VALIDATED tags)
07. PRICING — transparent, single tier paid beta
08. FOUNDER NOTE — short, signed, posisi jelas
09. FOOTER — changelog, build hash, contact
```

**Yang dihindari eksplisit:**
- "Trusted by" logo cloud (FlowDesk belum punya — jangan fake)
- Testimonial 3-col grid (belum punya user → jangan karang)
- FAQ accordion generic
- "How it works" 3-step icon row

## 3. Hero Composition (chosen + 2 backup)

**PILIHAN UTAMA — "Live Tape, Single Headline"** (risk: low)

```
┌─────────────────────────────────────────────────────────┐
│ FLOWDESK®  v0.4.1 · CME-GLOBEX · BETA                   │  <- mono pill
│─────────────────────────────────────────────────────────│
│ ES 5874.25 ▲0.18  NQ 20412.5 ▼0.04  ...                 │  <- live tape (replay)
│─────────────────────────────────────────────────────────│
│                                                         │
│   0DTE gamma & dealer                                   │
│   exposure for /ES & /NQ.                               │  <- H1 grotesk display
│                                                         │
│   Beta. Historical replay only.                         │  <- honesty subline
│   No live arming until hardened.                        │
│                                                         │
│   [ Get beta access ]   [ Read the docs ]               │  <- CTA pair
│                                                         │
│                          MEDIAN SNAPSHOT  18ms          │  <- right-aligned stamp
│                          ENGINE TESTS     415 ✓         │
└─────────────────────────────────────────────────────────┘
```

**Why fits:**
- Real symbols dari awal → langsung legitimacy
- Honesty subline ("Beta. Historical replay only.") = trader respect
- Latency stamp + test count = developer/quant authority
- Zero Aceternity, zero glass card, zero gradient mesh

**Backup 1 — "Manifesto Stack"** (rig.ai-derived, risk: med)
4 numbered problem statements full-bleed, no image, CTA bawah.
Cocok kalau user mau push thesis dulu sebelum show product.

**Backup 2 — "Latency-as-Headline"** (risk: med)
Giant numeral `18ms` clamp(18vw), caption `median snapshot · n=...`.
Worth it kalau angka kompetitif vs vendor lain.

## 4. Animation Budget (concrete, ≤25KB GSAP gz)

| # | Where | What | Lib | Cost |
|---|-------|------|-----|------|
| 1 | Hero tape | CSS marquee 60s linear infinite, pause-on-hover | CSS | 0 KB |
| 2 | Hero H1 | GSAP SplitText reveal, stagger 40ms, 600ms total, fire ONCE | GSAP | shared |
| 3 | Stat strip | GSAP count-up on IntersectionObserver, tabular nums, fire ONCE | GSAP | shared |
| 4 | Case study | ScrollTrigger pinned 600vh, 4 frames cross-fade by progress | GSAP | shared |
| 5 | DOM panel | Background flash 120ms on row update (matches Bloomberg) | CSS | 0 KB |
| 6 | Latency chart | SVG stroke-dashoffset draw 1.6s on enter, ONCE | CSS | 0 KB |
| 7 | Pricing card | scale 1→1.012 on focus, sibling desaturate | CSS | 0 KB |
| 8 | Footer wordmark | Slow fade-in 1.2s on scroll-into-view | CSS | 0 KB |

**Total animation lib: ~27 KB GSAP + ScrollTrigger + SplitText gz.**
**Lenis: SKIP.** Native scroll. Trader scroll cepat — Lenis bikin
frustrasi + a11y cost. Decision locked.

## 5. Tech Stack

```
Framework:    Astro 4.x (static-first, islands for live tape)
Animation:    GSAP (ScrollTrigger + SplitText) only
Style:        Tailwind v4 + custom CSS tokens (NO shadcn defaults)
Primitive:    Radix UI (Tabs/Dialog) restyled total
Icons:        Custom SVG set (no Lucide)
Font:         Space Grotesk + JetBrains Mono, self-hosted woff2,
              subset Latin, 2 weights each, font-display: swap
Deploy:       Vercel atau Cloudflare Pages (static)
```

## 6. Performance Budget (gates — fail → block ship)

| Metric | Target | Hard ceiling |
|--------|--------|--------------|
| LCP | ≤ 2.0s | ≤ 2.5s |
| CLS | ≤ 0.05 | ≤ 0.1 |
| INP | ≤ 150ms | ≤ 200ms |
| Total JS gz | ≤ 100KB | ≤ 170KB |
| Total CSS gz | ≤ 30KB | ≤ 50KB |
| Hero LCP element | ≤ 100KB AVIF | ≤ 200KB |
| Hero video | **HARD AVOID** | n/a |

## 7. Acceptance Criteria (saya akan self-audit pakai ini)

**Litmus AI-generated test (≥3 Y = redesign):**
1. [ ] Gradient mesh ungu/pink/biru di hero?
2. [ ] Glass card backdrop-blur sebagai feature card?
3. [ ] Headline punya "Build", "faster", "AI-powered", "The future of"?
4. [ ] Font pairing Inter/Geist polos tanpa custom tracking?
5. [ ] Macbook mockup atau floating UI cards di hero?
6. [ ] Lucide outline icon di feature card tanpa custom treatment?
7. [ ] Pricing 3-tier Free/Pro/Enterprise checkmark hijau?
8. [ ] Testimonial 3-col avatar bulat ⭐⭐⭐⭐⭐?
9. [ ] "Trusted by" logo cloud unverifiable?
10. [ ] Animasi entry `opacity 0→1, y 20→0` di setiap section?
11. [ ] Aceternity Spotlight/BorderBeam/Meteors anywhere?
12. [ ] Copy bisa find/replace "FlowDesk"→"Notion AI" tetap masuk akal?
13. [ ] Dashboard yang ditampilkan = mockup, bukan recorded session?
14. [ ] Stat row tanpa source/footnote?
15. [ ] Struktur Hero→Logo→Feature→Testi→Pricing→FAQ→CTA lurus?

**Trader trust test:**
- [ ] Real symbol & exchange visible di hero?
- [ ] Latency angka ada (atau jujur "TBD historical mode")?
- [ ] Beta status + NOT-VALIDATED tag visible?
- [ ] No "AI-powered" / "10x returns" / "VIP signals"?
- [ ] Founder note signed, posisi jelas?
- [ ] Pricing transparan?
- [ ] Changelog / build hash di footer?

## 8. Build Sequence (estimasi)

1. **Setup Astro + Tailwind + GSAP + font self-host** — 2-3h
2. **Design tokens** (color/spacing/typography scale) + global CSS — 2h
3. **Hero section** (tape + H1 + CTA + stamp) — 4-6h
4. **Manifesto + Exhibit A/B sections** — 6-8h
5. **Case study scroll-pinned animation** — 4h
6. **Honesty section + Pricing + Founder note + Footer** — 4h
7. **Performance pass** (Lighthouse → fix) — 2-3h
8. **Litmus self-audit + iterate** — 2h

**Total: ~26-32h focused work.** Bisa dipecah 3-4 session.

## 9. Open Questions (jawab sebelum build)

1. **Single accent: TURQUOISE atau CRIMSON dominan?**
   Saya lean **CRIMSON** untuk hero accent (urgency/execution),
   TURQUOISE untuk data positive (▲ green proxy).
2. **Pricing visible atau gated?** Saya lean **visible** (databento
   pattern).
3. **Founder photo + nama nyata di Founder Note?** Trader googles —
   pakai nama asli kalau OK.
4. **Domain landing terpisah** (flowdesk.io) atau **subpath** dari app?
5. **Beta access form**: email-only atau dengan screening question
   (e.g., "broker prop apa?").

## 10. Round-2 polish (2026-06-15)

Visual feedback round on top of the round-1 brick-aura build. Driven by user
screenshots and 7 concrete demands.

### 10.1 Decisions

- **BG hitam pekat.** `ink-0` was `#0A0A0B` (slightly grey), reset to pure
  `#000000`. `themeColor` and the body BG follow.
- **Cursor smoke (brick).** New `<CursorTrigger />` mounted in the root layout.
  A fixed full-viewport div carries a radial brick gradient anchored to
  `--cx/--cy`, blended via `mix-blend-mode: screen`, fading in/out via `--cv`
  on `mousemove`. Disabled on coarse pointers and `prefers-reduced-motion`.
- **Static aura brick removed.** Every section that previously painted a fixed
  brick blob behind the headline lost it. Ambient brick now comes from the
  cursor trigger only — the page is calm at rest, brick wakes on interaction.
- **Headline2 white, not brick.** Both display lines are `text-bone-0`. The
  brick reveal is delivered by the cursor trigger passing across them, not by
  static color.
- **Hover aura per card / row.** A reusable `<HoverAura />` atom lives inside a
  `group`, absolutely positioned with `-z-10`, `origin-left`, and a 600ms
  transform+opacity transition.
  - **`stay` variant** — grows on hover and holds. Used on Problem/System/
    Lenses/Flow cards (the "settles, not just passes through" ask).
  - **`sweep` variant** — runs the `aura-sweep` keyframe (defined in
    `globals.css`) once per hover, travelling left → through → off-right and
    fading. Used on Honest table rows, where a persistent fill would drown the
    rest of the table.
- **Typography descender clearance.** Display headlines move from
  `leading-[0.82..0.86]` to `leading-[0.92]` (Hero) / `leading-[0.96]`
  (sections). This kills the `p`/`y`/`h` collisions across `options charts` and
  `yesterday's news`.
- **Lenses spacing tightened.** Card width `min(720px, 78vw)`, gap `2vw`. Track
  width and translate are recomputed from `n_cards × (card + gap) + 2 × side
  padding` so the last card lands flush right.

### 10.2 Copy de-leak (proprietary protection)

The previous copy named exact internals — competitors could rebuild the
pipeline from the marketing page alone. The pass strips that down to
**outcome language**, keeping conventions and instrument names intact but
removing constants, vendor names, schema versions, internal keys, and
algorithm specifics.

| Removed (leaked) | Replacement (clean) |
|---|---|
| `Black-76 on the future · r = ln(1 + SOFR)` | `Futures-correct math · standard risk-free curve` |
| `Newton → bisection · tol 1e-6` | `Two-stage convergence to floating-point tolerance` |
| `+1 call · −1 put · hardcoded` | `Industry convention, locked at codepath` |
| `VOL · cumulative since RTH open` | `Volume-weighted · cumulative since RTH open` |
| `gamma-dollar Top-3 · static for session` | `Top dealer-gamma levels · fixed at session open` |
| `HIRO_t = Σ s·δ·q·M·F. Aggressor side from CME trades.side (B=+1, A=−1, N=0)` | `Aggressor-signed flow accumulated since the RTH open` |
| `Raw-SVI surface fit per expiry (deterministic Nelder-Mead)` | `Per-expiry vol surface, deterministic` |
| `Databento` (named in flow + node detail) | `Licensed CME feed` |
| `GLBX.MDP3 · trades · bbo-1m` | `Licensed CME feed · chain + trades` |
| `schema_version=2 · pydantic ↔ zod byte-for-byte` | `Schema-locked · typed end-to-end` |
| `flowdesk:now · flowdesk:updates` (Redis keys) | `In-memory · sub-second fanout` |
| `snapshots hypertable · replay` | `Scrubbable past sessions` |
| `(M=$50, step=5)` / `(M=$20, step=10)` | `CME /ES and /NQ · standard contract specs` |

What stays on the page (these are not leaks):
- `/ES`, `/NQ`, `0DTE`, `RTH`, `GEX`, `DEX`, `IV`, `vanna`, `charm`,
  `gamma walls`, `regime flip`, `ATM`, `expected move`, `skew`.
- Engine names `FOG`, `FLUX`, `ARC` and the lens labels `Profile`, `Walls`,
  `Regime`, `Replay`.
- The `EXPERIMENTAL` flag pattern, advertised on purpose.
- Cadence claim `one read per minute`, audit claim `worker ↔ generator
  bit-equal` (stated as "identical bytes / receipts you can audit").

The same de-leak hits `<head>` — `metadata.description` no longer mentions
Black-76, Snapshot, FOG/FLUX/ARC. Open Graph and Twitter cards are unchanged
because they were already in outcome-language.

### 10.3 Files touched

```
apps/landing/tailwind.config.ts                         ink-0 #0A0A0B → #000
apps/landing/src/app/layout.tsx                         themeColor + meta de-leak + CursorTrigger mount
apps/landing/src/app/globals.css                        @keyframes aura-sweep + .anim-aura-sweep
apps/landing/src/components/atoms/cursor-trigger.tsx    NEW — viewport brick smoke
apps/landing/src/components/atoms/hover-aura.tsx        NEW — group-hover aura (stay | sweep)
apps/landing/src/components/sections/hero.tsx           leading 0.92, headline2 white, aura removed
apps/landing/src/components/sections/problem.tsx        leading 0.96, headline2 white, HoverAura(stay) ×3
apps/landing/src/components/sections/system.tsx         leading 0.96, headline2 white, HoverAura(stay) ×3
apps/landing/src/components/sections/lenses.tsx         spacing tight, headline2 white, HoverAura per card
apps/landing/src/components/sections/flow.tsx           leading 0.96, headline2 white, HoverAura per node
apps/landing/src/components/sections/honest.tsx         leading 0.96, headline2 white, HoverAura(sweep) per row
apps/landing/src/components/sections/access.tsx         leading 0.96, headline2 white, HoverAura(sweep) per bullet
apps/landing/src/lib/copy.ts                            de-leak rewrite (full table above)
```

### 10.4 Verification

- Dev server: `next dev -p 4321`, HTTP 200, ~95 KB SSR HTML.
- Leak grep on rendered HTML for `Black-76 / Databento / GLBX / Newton / SVI /
  tol 1e- / schema_version / Redis / Timescale / HIRO_t / SOFR` — all 0.
- All seven section anchors (`top problem system lenses flow honest access`)
  present in DOM.
- `CursorTrigger` SSR-renders the radial-gradient div with brick stops.
- HoverAura spans render with `origin-left scale-x-0 ... group-hover:scale-x-100`
  on every targeted card.

### 10.5 What was deliberately NOT changed

- Page order, single Discord CTA, nav, footer.
- Existing entrance fade+slide animations on headlines (framer-motion).
- Backend / engine / contracts. This is landing-only.
- The `lenis-provider`, `magnetic`, and `globals.css` reset (only the
  `aura-sweep` keyframe block was added).
- Color tokens beyond `ink-0`: `brick`, `bone-*`, `ink-1..3` are unchanged.

