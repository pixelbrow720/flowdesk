# Landing Page Research — Multi-Researcher Synthesis

**Date:** 2026-06-15
**Method:** 3 paralel subagent (creative, validation, redteam) ala
quant research workflow. Output mentah disimpan di file ini sebagai
arsip permanen sebelum saya sintesis ke plan eksekusi.

User constraints yang dikunci sebelum riset:
- Audience: serious quant traders (BUKAN retail meme, BUKAN crypto-bro)
- Locked tokens: TURQUOISE/CRIMSON + Space Grotesk/JetBrains Mono
- User EKSPLISIT: "aku gamau ini landing page seperti buatan AI"
- Reference primer dari user: scroll.locomotive.ca, yourbana.com, rig.ai

---

## TL;DR sintesis

1. **Aceternity / Magic UI default = jangan disentuh.** Setiap komponen
   showcase mereka sudah dead inside. Rebuild from scratch atau pakai
   shadcn primitive (Tabs/Dialog/Accordion) saja, restyle total.
2. **Mono-accent > gradient.** Gradient mesh = single biggest "AI
   startup" tell. Hindari TOTAL.
3. **Real data > mockup.** Real symbols (ES/NQ/CL/ZN), real exchange
   names, real pricing visible, real latency stamp. Databento adalah
   teladan terkuat.
4. **Stack: Astro + GSAP (selective) + CSS-native.** Bukan Next.js.
   Bukan Framer Motion (kecuali butuh React DX hard).
5. **Animation = data narrative, BUKAN dekorasi.** Kalau bisa dihapus
   tanpa kehilangan komunikasi → hapus.
6. **Performance budget:** LCP ≤2s, JS ≤100KB gz, CLS ≤0.05, animation
   lib ≤25KB gz. Hero video = HARD AVOID.
7. **rig.ai = benchmark realistis** (B2B SaaS art-directed, mono-accent,
   restraint). locomotive + yourbana = inspirasi prinsip, BUKAN tiru
   langsung (mereka non-SaaS).

## Tiga sumber utama yang harus kita curi disiplinnya

| Site | Apa yang dicuri |
|------|----------------|
| **databento.com** | Show real instruments + exchange names + pricing langsung di hero. "Since 20XX" date marker > "Trusted by X+" vanity. Dashboard ditampilkan in-line as data tables, BUKAN mockup Macbook. |
| **rig.ai** | Manifesto-numbered problem (`001 / 002 / 003 / 004`), mono kicker uppercase, monoaccent restraint, editorial copy yang punya posisi. |
| **linear.app** | Editorial figure-numbered sections (`FIG 0.2`, `EXHIBIT B`), live-mounted product di hero (DOM real, bukan PNG), single-paragraph H1 yang opinionated. |

## Anti-pattern (HARD BAN list)

Dari redteam — 30 tanda landing page "buatan AI". Wajib hindari:

**Visual:**
- Gradient mesh ungu→pink→biru radial blur 200px+
- Glass card `backdrop-blur-xl border-white/10 bg-white/5`
- Aceternity Spotlight / BorderBeam / Meteors / TracingBeam / MacbookScroll / 3DCard / WavyBackground / InfiniteMovingCards
- Magic UI BorderBeam / ShimmerButton / NumberTicker (count-up generic)
- Conic gradient di tombol CTA
- Mockup Macbook 3D tilted dengan dashboard fake
- Floating UI cards di sekitar mockup
- Rainbow gradient text di headline
- Noise/grain overlay tanpa color story

**Typography/copy:**
- Inter atau Geist polos tanpa custom tracking/leading
- Headline pattern "Build [X] faster" / "The [X] platform for [Y]"
- "AI-powered" / "Powered by AI"
- "Simple. Fast. Reliable." three-word manifesto
- "Built for builders/teams/the modern trader"

**Section structure:**
- Urutan kanonik YC: Hero → Logo cloud → Features 3-col → How it works
  3-step → Testimonial 3-col → Pricing Free/Pro/Enterprise → FAQ → CTA
- "Trusted by" logo cloud yang tidak verifiable
- Pricing 3-tier dengan checkmark hijau Lucide
- Testimonial card grid 3-col dengan avatar bulat ⭐⭐⭐⭐⭐
- FAQ accordion shadcn default
- Stat row "10x faster · 99.9% uptime · $0 setup" tanpa source

**Animation:**
- Framer Motion `initial={opacity:0, y:20}` fade-in-up generic
- Marquee logo cloud "Trusted by"
- Cursor glow yang ngikutin mouse di hero
- Sparkles/particles di tombol CTA

**Iconography:**
- Lucide outlined `Zap`/`Shield`/`Sparkles`/`Rocket`/`BarChart3`
- Emoji di CTA: "Get started 🚀" / "Join now ✨"

## Audience-specific kill list (sophisticated trader red flags)

10 hal yang bikin trader serius INSTANT close tab:
1. Animasi dekoratif >10% screen time → "founder design-bro, bukan trader"
2. Mockup dashboard fake dengan candle/angka palsu
3. "AI-powered" / "Powered by GPT" / "AI-driven"
4. Klaim "10x returns" / "Beat the market" tanpa audited track record
5. No mention latency / data source / exchange → vague = belum jadi
6. Pricing langsung di-push sebelum proof
7. Testimonial nama generic ("John D., Day Trader")
8. CTA "Book a demo" tanpa self-serve tier
9. Logo "Trusted by Goldman/JP Morgan" tanpa case study
10. Discord/Telegram "VIP signals" framing
11. Hero copy "Trade smarter not harder" / "Make money while you sleep"
12. Countdown timer di pricing → infomercial energy
13. No documentation / API reference visible
14. No risk disclaimer untuk produk trading
15. Founder background absent → trader googles founder dulu

## Validated technical decisions

Dari validation researcher — yang terbukti vs tidak:

| Klaim | Verdict | Implikasi |
|-------|---------|-----------|
| Astro > Next.js untuk landing static | **CONFIRMED** (40% faster, 90% less JS) | Pakai Astro |
| Hero video bg menurunkan LCP | **CONFIRMED** (5MB → 5-6s LCP > 2.5s threshold) | Hard avoid hero video |
| GSAP < Framer Motion bundle size | **FALSE** (27KB vs 30KB, comparable) | Pilih by use case bukan reputation |
| Smooth scroll (Lenis) = premium | **PARTIAL** (a11y cost, wajib `prefers-reduced-motion` bail) | Pakai dengan damping konservatif, OR skip |
| Custom cursor = craft signal | **PARTIAL → leans negative untuk B2B** | Skip total |
| shadcn customized bisa tidak generic | **PARTIAL** (~70-80% kalau customize ≥5 dimensi) | OK pakai primitive saja, restyle total |
| Show pricing > Contact Sales (B2B SMB) | **CONFIRMED** | Show pricing publik |
| Animated data-viz hero efektif fintech | **PARTIAL** (anecdotal, butuh = produk itself) | OK kalau viz = real data |
| Audience quant anti animasi flashy | **UNVERIFIED tapi strong inference** | Default minimalist |
| Animation scroll-driven naikkan engagement | **UNVERIFIED** (no controlled study) | Pakai minimal, justifikasi data-narrative |

## Performance budget final

| Metric | Target | Hard ceiling |
|--------|--------|--------------|
| LCP | ≤ 2.0s | ≤ 2.5s |
| CLS | ≤ 0.05 | ≤ 0.1 |
| INP | ≤ 150ms | ≤ 200ms |
| Total JS (gzip) | ≤ 100KB | ≤ 170KB |
| Total CSS (gzip) | ≤ 30KB | ≤ 50KB |
| Hero LCP element | ≤ 100KB AVIF/WebP | ≤ 200KB |
| Hero video | **HARD AVOID** | n/a |
| Animation lib | ≤ 25KB gz | ≤ 40KB gz |
| Font total | 2 weights subset, ≤ 40KB woff2 | n/a |

## Tech stack final

- **Framework:** **Astro** + selective React/Svelte islands (untuk live
  tape + DOM ladder demo). Static-first. Zero JS by default.
- **Animation:** **GSAP** (ScrollTrigger + SplitText) untuk timeline
  scrubbing + scroll-pin. **CSS-native** untuk marquee/hover/simple
  reveal. **No Framer Motion** (React-only, bundle comparable, DX win
  tidak relevan kalau pakai Astro).
- **Smooth scroll:** **Lenis** dengan `lerp: 0.08`, **WAJIB** disable on
  `prefers-reduced-motion` + on touch devices. ATAU skip total dan
  pakai native scroll (saya lean ke skip).
- **Component base:** Custom from scratch. Pinjam shadcn/Radix primitive
  untuk Tabs/Dialog/Accordion (saving a11y week of work), restyle
  total — hairline border, 90° corner, mono labels.
- **Icon:** **Hugeicons** (user kasih reference) atau **custom SVG
  set** untuk top-level. Lucide BANNED.
- **Font:** **Space Grotesk** (display, locked) + **JetBrains Mono**
  (numeric, locked). Self-hosted woff2, 2 weights each, subset Latin.
  `font-display: swap`, preload critical weight.

## Tiga lapis riset (raw output disimpan terpisah)

- `landing-page-research-redteam.md` — galak, 30 anti-pattern, audit
  brutal kompetitor, litmus test
- `landing-page-research-creative.md` — 5 site teardown, 12 hero ideas,
  10 pattern catalog, animation palette, 5 unhinged ideas
- `landing-page-research-validation.md` — 10 klaim verified, library
  reality check, performance budget, mitos yang ternyata FALSE

(File raw akan saya tulis terpisah supaya bisa di-rujuk individual.)
