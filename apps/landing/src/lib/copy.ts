/**
 * COPY — single source of truth.
 *
 * DE-LEAK POLICY:
 *   We DO NOT publish exact constants, vendor identifiers, solver internals,
 *   schema versions, internal keys, or full mathematical formulas on the
 *   landing page. Outcomes and conventions are fair game. Implementation
 *   details belong in the closed-beta docs, not on a public surface that a
 *   competitor can reverse-engineer from.
 *
 * NARRATIVE ARC:
 *   HERO    — Hook: most options charts lie; ours shows the dealer.
 *   PROBLEM — Why retail GEX is useless on 0DTE.
 *   SYSTEM  — Three engines compute three shapes of the same chain.
 *   LENSES  — Seven ways to read dealer positioning.
 *   HONEST  — What is measured vs approximated (trust builder).
 *   ACCESS  — Single CTA: Discord login → flowjob.id.
 *
 * Voice: confident, terse, market-native. Tech terms stay English in both
 * locales (orderflow, gamma, dealer, walls, IV, skew, snapshot, DTE, GEX).
 * Color rule: brick accent only.
 */

import type { TString } from "@/lib/i18n";

export const copy = {
  nav: {
    system: { en: "System", id: "System" } as TString,
    lenses: { en: "Lenses", id: "Lenses" } as TString,
    flow: { en: "Data flow", id: "Data flow" } as TString,
    access: { en: "Access", id: "Access" } as TString,
    cta: { en: "Get access", id: "Akses" } as TString,
  },

  // HERO — punchy. No button. Both headlines white; cursor smoke paints brick.
  hero: {
    eyebrowBeta: { en: "v0.4 · Closed beta", id: "v0.4 · Closed beta" } as TString,
    eyebrowScope: { en: "0DTE · /ES & /NQ", id: "0DTE · /ES & /NQ" } as TString,
    headline1: { en: "Most options charts lie.", id: "Kebanyakan options chart bohong." } as TString,
    headline2: { en: "Ours shows the dealer.", id: "Kami tunjukkan dealer-nya." } as TString,
    sub: {
      en: "Real-time 0DTE dealer positioning for /ES and /NQ. Built for futures — not stock-option leftovers. One validated read per minute. For operators who trade flow, not opinions.",
      id: "Real-time 0DTE dealer positioning untuk /ES dan /NQ. Dibangun untuk futures — bukan sisa stock-option. Satu validated read per menit. Untuk operator yang trade flow, bukan opini.",
    } as TString,
    scrollHint: { en: "Scroll to see the system", id: "Scroll untuk lihat system-nya" } as TString,
    ticker: [
      "0DTE GEX",
      "Dealer positioning",
      "Gamma walls",
      "Signed orderflow",
      "IV surface",
      "Regime flip",
      "Replay any session",
    ],
  },

  // PROBLEM — the wedge. Agitate before sell.
  problem: {
    eyebrow: { en: "[01] The problem", id: "[01] Masalahnya" } as TString,
    eyebrowRight: { en: "Why most GEX charts fail intraday", id: "Kenapa kebanyakan GEX chart gagal intraday" } as TString,
    headline1: { en: "End-of-day GEX is", id: "GEX end-of-day itu" } as TString,
    headline2: { en: "yesterday’s news.", id: "berita kemarin." } as TString,
    lede: {
      en: "By 9:31am the chain has already moved. By lunch, half the 0DTE volume happened. The free charts circulating online are stale, smoothed, or worse — built off the wrong instrument entirely. We rebuild the chain every minute, sign every trade by aggressor, and stream the result.",
      id: "Jam 9:31 chain sudah pindah. Jam makan siang, separuh volume 0DTE sudah lewat. Chart gratis yang beredar itu stale, smoothed, atau lebih buruk — dibangun di instrumen yang salah. Kami rebuild chain tiap menit, sign tiap trade by aggressor, dan stream hasilnya.",
    } as TString,
    bullets: [
      {
        h: { en: "Stale by an hour", id: "Stale sejam" } as TString,
        b: { en: "Most public GEX feeds update on the close. 0DTE positions die before they refresh.", id: "Kebanyakan public GEX feed update di close. Posisi 0DTE mati sebelum mereka refresh." } as TString,
      },
      {
        h: { en: "Wrong instrument", id: "Salah instrumen" } as TString,
        b: { en: "Stock-option models leak signal on futures. /ES and /NQ need pricing math built for futures — not borrowed from cash.", id: "Model stock-option bocor sinyal di futures. /ES dan /NQ butuh pricing math yang dibangun untuk futures — bukan dipinjam dari cash." } as TString,
      },
      {
        h: { en: "No aggressor side", id: "Tanpa aggressor side" } as TString,
        b: { en: "Without per-trade buy/sell sign, flow is just volume. We use trade-level aggressor directly from the exchange feed.", id: "Tanpa per-trade buy/sell sign, flow cuma volume. Kami pakai trade-level aggressor langsung dari exchange feed." } as TString,
      },
    ],
  },

  // SYSTEM — outcome-language. Engine names stay (FOG/FLUX/ARC), internals stay vague.
  system: {
    eyebrow: { en: "[02] System", id: "[02] System" } as TString,
    headline1: { en: "Three engines.", id: "Tiga engine." } as TString,
    headline2: { en: "One truth per minute.", id: "Satu truth per menit." } as TString,
    lede: {
      en: "Not a feature list. An architecture. FOG, FLUX, and ARC each compute a different shape of the same chain. Every minute, they collapse into one validated read — schema-locked, identical between backend and frontend.",
      id: "Bukan feature list. Arsitektur. FOG, FLUX, dan ARC compute shape berbeda dari chain yang sama. Tiap menit, mereka collapse jadi satu validated read — schema-locked, identik antara backend dan frontend.",
    } as TString,
    layers: [
      {
        id: "FOG",
        kind: { en: "Gamma topology", id: "Gamma topology" } as TString,
        tagline: { en: "The dealer hedging map — for futures.", id: "Map hedging dealer — untuk futures." } as TString,
        copy: {
          en: "Gamma and delta re-evaluated across a price grid, dealer-signed. Rendered as a topographic heatmap so you see where hedging pressure lives — not just at the current print.",
          id: "Gamma dan delta di-re-evaluate lintas price grid, dealer-signed. Di-render sebagai topographic heatmap supaya lu lihat di mana hedging pressure hidup — bukan cuma di current print.",
        } as TString,
        tags: ["Futures-correct", "Dealer-signed", "Topographic", "Per-minute"],
      },
      {
        id: "FLUX",
        kind: { en: "Signed orderflow", id: "Signed orderflow" } as TString,
        tagline: { en: "Per-trade signed flow, auditable end-to-end.", id: "Per-trade signed flow, auditable end-to-end." } as TString,
        copy: {
          en: "Aggressor-signed flow accumulated since the RTH open. Split into total, calls, puts, 0DTE, and retail. The worker and the offline generator produce identical bytes — receipts you can audit.",
          id: "Aggressor-signed flow di-accumulate sejak RTH open. Dipecah ke total, calls, puts, 0DTE, dan retail. Worker dan offline generator produce bytes identik — receipts yang bisa lu audit.",
        } as TString,
        tags: ["Aggressor-signed", "Cumulative", "RTH-reset", "Auditable"],
      },
      {
        id: "ARC",
        kind: { en: "Volatility surface", id: "Volatility surface" } as TString,
        tagline: { en: "The IV layer most retail tools don’t show.", id: "Layer IV yang kebanyakan tool retail tidak tunjukkan." } as TString,
        copy: {
          en: "Per-expiry vol surface, deterministic. ATM vol, expected move, skew. Plus vanna and charm exposure aggregated dealer-signed. Labeled EXPERIMENTAL while the math is still in burn-in.",
          id: "Per-expiry vol surface, deterministic. ATM vol, expected move, skew. Plus vanna dan charm exposure aggregated dealer-signed. Ditandai EXPERIMENTAL selama math-nya masih burn-in.",
        } as TString,
        tags: ["Vol surface", "Vanna", "Charm", "Expected move"],
      },
    ],
    snapshotNote: {
      en: "All three feed one validated read per instrument per minute — schema-locked, identical between server and client. Streamed live. Replayable historically.",
      id: "Ketiganya feed satu validated read per instrumen per menit — schema-locked, identik antara server dan client. Di-stream live. Bisa di-replay historis.",
    } as TString,
  },

  // LENSES — 7 views.
  lenses: {
    eyebrow: { en: "[03] Lenses", id: "[03] Lenses" } as TString,
    eyebrowRight: { en: "Seven views, one chain", id: "Tujuh view, satu chain" } as TString,
    headline1: { en: "Seven ways to read", id: "Tujuh cara baca" } as TString,
    headline2: { en: "the same chain.", id: "chain yang sama." } as TString,
    items: [
      {
        no: "01",
        tag: { en: "Profile", id: "Profile" } as TString,
        title: { en: "Net GEX & DEX per strike.", id: "Net GEX & DEX per strike." } as TString,
        copy: {
          en: "The ladder you check first. Dealer-signed, cumulative since the RTH open. The shape tells you where dealers must hedge.",
          id: "Ladder yang lu check duluan. Dealer-signed, cumulative sejak RTH open. Shape-nya kasih tahu di mana dealer harus hedge.",
        } as TString,
        status: "REAL",
      },
      {
        no: "02",
        tag: { en: "FOG", id: "FOG" } as TString,
        title: { en: "Gamma topology heatmap.", id: "Gamma topology heatmap." } as TString,
        copy: {
          en: "Topographic heatmap of gamma and delta across hypothetical spot. Stacked over time — an evolving terrain. The dealer hedging map.",
          id: "Topographic heatmap dari gamma dan delta lintas hypothetical spot. Di-stack lintas waktu — terrain yang berkembang. Map hedging dealer.",
        } as TString,
        status: "REAL",
      },
      {
        no: "03",
        tag: { en: "FLUX", id: "FLUX" } as TString,
        title: { en: "Signed cumulative flow.", id: "Signed cumulative flow." } as TString,
        copy: {
          en: "Cumulative signed orderflow since the RTH open. Split into calls, puts, 0DTE, retail. Positive = dealer net buying. Negative = selling.",
          id: "Cumulative signed orderflow sejak RTH open. Dipecah ke calls, puts, 0DTE, retail. Positive = dealer net buying. Negative = selling.",
        } as TString,
        status: "REAL",
      },
      {
        no: "04",
        tag: { en: "Walls", id: "Walls" } as TString,
        title: { en: "Top walls & flip.", id: "Top walls & flip." } as TString,
        copy: {
          en: "The session’s biggest dealer-gamma levels on the call and put side, plus the gamma flip strike. Structural — not noise.",
          id: "Level dealer-gamma terbesar di session, sisi call dan put, plus gamma flip strike. Structural — bukan noise.",
        } as TString,
        status: "REAL",
      },
      {
        no: "05",
        tag: { en: "Regime", id: "Regime" } as TString,
        title: { en: "Long-gamma or short.", id: "Long-gamma atau short." } as TString,
        copy: {
          en: "Net gamma sign and a stability read. Long-gamma regimes dampen; short-gamma regimes accelerate. Read this before you size.",
          id: "Net gamma sign dan stability read. Long-gamma regime dampen; short-gamma regime accelerate. Baca ini sebelum size.",
        } as TString,
        status: "REAL",
      },
      {
        no: "06",
        tag: { en: "ARC", id: "ARC" } as TString,
        title: { en: "IV surface, in 3D.", id: "IV surface, dalam 3D." } as TString,
        copy: {
          en: "Per-expiry vol surface. ATM IV, expected move, skew. 3D view: strike × moneyness × IV. Surfaced honestly — EXPERIMENTAL where it should be.",
          id: "Per-expiry vol surface. ATM IV, expected move, skew. 3D view: strike × moneyness × IV. Di-surface honestly — EXPERIMENTAL di mana seharusnya.",
        } as TString,
        status: "EXPERIMENTAL",
      },
      {
        no: "07",
        tag: { en: "Replay", id: "Replay" } as TString,
        title: { en: "Any session, scrubbable.", id: "Session manapun, scrubbable." } as TString,
        copy: {
          en: "Any past RTH session, minute by minute, exactly as the engine saw it. Scrub, pause, study.",
          id: "Past RTH session manapun, menit demi menit, persis seperti engine lihat. Scrub, pause, study.",
        } as TString,
        status: "REAL",
      },
    ],
  },

  // DATA FLOW — outcome-only; no vendor name, no specific stack components.
  flow: {
    eyebrow: { en: "[04] Data flow", id: "[04] Data flow" } as TString,
    headline1: { en: "From tick to read,", id: "Dari tick ke read," } as TString,
    headline2: { en: "in under a minute.", id: "dalam kurang dari satu menit." } as TString,
    lede: {
      en: "A licensed exchange feed delivers raw chain and trades. The engine prices the chain, solves IV, computes the dealer view, and emits one validated read. Cached hot for live. Persisted for replay. Streamed to the terminal.",
      id: "Licensed exchange feed kirim raw chain dan trades. Engine pricing chain, solve IV, compute dealer view, dan emit satu validated read. Di-cache hot untuk live. Di-persist untuk replay. Di-stream ke terminal.",
    } as TString,
    nodes: [
      { id: "Feed", kind: { en: "Source", id: "Source" } as TString, detail: "Licensed CME feed · chain + trades" },
      { id: "Engine", kind: { en: "Compute", id: "Compute" } as TString, detail: "Pricing · IV · GEX · FLUX · FOG · ARC" },
      { id: "Read", kind: { en: "Contract", id: "Contract" } as TString, detail: "Schema-locked · typed end-to-end" },
      { id: "Worker", kind: { en: "Loop", id: "Loop" } as TString, detail: "Per-instrument · per-minute" },
      { id: "Hot cache", kind: { en: "Live", id: "Live" } as TString, detail: "In-memory · sub-second fanout" },
      { id: "History", kind: { en: "Replay", id: "Replay" } as TString, detail: "Scrubbable past sessions" },
      { id: "Stream", kind: { en: "Transport", id: "Transport" } as TString, detail: "WebSocket · DESK-gated" },
      { id: "Terminal", kind: { en: "Surface", id: "Surface" } as TString, detail: "7 lenses · keyboard-first" },
    ],
  },

  // HONEST — outcome-only conventions. No tolerances, no algorithm names, no constants.
  honest: {
    eyebrow: { en: "[05] Honest", id: "[05] Honest" } as TString,
    eyebrowRight: { en: "Receipts, not vibes", id: "Bukti, bukan vibes" } as TString,
    headline1: { en: "We label", id: "Kami label" } as TString,
    headline2: { en: "what we don’t know.", id: "yang tidak kami tahu." } as TString,
    lede: {
      en: "Most vendors hide their gaps behind a slick UI. We do the opposite — every approximated field carries an EXPERIMENTAL flag in the read itself. The chart shows it. The API returns it. You always know what is measured, what is estimated, and what is still in burn-in.",
      id: "Kebanyakan vendor sembunyikan gap mereka di balik UI slick. Kami sebaliknya — setiap field yang di-approximate carry EXPERIMENTAL flag di read itu sendiri. Chart tunjukkan. API return. Lu selalu tahu mana yang measured, mana yang estimated, mana yang masih burn-in.",
    } as TString,
    rows: [
      { k: { en: "Pricing", id: "Pricing" } as TString, v: "Futures-correct math · standard risk-free curve" },
      { k: { en: "IV solver", id: "IV solver" } as TString, v: "Two-stage convergence to floating-point tolerance" },
      { k: { en: "Dealer sign", id: "Dealer sign" } as TString, v: "Industry convention, locked at codepath" },
      { k: { en: "GEX basis", id: "GEX basis" } as TString, v: "Volume-weighted · cumulative since RTH open" },
      { k: { en: "Walls", id: "Walls" } as TString, v: "Top dealer-gamma levels · fixed at session open" },
      { k: { en: "0DTE day-count", id: "0DTE day-count" } as TString, v: "Real wall-clock to the RTH close" },
      { k: { en: "Instruments", id: "Instruments" } as TString, v: "CME /ES and /NQ · standard contract specs" },
      { k: { en: "Cadence", id: "Cadence" } as TString, v: "One read per instrument per minute" },
      { k: { en: "ARC surface", id: "ARC surface" } as TString, v: "EXPERIMENTAL · per-expiry vol fit · burn-in" },
      { k: { en: "Synthetic OI", id: "Synthetic OI" } as TString, v: "EXPERIMENTAL · flagged in the read" },
    ],
  },

  // ACCESS — single funnel.
  access: {
    eyebrow: { en: "[06] Access", id: "[06] Access" } as TString,
    headline1: { en: "No pricing page.", id: "Tidak ada pricing page." } as TString,
    headline2: { en: "Just a Discord role.", id: "Hanya Discord role." } as TString,
    lede: {
      en: "Login with Discord. If you hold the DESK role in our guild, the terminal opens — full stream, full replay, all seven lenses. If you don’t, the door points to flowjob.id, the guild that hands out the role. No seat tax. No trial timer. No credit card.",
      id: "Login dengan Discord. Kalau lu hold role DESK di guild kami, terminal terbuka — full stream, full replay, semua tujuh lenses. Kalau tidak, pintu menunjuk ke flowjob.id, guild yang hand out role. Tidak ada seat tax. Tidak ada trial timer. Tidak ada credit card.",
    } as TString,
    bullets: [
      { en: "Discord OAuth · identity + guild role check", id: "Discord OAuth · identity + guild role check" } as TString,
      { en: "DESK role checked daily · grace window if revoked", id: "DESK role di-check harian · grace window kalau dicabut" } as TString,
      { en: "Full access inside · no gated features", id: "Full access di dalam · tidak ada gated features" } as TString,
      { en: "No DESK → claim it at flowjob.id", id: "No DESK → claim di flowjob.id" } as TString,
    ],
    ctaPrimary: { en: "Login with Discord", id: "Login dengan Discord" } as TString,
    ctaSecondary: { en: "Claim DESK at flowjob.id", id: "Claim DESK di flowjob.id" } as TString,
    legal: {
      en: "Closed beta · historical replay only · live feed armed behind a second flag. Not investment advice. EXPERIMENTAL lenses surfaced for transparency, not execution.",
      id: "Closed beta · historical replay only · live feed armed di belakang flag kedua. Bukan investment advice. EXPERIMENTAL lenses di-surface untuk transparency, bukan execution.",
    } as TString,
  },

  footer: {
    tagline: {
      en: "Real-time 0DTE GEX terminal for /ES & /NQ. Schema-locked. Honest about what’s experimental.",
      id: "Real-time 0DTE GEX terminal untuk /ES & /NQ. Schema-locked. Honest tentang yang experimental.",
    } as TString,
    cols: [
      {
        title: { en: "Product", id: "Product" } as TString,
        links: [
          { label: { en: "System", id: "System" } as TString, href: "#system" },
          { label: { en: "Lenses", id: "Lenses" } as TString, href: "#lenses" },
          { label: { en: "Data flow", id: "Data flow" } as TString, href: "#flow" },
          { label: { en: "Honest", id: "Honest" } as TString, href: "#honest" },
        ],
      },
      {
        title: { en: "Access", id: "Access" } as TString,
        links: [
          { label: { en: "Login with Discord", id: "Login dengan Discord" } as TString, href: "#access" },
          { label: { en: "flowjob.id", id: "flowjob.id" } as TString, href: "https://flowjob.id" },
        ],
      },
      {
        title: { en: "Engineering", id: "Engineering" } as TString,
        links: [
          { label: { en: "Locked contract", id: "Locked contract" } as TString, href: "#" },
          { label: { en: "Methodology", id: "Methodology" } as TString, href: "#" },
          { label: { en: "Honest gaps", id: "Honest gaps" } as TString, href: "#" },
        ],
      },
    ],
    legal: {
      en: "Not investment advice. Beta software. EXPERIMENTAL surfaced for transparency, not execution. © FlowDesk.",
      id: "Bukan investment advice. Beta software. EXPERIMENTAL di-surface untuk transparency, bukan execution. © FlowDesk.",
    } as TString,
  },
};
