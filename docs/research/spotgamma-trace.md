# SpotGamma TRACE — Visual & UX Research

> **Status riset**: Disusun saat web_search/web_extract tools tidak aktif (Firecrawl insufficient credits). Konten berasal dari pengetahuan publik tentang SpotGamma TRACE yang ter-index sebelum cutoff training. **Detail visual spesifik (hex color persis, layout exact, copy persis)** kemungkinan sudah berubah karena SpotGamma sering update UI. **Verifikasi disarankan** via screenshot terbaru dan video tutorial mereka ketika tools aktif.
>
> Untuk keperluan implementasi Flowdesk dashboard — pakai sebagai *direction*, bukan spec final.

---

## 1. Apa Itu TRACE

**TRACE** = produk SpotGamma untuk visualisasi **dealer gamma & vanna positioning intraday**, fokus indeks (SPX/SPY, NDX/QQQ) dan komoditas/futures yang aktif di options.

Beda dengan **HIRO** (yang track *flow* time-series), TRACE menampilkan **state of dealer book sekarang** — di strike mana gamma menumpuk, di mana walls berada, dan di level berapa dealer hedging behavior akan flip. Output utamanya bukan satu chart, tapi **suite multi-panel** yang bisa dibaca berbarengan.

URL utama yang harus di-scrape ulang ketika tool aktif:
- `https://spotgamma.com/trace/`
- `https://spotgamma.com/spotgamma-pro/`
- YouTube: channel SpotGamma, playlist "TRACE Tutorial" / "How to read TRACE"
- Twitter: `from:spotgamma trace`
- Reddit: `site:reddit.com spotgamma trace screenshot`

---

## 2. Komponen Visual Utama

Berdasarkan pola yang konsisten muncul di marketing material dan review publik:

### 2.1 Gamma Profile Chart (horizontal bar per strike)
Chart inti TRACE. Format:
- **Vertical axis**: harga underlying (strikes), dari bawah ke atas
- **Horizontal axis**: gamma exposure (positive ke kanan, negative ke kiri) atau hanya magnitude
- **Bar per strike**: tinggi sesuai strike spacing, panjang sesuai gamma magnitude
- **Color**: positive gamma = hijau atau cyan-ish (dealer long gamma → suppress vol), negative gamma = merah atau oranye (dealer short gamma → amplify vol)
- **Reference line**: harga spot saat ini sebagai garis horizontal tebal (sering kuning/putih) yang memotong bar chart

Implementasi: ini adalah **horizontal histogram** dengan diverging bar — bar mulai dari center axis dan tumbuh ke kiri/kanan. Scale axis biasanya symmetric.

### 2.2 Key Levels Table / Sidebar
Panel di samping chart yang list level-level penting:
- **Call Wall** — strike dengan gamma positive paling besar di atas spot, biasanya support/magnet
- **Put Wall** — strike dengan gamma negative paling besar di bawah spot
- **Vol Trigger** / **Zero Gamma** — strike di mana net gamma = 0 (regime flip)
- **HVL** (High Volume Level)
- **Absolute Gamma Strike**

Format: tabel kompak dengan kolom Label · Strike · (Optional) Magnitude. Color-code per row sesuai role (Call Wall = hijau, Put Wall = merah, Vol Trigger = oranye/ungu).

### 2.3 Intraday Evolution / Heatmap
Chart yang track gamma per strike **sepanjang hari**:
- **X-axis**: waktu (09:30–16:00 ET)
- **Y-axis**: strike
- **Color cell**: gamma value at that strike at that time
- Diverging colormap: blue/cyan → black/neutral → red/oranye
- Sering ada overlay: garis spot price plotted sebagai line putih melintang

Ini adalah **2D heatmap** (matrix). Format mirip seismic/geophysics chart — banyak data, color encoding heavy.

### 2.4 GEX Profile (Aggregated)
Single number per ticker: total Gamma Exposure (notional dollar terms). Ditampilkan sebagai:
- Big number di atas (`$3.2B`)
- Sparkline tren 30 hari di bawah
- Color: positive = green, negative = red

### 2.5 Charm / Vanna Profile (premium tier)
Sama format dengan gamma profile, tapi metric berbeda — **rate of change of delta over time** (charm) atau **over vol** (vanna). Visualization sama: horizontal bar per strike.

### 2.6 Real-time Spot Price Mini-Chart
Sub-panel kecil yang nunjukin price action live, dengan **horizontal level lines** untuk Call Wall / Put Wall / Vol Trigger overlay. Format candlestick atau line, refresh tiap 1-5 detik.

---

## 3. Layout & Composition

Halaman TRACE di terminal SpotGamma kemungkinan struktur:

```
┌─────────────────────────────────────────────────────────────┐
│ TOP NAV  [SPOTGAMMA] [HIRO] [TRACE] [Equity Hub] [...]      │
├─────────────────────────────────────────────────────────────┤
│ TICKER BAR  [SPX ▾]  [Date: today ▾]  [Refresh: live ●]    │
├──────────────────────────────────┬──────────────────────────┤
│                                  │  KEY LEVELS              │
│   GAMMA PROFILE (vertical)       │  ─────────────           │
│   horizontal bars per strike     │  Call Wall    4520       │
│   diverging green/red            │  Put Wall     4380       │
│   spot line overlay              │  Vol Trigger  4445       │
│                                  │  HVL          4500       │
│                                  │                          │
│                                  │  GEX TOTAL               │
│                                  │  $3.2B  +12%             │
│                                  │  ▁▂▃▅▇▆▄▃                │
├──────────────────────────────────┴──────────────────────────┤
│ INTRADAY HEATMAP                                            │
│ time → → → → → → → → → → → → → → → → → → → → →            │
│ strikes (Y), color = gamma at (strike, time)                │
│ with spot price line overlay                                │
└─────────────────────────────────────────────────────────────┘
```

Variasi yang umum:
- **Tab switcher** "Gamma / Charm / Vanna / Delta" di atas chart utama
- **Expiration filter** (All / 0DTE / Weekly / Monthly) sebagai chip group
- **Compare mode** — overlay 2 ticker atau 2 timestamp

Pada wide screen (>1600px), layout 3 kolom: profile (kiri), heatmap (tengah), levels+stats (kanan). Pada mobile, stacked vertikal.

---

## 4. Color System

Pola yang konsisten di product screenshot SpotGamma:

| Element | Warna |
|---|---|
| Background | Dark — charcoal `#0E1116` atau navy `#1A1D24` |
| Body text | Bone `#E0E0E0` / `#C9C9C2` |
| Positive gamma | Green/teal — `#00C853`, `#1DE9B6`, atau cyan `#00BCD4` |
| Negative gamma | Red/orange — `#E53935`, `#FF6F00` |
| Call Wall line | Solid green |
| Put Wall line | Solid red |
| Vol Trigger / Zero Gamma | Orange `#FF9800` atau purple `#AB47BC`, sering dashed |
| Spot price line | Yellow `#FFEB3B` atau white `#FFFFFF`, solid thick |
| HVL | Cyan dashed |
| Hairline / grid | Dim `#2A2D34` |
| Accent / brand | Tealish `#00BFA5` (SpotGamma logo) |

**Light mode**: tersedia tapi marketing 95% pakai dark. Untuk Flowdesk, dark default match.

**Diverging palette principle**: gamma adalah quantity yang punya zero-center natural — ini *signature usecase* untuk diverging colormap. Pakai **RdBu** atau **RdYlGn** atau custom brand divergent. JANGAN sequential (viridis/plasma) untuk gamma — confusing.

---

## 5. Chart Types yang Konsisten

Yang dipakai TRACE:

1. **Horizontal histogram** (gamma profile) — bar diverging per strike
2. **2D heatmap** (intraday evolution) — matrix color cell
3. **Line chart with horizontal level overlays** (price action panel)
4. **Sparkline** (mini trend di key stats)
5. **Big number + delta indicator** (GEX total)
6. **Tabular list** (key levels)

Yang **TIDAK** muncul di TRACE (penting untuk dibedakan):
- Candlestick standalone (TRACE bukan price chart tool)
- Pie/donut chart (zero usage di financial dashboard professional)
- Radar chart (idem)
- 3D anything (TRACE is 2D-flat)

---

## 6. Interactivity & UX Patterns

### Hover & Tooltip
- **Crosshair on heatmap**: hover di cell menampilkan tooltip floating dengan format:
  ```
  Strike   4485
  Time     11:42 ET
  Gamma   +$245M
  ```
- **Bar chart hover**: highlight bar (border atau brightness boost), tooltip di samping
- **Level line hover**: tooltip nempel di line, kasih definisi level itu (educational)

### Time Scrub
- Slider di bawah heatmap untuk scrub kembali ke timestamp historical
- Ketika di-scrub, gamma profile chart juga update (sync state)
- Play/pause button untuk auto-replay intraday evolution

### Level Toggle
- Each level in legend (Call Wall, Put Wall, etc.) bisa di-toggle on/off
- Disimpan ke localStorage per user

### Refresh Indicator
- Dot status di header: green pulsing = streaming live, gray = paused/stale
- Last update timestamp di footer: `Last: 11:42:37 ET` monospace

### Ticker Switch
- Dropdown atau autocomplete input di top, dengan quick-pill SPX/SPY/QQQ/NDX/IWM
- Switch mempertahankan filter state (timeframe, expiration filter)

### Export
- Button "Export PNG" / "Copy Image" pada chart
- Tier tinggi: API/CSV download

---

## 7. Typography

- **Sans-serif modern** untuk UI chrome — Inter, IBM Plex Sans, atau similar
- **Monospace untuk angka real-time** — Roboto Mono, JetBrains Mono, IBM Plex Mono. Critical karena angka berubah dan alignment harus tetap rapi
- **Hierarchy**:
  - Ticker symbol: 24-32px bold sans
  - Big stat (GEX): 28-36px monospace bold
  - Level value: 16-18px monospace
  - Label / level name: 11-13px sans uppercase tracking 0.15em
  - Axis tick: 10-11px monospace
  - Tooltip body: 12-13px monospace (numbers) + sans (labels)

---

## 8. Refresh Cadence

Berdasarkan tier produk (publik):
- **Pro tier**: 1-second refresh, intraday history full
- **Standard**: 5-15 second refresh
- **Free / demo**: end-of-day snapshot only

Critical untuk UX: **show data freshness** secara explicit. User perlu tau kalo data 5 detik basi atau live.

---

## 9. Responsive Behavior

Pattern yang lazim:
- **>1600px**: 3-column (profile, heatmap, sidebar)
- **1200-1600px**: 2-column (profile+heatmap stacked, sidebar terpisah)
- **768-1200px**: 1-column stacked, panel collapsible
- **<768px**: minimal — gamma profile + key levels list, heatmap hidden atau swipe-able tab

Mobile considerations:
- Heatmap crosshair via touch — pakai long-press atau move finger
- Tooltip jadi bottom sheet di mobile
- Disable some animations (level pulse) untuk performa

---

## 10. Translation ke Flowdesk Dashboard

Untuk section dashboard kita (Fog · Flux · Arc · Settings), TRACE pattern paling cocok di-adopt di section yang menampilkan **state-now dealer positioning** — kemungkinan **Fog**.

### Komponen yang harus ada di Fog:
1. **Gamma profile horizontal bar chart** — divergent green/brick (pakai brand color: `#40E0D0` turquoise positive, `#B8333E` brick negative — match brand alih-alih hijau-merah generic)
2. **Key levels sidebar** — tabular dengan level lines color-coded
3. **Intraday heatmap** — sub panel di bawah profile
4. **Big GEX stat** — di atas, dengan sparkline tren

### Color mapping ke brand Flowdesk:
- Positive gamma → `#40E0D0` (turquoise)
- Negative gamma → `#B8333E` (brick)
- Spot line → `#E0E0E0` (bone-0)
- Vol Trigger → `#D54452` (brick-glow) atau `#FF9800` orange neutral
- Background → `#000000` (ink-0)
- Hairline / grid → `#2A2D34` atau token `--hairline`

### Differentiator vs TRACE:
- Brand color identity (turquoise + brick instead of generic green/red)
- Cleaner typography hierarchy (TRACE feel terminal-ish heavy; Flowdesk lebih editorial)
- Better mobile (TRACE mobile experience kurang)

### Library untuk implementasi:
- **D3.js + React** untuk horizontal bar profile (custom flexible)
- **Apache ECharts** atau **Plotly** untuk heatmap (built-in interactivity)
- **Lightweight Charts** (TradingView open source) untuk price line + level overlays
- **Visx** (Airbnb) — alternative D3-React composition

Rekomendasi: **D3 + React + custom rendering** untuk profile (control penuh visual), **Lightweight Charts** untuk price+level overlay (mature, fast).

---

## 11. Kompetitor TRACE — Comparison

| Tool | Fokus | Strength | Weakness |
|---|---|---|---|
| **SpotGamma TRACE** | Index dealer positioning | Brand recognition, content ekosistem | Pricing premium |
| **MenthorQ** | Levels-based, TV indicator | TradingView integration | Less flow context |
| **GEXBot** | GEX/DEX/Vanna profile | Cheap, dev-friendly | Spartan UI |
| **OptionStrat Flow** | Flow + payoff | All-in-one strategy + flow | Less depth |
| **Unusual Whales** | Tape + flow | Live tape unique | Cluttered UI |
| **Convex Value** | Ribbon flow chart | Aesthetic premium | Niche audience |

Yang paling visually polished untuk dealer positioning: **TRACE** dan **Convex Value**. **MenthorQ** menarik karena tetap pakai TradingView native chart sebagai canvas — lower friction adoption.

---

## 12. Quick Reference — Visual Spec Checklist

Saat implementasi Fog section di Flowdesk, pastikan:

- [ ] Gamma profile chart: horizontal bar, diverging from spot price center
- [ ] Color: turquoise positive, brick negative, no green/red
- [ ] Spot price as solid white horizontal line, thick
- [ ] Call Wall, Put Wall, Vol Trigger sebagai labeled horizontal lines
- [ ] Key levels sidebar: tabular, color-dot prefix matching line color
- [ ] Intraday heatmap below, time X / strike Y / color = gamma
- [ ] Crosshair tooltip: monospace numbers, dark card
- [ ] Time scrub slider with play/pause
- [ ] Level toggle in legend
- [ ] GEX total big number + sparkline
- [ ] Refresh status indicator (live dot pulse)
- [ ] Dark theme default, no light toggle (yet)
- [ ] Monospace for all numbers, sans for labels
- [ ] Responsive: 3-col → stacked
- [ ] Export PNG button
- [ ] No 3D, no candlestick standalone, no radar, no donut

---

**Word count**: ±2,400 kata.

**TODO ketika web tools aktif**:
1. Re-fetch screenshot TRACE actual untuk verify hex color, exact layout
2. Watch SpotGamma YouTube tutorials latest (2024-2025) untuk capture UI changes
3. Cross-check Reddit threads untuk user complaint patterns (apa yang TRACE gagal handle, jadi opportunity Flowdesk)
4. Check if SpotGamma has API/widget embed — bisa dijadikan reference live
