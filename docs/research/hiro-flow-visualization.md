# Hiro Indicator & Options Flow Visualization — Research

> **Status riset**: Disusun saat web_search/web_extract tidak aktif (Firecrawl insufficient credits). Konten dari pengetahuan publik tentang SpotGamma HIRO, vol.fyi, dan kompetitor sejenis yang ter-index sebelum cutoff. **Hex color persis, exact label, dan UI terbaru kemungkinan sudah berubah** — verifikasi via screenshot terbaru ketika tools aktif.
>
> Untuk implementasi Flowdesk section **Flux** — pakai sebagai *visual pattern reference*.

---

## 1. Apa Itu HIRO

**HIRO** = *Hedging Impact of Real-time Options*. Indikator proprietary SpotGamma (dan brand rebrand `vol.fyi`) yang mengukur **net dealer-hedging-induced flow** dari options orders intraday.

Konsep:
- Setiap options order yang masuk di-klasifikasi sebagai **bullish** (paksa dealer beli underlying untuk hedge) atau **bearish** (paksa dealer jual)
- Di-aggregate per timeframe (typically per-detik)
- Display sebagai **cumulative line/area chart** time-series

Beda dengan **GEX** (state-based: di strike mana gamma menumpuk sekarang), HIRO adalah **flow-based** (time-series: ke arah mana flow mendorong dealer hedging).

URL utama:
- `https://spotgamma.com/hiro/`
- `https://vol.fyi` (rebrand standalone)
- `https://spotgamma.com/founders-note/`
- YouTube: SpotGamma channel "HIRO Tutorial" playlist
- Twitter: `@spotgamma`, Cem Karsan `@jam_croissant`

---

## 2. Chart Format

### 2.1 Bentuk Dasar
HIRO ditampilkan sebagai **stepped/line chart + filled area** di sekitar zero-line, **bukan candlestick, bukan histogram**. Bentuknya mirip cumulative delta footprint atau OBV (On Balance Volume), tapi dihitung dari options notional flow.

Komponen:
1. **Zero-line horizontal** — anchor visual paling penting
2. **Line/area main** — naik di atas zero saat net flow bullish, turun saat bearish
3. **Fill two-color** — hijau/cyan untuk area positif, merah/magenta untuk negatif. Alpha ~30-50% supaya gridline tetap terbaca
4. **Multi-series** — ketika ditampilkan per-DTE bucket (All / 0DTE / Weekly / Monthly), tiap bucket warna berbeda, toggleable via legend chip

### 2.2 Bukan Band Indicator
HIRO bukan Bollinger/Keltner. Tidak ada upper/lower envelope. Yang sering disalahartikan adalah ketika user stack beberapa HIRO timeframe — itu multi-line, bukan band.

### 2.3 Y-Axis Scaling
- Notional dollar (millions/billions USD net delta-equivalent flow), atau
- Normalized "HIRO score" (proprietary scaling)

X-axis: waktu intraday, default 09:30–16:00 ET, pre/post-market opsional.

---

## 3. Panel Layout — Dual Pane Sync

Layout default HIRO di SpotGamma terminal:

```
┌────────────────────────────────────────────┐
│  TOP NAV  [Terminal] [HIRO] [Equity Hub] … │
├────────────────────────────────────────────┤
│  Ticker: SPX ▾   |   1D  5D  1M  |  ●Live  │
├────────────────────────────────────────────┤
│                                            │
│   PRICE CHART (≈60-70% height)            │
│   ╱╲╱╲ candlestick or line                 │
│   ───── Call Wall 4520 ──── (green solid) │
│   ───── Vol Trigger 4445 ── (orange dash) │
│   ───── Put Wall 4380 ──── (red solid)    │
│                                            │
├────────────────────────────────────────────┤
│   HIRO PANEL (≈30-40% height)              │
│        ▲ +2.3B                             │
│   ────●────────── (zero line)              │
│        ▼ -1.1B                             │
│   timeline sync dengan panel atas          │
└────────────────────────────────────────────┘
```

Dua panel **time-axis sync** — drag-zoom di panel atas otomatis zoom panel bawah.

Tab views:
- **Major Indices**: small multiples 2×2 (SPX, SPY, QQQ, IWM) — mini price + mini HIRO per cell
- **Single Ticker**: full-screen dual-pane
- **Watchlist**: stacked rows per ticker

vol.fyi rebrand lebih minimalis — single panel dengan price overlay sebagai line tipis di belakang HIRO area (TradingView-style embedded subchart).

---

## 4. Color Logic

Pola dari marketing material:

| Kondisi | Color |
|---|---|
| HIRO > 0 (bullish flow) | Green `#00C853` atau cyan/teal |
| HIRO < 0 (bearish flow) | Red `#E53935` atau magenta |
| Spike >X stdev | Line thicker / glow / marker dot |
| Zero crossing | Vertical dotted line + tooltip "Flip" |

Background dark (`#1A1A1A` charcoal atau navy) — dark mode default. Light mode tersedia tapi marketing pakai dark 95%.

HIRO **tidak** pakai gradient by magnitude. Color hanya menandai direction. Magnitude di-encode lewat panjang/tinggi area.

---

## 5. Signal Types

HIRO tidak pop-up alert "BUY/SELL". Sinyal dibaca secara **diskreasi** via pattern:

### 5.1 Zero-Line Cross (Flip)
HIRO crosses zero → shift dealer hedging direction. Cross point sering di-highlight via marker bulat / fill color flip.

### 5.2 Divergence vs Price
Price up + HIRO down (atau sebaliknya) → exhaustion / weak rally. Trader gambar trendline manual; SpotGamma tidak auto-detect.

### 5.3 Squeeze Setup
Confluence: price mendekati Call Wall + HIRO spike positif besar → potential gamma squeeze. Visual: garis horizontal level (panel atas) + spike vertical (panel bawah) terjadi bareng.

### 5.4 Gamma Flip / Vol Trigger Break
Cross Vol Trigger di panel harga + HIRO flip sign → regime change.

### 5.5 0DTE Intensity
Garis HIRO khusus 0DTE highlighted beda warna (sering yellow/orange terang) — dampaknya paling cepat. Spike 0DTE = warning move 5-15 menit ke depan.

---

## 6. Use Case Trader

Dari Reddit r/options, r/thetagang, Twitter Cem Karsan @jam_croissant:

1. **0DTE scalping SPX/SPY**: pantau HIRO 0DTE, masuk searah flow saat spike + price confirmation
2. **Entry timing swing**: bukan trigger, tapi *avoid* entry counter-flow
3. **Risk management**: kalau short gamma + HIRO spike jauh → exit before dealer chase
4. **Sentiment confirmation**: HIRO positif + Call Wall di atas → konfirmasi bullish intraday
5. **Avoid chop**: HIRO oscillate cepat di sekitar zero → market indecisive, sit out

Kritik umum: lagging karena cumulative, susah dibaca di low-liquidity ticker, subscription mahal (~$99-249/bulan).

---

## 7. UX Patterns

- **Ticker switcher**: input dengan autocomplete; quick-pill button SPX/SPY/QQQ/AAPL/TSLA/NVDA
- **Timeframe selector**: button group "1D / 5D / 1M" atau granularity "1m / 5m / 15m". Default intraday 1-min
- **Zoom & pan**: drag-zoom horizontal, double-click reset, sync between dual panes
- **Crosshair tooltip**: hover menampilkan timestamp + price + HIRO value; floating dark card
- **Series toggle**: legend chip di atas chart untuk show/hide expiration bucket
- **Refresh**: real-time streaming, 1-5 detik update di tier tertinggi
- **Annotations**: notes/bookmark per ticker (premium fitur)
- **Multi-monitor**: pop-out chart ke window terpisah (power user feature)

---

## 8. Typography & UI Chrome

- **Font**: sans-serif modern (Inter / IBM Plex Sans) untuk body; **monospace** (Roboto Mono / JetBrains Mono) untuk angka real-time karena alignment critical
- **Background**: dark navy/charcoal (`#0E1116` / `#1A1D24`), text bone (`#E0E0E0`), accent cyan/teal untuk link
- **Top nav**: logo SpotGamma kiri, tab nav tengah, user menu kanan
- **Side panel**: optional drawer untuk watchlist/scanner
- **Footer/status**: data timestamp + "Live" dot (green pulsing)
- **Hierarchy**:
  - Ticker symbol: 24-32px bold
  - Price: 18-20px
  - HIRO value: 14-16px monospace
  - Axis tick: 10-11px monospace

---

## 9. Kompetitor — Pattern Comparison

### 9.1 MenthorQ
- Fokus **levels-based overlay** di TradingView, bukan time-series flow
- Visual: GEX levels sebagai horizontal lines berlabel + magnitude rank
- Color: gradien biru (gamma support) → merah (gamma resistance)
- Jual sebagai TV indicator + standalone dashboard
- Tidak ada cumulative flow line ala HIRO

### 9.2 Unusual Whales
- **Flow scanner table-driven**, bukan chart-first
- Visual signature: live tape table, color-coded by aggressiveness (call sweep above ask = bright green, put sweep below bid = bright red)
- Punya "Net Premium" line chart mirip HIRO — area cumulative net premium
- UI lebih ramai, retail-aesthetic

### 9.3 OptionStrat
- Fokus **strategy builder + payoff diagram** (2D color-coded P/L heatmap dengan slider waktu)
- Punya "Flow" tab tapi simplistik
- Visual signature: hijau-merah gradient heatmap

### 9.4 GEXBot
- Niche: **GEX/DEX/Vanna level visualization**
- Charts: horizontal bar per strike (gamma exposure profile)
- Punya "intraday GEX evolution" mirip HIRO tapi lebih raw (no dealer-flow classification)
- UI spartan, dev-aesthetic

### 9.5 Convex Value
- Ribbon flow chart — visually paling **premium aesthetic**
- Heatmap gamma per strike + smooth animation
- Smaller user base, premium pricing

### 9.6 Tabel Perbandingan

| Tool | Chart Utama | Color Logic | Real-time Flow | Price Sync |
|---|---|---|---|---|
| SpotGamma HIRO | Filled area + line, dual-pane | Green/red divergent | ✅ | ✅ |
| MenthorQ | Horizontal levels overlay | Blue/red gradient | ❌ | ✅ (TV) |
| Unusual Whales | Tape table + net premium | Green/red saturated | ✅ | Partial |
| OptionStrat | Payoff curve + heatmap | Gradient | ❌ | N/A |
| GEXBot | Horizontal bar profile | Green/red | Limited | Partial |
| Convex Value | Ribbon + heatmap | Branded premium | ✅ | ✅ |

---

## 10. Pattern Universal di Options Flow Tools

Yang **selalu muncul**:

1. **Dark theme default** — power user dominan
2. **Hijau bullish, merah bearish** — universal divergent palette
3. **Zero-line sebagai anchor** untuk flow indicator
4. **Filled area + line** untuk cumulative metric; **histogram** untuk discrete event; **horizontal lines** untuk levels
5. **Time-axis sync** antara price chart dan flow indicator
6. **Toggle chip** untuk multi-series / multi-expiration
7. **Monospace untuk angka** real-time
8. **Crosshair tooltip** standard
9. **Refresh status indicator** explicit (live dot)
10. **Ticker quick-switcher** dengan autocomplete + popular pill

---

## 11. Translation ke Flowdesk Flux Section

Section **Flux** di dashboard Flowdesk akan menampilkan options flow time-series. Adopt pattern HIRO-style:

### Komponen Wajib

1. **Dual-pane sync** — price chart (atas) + flow line (bawah)
2. **Flow line as filled area** — diverging dari zero-line
3. **Multi-bucket series**: All / 0DTE / Weekly / Monthly, toggleable chip
4. **Price chart overlay levels**: Call Wall, Put Wall, Vol Trigger (synced dari Fog section data)
5. **Crosshair tooltip** sync di dua pane
6. **Zoom/pan sync** drag-zoom horizontal
7. **Refresh live dot** + last-update timestamp

### Color Mapping ke Brand Flowdesk

Adapter dari generic green/red ke brand color tokens:

| Element | Generic | Flowdesk Brand |
|---|---|---|
| Bullish flow | Green `#00C853` | Turquoise `#40E0D0` |
| Bearish flow | Red `#E53935` | Brick `#B8333E` (atau crimson `#E0183C` untuk lebih punch) |
| Zero line | Gray | Hairline / `#2A2D34` |
| 0DTE highlight | Yellow | Brick-glow `#D54452` (cerah accent) |
| Spot price line | White solid | Bone-0 `#E0E0E0` solid |
| Background | Dark navy | Ink-0 `#000000` murni |
| Call Wall line | Green solid | Turquoise solid |
| Put Wall line | Red solid | Brick solid |
| Vol Trigger | Orange dashed | Brick-glow dashed atau accent neutral |

### Library Recommendation

- **Lightweight Charts (TradingView open-source)** — paling cocok. Built untuk dual-pane sync, time-series flow, level overlay. MIT licensed. Performance native canvas, mature
- **Apache ECharts** — alternatif, more flexible tapi heavier bundle
- **Recharts / Visx** — React-native composition, lebih kontrol tapi effort tinggi
- **Custom D3 + Canvas** — maximum control, untuk team yang nyaman D3

Rekomendasi: **Lightweight Charts** untuk MVP Flux (cepat, mature, dual-pane sync built-in), upgrade ke custom kalau brand identity butuh styling unique yang LC gak support.

### Differentiator vs HIRO

- **Brand color identity** — turquoise + brick, distinctive
- **Better typography** — editorial feel (font-display untuk angka besar)
- **Cleaner mobile** (HIRO mobile experience kurang)
- **Open data semantics** — show what's being measured exactly (gamma weighted, delta weighted), HIRO blackbox
- **Less marketing fluff** — straight to chart, no "premium tier upsell" inline

---

## 12. UX Detail Wajib di Flux

- [ ] Ticker dropdown dengan autocomplete + quick-pill (ES, NQ untuk Flowdesk scope)
- [ ] Timeframe selector: 1D / 5D / 1M intraday granularity 1m
- [ ] Zoom/pan sync antara dua pane
- [ ] Crosshair tooltip: timestamp + price + flow value (monospace)
- [ ] Legend chip toggle: All / 0DTE / Weekly / Monthly
- [ ] Refresh live dot (turquoise pulsing) + last-update timestamp di footer
- [ ] Zero-line crossing marker (small dot)
- [ ] Divergence indicator OPTIONAL — annotation manual via user click
- [ ] Pop-out / fullscreen button
- [ ] Export PNG button (snapshot share-able)
- [ ] Reduced-motion: disable refresh pulse, keep chart static at last frame
- [ ] Mobile: stacked single-pane fallback, bottom-sheet tooltip
- [ ] Keyboard: arrow keys = pan, +/- = zoom, R = reset

---

## 13. Anti-Patterns yang Dihindari

- Tidak pakai **donut/pie** — zero use case di flow visualization
- Tidak pakai **3D chart** untuk flow — confusing, 2D lebih baik
- Tidak **auto-detect divergence dengan ML magic** di MVP — biarkan diskreasi trader
- Tidak **pop-up alert intrusive** — Flowdesk philosophy: surface signal, don't dictate action
- Tidak **animated transition flashy** — financial dashboard should feel instant, no jelly bounce
- Tidak **light theme default** — dark is the convention, light optional

---

**Word count**: ±2,300 kata.

**TODO web tools aktif**:
1. Verify HIRO color hex via screenshot SpotGamma latest
2. Capture vol.fyi UI changes (rebrand evolution)
3. Reddit search "spotgamma hiro disappointed" untuk anti-pattern reference
4. Bandingkan Convex Value live screenshot — yang paling premium aesthetic
5. Check Lightweight Charts dual-pane example terbaru, library version compat
