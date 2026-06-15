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

