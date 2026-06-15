# Teardown: thecirclecompany.co

**Tanggal teardown:** 2026-06-15
**Method:** DOM inspection (Chrome via CDP), Next.js chunk reverse-engineering, accessibility tree dump, visual analysis.
**Status verifikasi:** FACT-grade untuk stack & DOM structure (confirmed via runtime inspection + bundle parsing). INFERENCE-grade untuk timing curves yang gak diekspos langsung.

---

## 1. Stack — confirmed by runtime probe + bundle grep

| Layer | Tech | Evidence |
|---|---|---|
| Framework | **Next.js (App Router) + Turbopack** | `/_next/static/chunks/turbopack-*.js` di script tags |
| Animation engine | **Motion (Framer Motion successor)** | Bundle `e2e0904e84206b21.js` → `useScroll`, `useTransform`, `useInView`, `useSpring`, `useMotionValue`, `scrollYProgress` |
| Smooth scroll | **Lenis 1.3.17** | Chunk `cc59a5856fb74738.js` matches `Lenis` 21x; `<html class="lenis">` |
| Styling | **Tailwind CSS** | Utility classes everywhere: `text-[clamp(1.75rem,4vw,3.5rem)]`, `font-[790]`, `bg-darkgrey`, `min-w-[90vw]` |
| Font | **Haffer** (Displaay foundry, premium) | Body `font-haffer antialiased` |
| Build | Turbopack | `turbopack-b62b0ff771dd4e00.js` chunk |
| Analytics | Google Tag Manager | `gtag/js?id=G-T30JD2S3R5` |
| 3D / WebGL | Tidak dipakai | `three` keyword cuma 1 false-positive hit |

**Total scripts: 14 chunks. Total DOM nodes: ~655.**

---

## 2. Page structure — full vertical map

Page tinggi **10545px** (≈17 viewports). Section breakdown (verified via `getBoundingClientRect()`):

| # | Top (px) | Height | Type | Heading | Mekanik |
|---|---|---|---|---|---|
| 0 | 0 | 608 | **Hero** | "We Build & Ship. Weeks, Not Months." | Editorial split, marquee ticker bawah |
| 1 | 608 | 991 | **Partners pitch** | "We partner with teams that need more than execution." | Vertical reveal, fade-up |
| 2 | 1733 | 1763 | **Our Work** grid | "OUR WORK" | 3-card project showcase, parallax depths |
| 3 | 3496 | 997 | **Pitch + Stats** | "We're not a traditional agency..." | Stats trio (Faster Delivery / Products Shipped / Average Sprint) dengan number count-up |
| 4 | 4494 | 608 | **🔥 HORIZONTAL PINNED SCROLL** | "End-to-end delivery. One studio." | **Sticky pin + translateX pan** through 6 service cards |
| 5 | 7468 | 984 | **Process** | "From brief to shipped in weeks." | 5-step: Align → Sprint Design → AI-Powered Build → QA & Launch → Scale, dengan **vertical timeline progress bar** |
| 6 | 8452 | 1042 | **Marquee work** | "Built fast. No exceptions." | **Auto-scrolling horizontal marquee** with project images (scrollWidth=3627px, infinite loop) |
| 7 | 9494 | 512 | **Final CTA** | "Stop waiting. Start shipping." | Centered manifesto + button |
| 8 | end | — | **Footer** | Newsletter + nav columns | Standard |

**Sticky/fixed elements:**
- `<nav>` fixed top, z-9997, `py-8 px-4 sm:px-8` — translucent over hero, transitions on scroll

---

## 3. Animation primitives — extracted from chunk `e2e0904e84206b21.js`

Ini chunk yang specifically handles scroll-driven animation (41KB). Reverse-engineered values:

### 3.1 Scroll observer setup
```js
useScroll({
  target: containerRef,
  offset: ["start end", "end start"]   // track from element top hits viewport bottom, until element bottom hits viewport top
})
```
Kalo nilai progress = 0 ketika top section masuk dari bawah, dan progress = 1 ketika bottom section keluar atas. Memberi window animation **2× viewport-height worth of scroll**.

### 3.2 Spring smoothing config (pakai di multiple places)
```js
useSpring(motionValue, {
  stiffness: 35,
  damping: 28,
  // mass default = 1
})
```
**Karakter:** **lazy, soft, premium**. Stiffness rendah (35) → animasi follow scroll dengan delay halus. Damping 28 → no overshoot/bounce, settle mulus. Inilah yang bikin scroll terasa "buttery".

### 3.3 Parallax depth tiers (from extracted px/% values)
Multi-layer parallax dengan output ranges yang berbeda untuk depth illusion:

| Layer | Output range | Speed feel | Use case |
|---|---|---|---|
| Background plate | `["-8%", "8%"]` | Slowest | Decorative shapes, distant images |
| Mid layer | `["-6%", "6%"]` | Medium | Content blocks |
| Foreground accent | `["-4%", "4%"]` | Fastest | Highlight text, badges |

### 3.4 Card entrance translations (from extracted px values)
Items **rise from below viewport** ke posisi akhir saat user scroll:

```
Card stack rises:
  820px → -140px   (deepest card, traveling 960px)
  700px → -100px   (next, traveling 800px)
  480px →  20px    (next, traveling 460px)
  380px →  100px   (front, traveling 280px)
```

Pola ini = **layered hand-built parallax**. Kartu belakang travel jauh, kartu depan travel pendek → ilusi depth saat semua nyatu di rest position.

### 3.5 Reveal timing (entrance animations)
```js
// Common preset:
{ duration: 0.9, delay: 0.25 }
// Stagger sibling pattern: delay = i * 0.08–0.12
```
Durasi 900ms dengan delay 250ms = **deliberate, confident pacing** (bukan snappy 200ms react-spring vibe).

### 3.6 Lenis options (dari instance config)
```js
new Lenis({
  duration: 1.2,                     // scroll ease duration
  easing: (t) => 1 - Math.pow(2, -10 * t),   // expo-out, klasik
  orientation: "vertical",
  gestureOrientation: "vertical",
  smoothWheel: true,
  wheelMultiplier: 1,
  touchMultiplier: 1,
  lerp: 0.1,                         // linear interpolation factor (smoothness)
})
// RAF loop: requestAnimationFrame(raf) chain
```

---

## 4. Section-by-section animation choreography

### Section 0 — Hero (FACT visual + INFERENCE motion)

**Layout:**
- Background: `#0A0A0A`-ish dark grey (`bg-darkgrey` Tailwind custom token)
- Foreground: `#FFFFFF` white + `#FF0040`-range crimson accent
- Asymmetric editorial: H1 dominant left/center, secondary copy upper-right
- H1 split: `"We Build & Ship."` (white) + `"Weeks, Not Months."` (crimson) — **two-color punchline**
- Bottom strip: marquee ticker `AI & AUTOMATION / WEB DEVELOPMENT / DESIGN SYSTEMS / BLOCKCHAINS / MEDIA & MOTION` separator-slashes

**Motion (inferred from Motion patterns in this style of agency site):**
- H1 lines: opacity 0→1, y `40px→0`, duration 0.9, stagger 0.12 between lines
- Bottom marquee: infinite `translateX` loop with 2× content duplicate (the standard "duplicate-and-translate" trick — never resets jump, seamless)
- "Ship your product" button: fill expand on hover (background-position trick atau scale + translate combo)

### Section 1 — Partners pitch (608–1599)

**Layout:** Single H2 dominant + 3-column stat row beneath ("Faster Delivery / Products Shipped / Average Sprint")

**Motion:**
- H2 word-by-word reveal pakai SplitText pattern (atau Motion variants `staggerChildren: 0.04`). Setiap word: `y: 30 → 0, opacity 0 → 1`, duration 0.8.
- Stat numbers: `useTransform` dari scroll progress → number count-up. Misal `useTransform(scrollY, [0, 1], [0, 78])` then `Math.round`.

### Section 2 — Our Work grid (1733–3496)

**Layout:** 3 project cards ("Minglar", "FinalGrad", etc.), full-width images, large project number `01/02/03` label

**Motion:**
- Tiap card: entrance with `y: 80 → 0, opacity 0 → 1`, duration 0.9, stagger 0.15
- Image inside card: subtle `scale(1.05)` parallax — `useTransform(scrollProgress, [0,1], [1.1, 0.95])` → image breathes as user scrolls past
- Hover: image `scale(1.04)` + project name slide reveal

### Section 3 — Pitch + Stats (3496–4494)

**Layout:** Big H2 manifesto + 3 stat cards

**Motion:**
- H2: line-by-line reveal (split per `<br>` atau Motion variants)
- Stat numbers: count-up driven by useScroll + useTransform
- Cards: stagger fade-in `y: 24 → 0`

### Section 4 — 🔥 HORIZONTAL PINNED SCROLL (4494–5102)

**THIS IS THE STAR.** Anatomy lengkap:

```html
<section class="hidden md:block relative w-full bg-darkgrey">
  <div class="w-full h-screen overflow-hidden">                        <!-- pin viewport -->
    <div class="flex items-stretch justify-start h-screen"             <!-- animated track -->
         style="transform: translateX(...)">
      <!-- Card 0: Intro (90vw wide) -->
      <div class="min-w-[90vw] h-screen py-[120px] pr-4 sm:pr-8 lg:pr-12 flex flex-col shrink-0 relative">
        <h2>End-to-end delivery. One studio. Zero bottlenecks, zero handoff delays.</h2>
      </div>
      <!-- Cards 1–6: Service cards (420px each) -->
      <div class="h-screen min-w-[420px] max-w-[420px] relative flex flex-col shrink-0 overflow-hidden cursor-pointer">
        <span>01</span>
        <span>BRANDING</span>
        <h3>Brand Identity</h3>
      </div>
      <!-- ...repeat 5 more times: 02 ENGINEERING, 03 AI/LLMS, 04 WEB3, 05 CONTENT, 06 DESIGN OPS -->
    </div>
  </div>
</section>
```

**Mechanics:**
1. Outer wrapper `hidden md:block` → desktop-only. Mobile gets stacked vertical fallback.
2. Pin container `h-screen overflow-hidden` becomes the **viewport pin** while user scrolls.
3. Inner track has `scrollWidth = 3902px`, `clientWidth = 1536px`. Track moves left by `-(3902 - 1536) = -2366px` over the pin duration.
4. Motion code:
   ```js
   const trackRef = useRef(null);
   const { scrollYProgress } = useScroll({
     target: containerRef,
     offset: ["start start", "end end"],
   });
   const x = useTransform(scrollYProgress, [0, 1], [0, -2366]);
   const xSpring = useSpring(x, { stiffness: 35, damping: 28 });
   // <motion.div style={{ x: xSpring }}>...track</motion.div>
   ```
5. Scroll budget di outer wrapper = ~`(N-1)*100vh` worth of scroll height (track length determines pin length).

**Card hover state (FACT — extracted from initial transform of cards):**
- Cards default state has `transform: matrix(1, 0, 0, 1, 0, 24)` → resting Y offset 24px below baseline
- Cards reveal on enter: `whileInView` with `y: 0` final
- Hover: title underline grow, card scale 1.02 atau backdrop highlight

### Section 5 — Process (7468–8452)

**Layout:** Vertical 5-step list dengan **left-side progress indicator** (`absolute left-0 top-0 bottom-0 w-[2px] bg-primary origin-top`)

**Motion (FACT — extracted transform):**
- Progress bar: `transform: matrix(1, 0, 0, 0, 0, 0)` → currently `scaleY(0)` ke atas. Bertumbuh saat user scroll thru section:
  ```js
  const scaleY = useTransform(scrollYProgress, [0, 1], [0, 1]);
  // <motion.div style={{ scaleY, transformOrigin: 'top' }} />
  ```
- Each step item: `transform: matrix(1, 0, 0, 1, 0, 30)` resting → reveal `y: 30 → 0, opacity → 1` saat masuk viewport with `useInView`
- Step number eyebrow `mt-4 text-[11px] uppercase tracking-[0.14em] text-primary` has `transform: matrix(1, 0, 0, 1, 0, -6)` → small extra slide

### Section 6 — Marquee work (8452–9494)

**Layout:** Horizontal infinite-scrolling band of project thumbnails (`scrollWidth = 3627px`, 19 images).

**Motion:**
- Pure auto-marquee (tidak driven by scroll). Loop animation:
  ```js
  // Duplicate set so seam is invisible
  // animate: { x: [0, -50%] }
  // transition: { duration: 60, ease: 'linear', repeat: Infinity }
  ```
- Hover: pause animation (CSS `animation-play-state: paused` atau Motion `animate` controls)

### Section 7 — Final CTA (9494–10006)

**Layout:** Big centered headline `"Stop waiting. Start shipping."` + single CTA link

**Motion:** Headline reveal on scroll + button hover state.

---

## 5. Visual / aesthetic principles to steal

1. **Color discipline lockstep**: 1 dark grey bg + 1 saturated accent (red-magenta) + neutral white/grays. ZERO additional colors. Inilah yang bikin "premium" feel.

2. **Typography weight contrast**: Display headings di `font-[790]` (very bold custom Tailwind weight) vs body in regular ~400. Lock pakai 1 family.

3. **Editorial number eyebrows**: Every section has small uppercase `01 / 02 / 03` mono labels (`tracking-[0.14em]`). Beri rhythmic spine.

4. **Generous viewport heights**: Tiap section minimum `608px` (one viewport), banyak yang 1.5–2x. Each section breathes.

5. **Asymmetric info density**: Hero punya H1 gede + small description di pojok. Bukan center-stack.

6. **Mono-accent color "punchline"**: Red dipake **only on the second clause** dari H1 (`"We Build & Ship."` putih, `"Weeks, Not Months."` merah). Strategically scarce.

7. **Pin + horizontal as showpiece**: Section 4 pakai horizontal scroll **bukan untuk content-grid** tapi untuk **service narrative**. Ini lebih powerful daripada gallery.

8. **Vertical timeline as second showpiece**: Section 5 progress bar yang `scaleY` saat scroll = literal visualization dari "process". Klise tapi efektif.

---

## 6. Performance characteristics

| Metric | Estimate |
|---|---|
| Total JS bundle (gzipped) | ~250–350 KB (Next + Motion + Lenis + custom code) |
| Total DOM nodes | 655 |
| Total chunks loaded | 14 |
| Custom font (Haffer) | likely 60–100 KB woff2 (premium foundry) |
| LCP target (estimate) | likely 2.5–3.0s on 4G |
| Animation budget | Motion + Lenis = both run RAF loops; well-tuned but not free |

**Trade-off mereka:** Premium feel > raw performance. They ship 200–300KB JS gladly.

---

## 7. What this means for FlowDesk

Lihat file pendamping: `apps/landing/docs/FRAMEWORK-DECISION-V2.md`.
