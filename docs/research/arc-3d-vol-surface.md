# 3D Volatility Surface — Arc Section Research

> **Status**: Disusun saat web_search/web_extract tidak aktif (Firecrawl insufficient credits). Konten dari pengetahuan tentang Three.js, react-three-fiber, Plotly, dan vendor finance tools — public docs ter-index sebelum cutoff. **Detail versi library terbaru kemungkinan sudah berubah** — verifikasi version compat saat implementasi.
>
> Untuk implementasi Flowdesk section **Arc** — 3D volatility surface viewer.

---

## 1. Anatomi Volatility Surface

Volatility surface adalah fungsi 3D `σ(K, T)` di mana:
- **X-axis** = Strike (atau **moneyness** `K/S`, atau **log-moneyness** `ln(K/F)`, atau **delta** untuk FX convention)
- **Y-axis** = Time-to-expiry `T` (calendar days, business days, atau `√T` untuk smoother surface)
- **Z-axis** = Implied Volatility (annualized %, atau **total variance** `σ²T` untuk no-arbitrage analysis)

Data input biasanya **sparse grid** — hanya beberapa expiry × beberapa strike yang likuid di pasar nyata. Sebelum di-render, perlu **interpolation / fitting** untuk smooth surface:
- **SVI** (Stochastic Volatility Inspired) — Gatheral parameterization, industry standard
- **SABR** — common di rates, FX
- **Cubic spline 2D** — gampang implementasi, tidak no-arb safe
- **Thin-plate spline** — smooth tanpa banyak parameter
- **Gaussian process** — Bayesian, kasih confidence band

Untuk Flowdesk yang fokus 0DTE /ES dan /NQ, surface lebih simple — single expiry per ticker per hari, jadi yang divisualisasi mungkin **smile** (1D, σ vs K) bukan full 3D surface. Tapi untuk multi-DTE view (0DTE + weekly + monthly), surface 3D tetap relevant.

---

## 2. Teknik Rendering — Pilihan Visual

| Teknik | Kapan Dipakai | Pros | Cons |
|---|---|---|---|
| **Smooth shaded surface** (triangle mesh + Phong/Lambert) | Default Bloomberg OVDV, OptionStrat 3D | Wow-factor, mudah baca smile/skew/term shape | Bisa "menyembunyikan" data sparse dengan interpolasi misleading |
| **Wireframe mesh** (lines only) | Quant research tools, dx.research | Tidak menyembunyikan grid resolution, ringan | Kurang "premium" feel untuk dashboard end-user |
| **Hybrid: shaded + wireframe overlay** | Bloomberg OVDV, ICE Data | Best of both — struktur grid + shape jelas | Render cost 2× |
| **Color-mapped 2D heatmap dengan elevation hint** | LiveVol, ORATS web | Familiar, scannable | Hilang sense of slope/curvature |
| **Point cloud raw quotes** | Research, debugging fit residual | Honest tentang sparsity | Susah baca shape |
| **Contour / isoline overlay** di surface | OVDV, surfacevol | Bantu baca exact level IV | Tambah clutter di mobile |

**Best practice industri**: shaded surface + thin wireframe (alpha ~0.3) + isolines tipis, dengan **markers di posisi raw quotes** (point cloud di atas mesh). Ini pattern Bloomberg OVDV dan dx Analytics.

Untuk Flowdesk Arc, rekomendasi: **smooth shaded surface dengan optional wireframe toggle**. Default smooth — premium feel. Power user bisa toggle wireframe untuk audit data quality. Raw quote markers sebagai dot kecil instanced — opsional.

---

## 3. Library / Tech Stack

### 3.1 Plotly.js (`Plotly.surface`)

URL: https://plotly.com/javascript/3d-surface-plots/

Trade-off:
- **Pro**: paling cepat untuk MVP. Built-in orbit/zoom/contour-projection ke wall, exportable PNG/SVG, axis labels gratis
- **Con**: bundle size full plotly ~3.5 MB (heavy). Solusi: `plotly.js-gl3d-dist` partial bundle ~1.2 MB. Styling terbatas (susah match brand exact). Animasi frame-by-frame agak janky di mobile mid-range

Verdict: bagus untuk prototype dalam 1-2 hari. Untuk production Flowdesk yang brand-heavy, kemungkinan butuh switch ke custom.

### 3.2 Three.js (raw)

URL: https://threejs.org

Approach: pakai `THREE.PlaneGeometry` segmented, mutate vertex Z attribute per data point.

Trade-off:
- **Pro**: kontrol penuh, performa terbaik (60 fps di 200×200 mesh desktop). Bundle ~150 KB
- **Con**: Anda harus build sendiri axes, labels, colorbar, tooltips, picking. Effort 1-2 minggu untuk production-quality

### 3.3 react-three-fiber (R3F) + drei — **REKOMENDASI UTAMA**

URL: https://r3f.docs.pmnd.rs/ • https://github.com/pmndrs/drei

Sweet spot untuk React dashboard. Declarative wrapper di Three.js, kompose dengan `<Canvas>`, `<mesh>`, `<OrbitControls>` sebagai komponen JSX.

Trade-off:
- **Pro**: integration React state mudah (Zustand, Context), drei provides 80% utility you need (Text, OrbitControls, GizmoHelper, useFrame, etc.). Bundle ~200 KB
- **Con**: react reconciliation overhead (minor, mostly ignorable). Learning curve kalau team belum familiar Three.js mental model

### 3.4 Babylon.js, deck.gl, ECharts GL

- **Babylon.js**: punya `MeshBuilder.CreateGroundFromHeightMap`, PBR built-in. Lebih populer di game/AEC, jarang di fintech
- **deck.gl**: untuk geospatial primarily. `SimpleMeshLayer` bisa dipaksa untuk vol surface, tapi bukan idiomatic
- **ECharts GL** (`echarts-gl`): `surface3D` series, populer di Asia. Integration ECharts ekosistem mudah, plug-and-play

### 3.5 Verdict Stack untuk Flowdesk

**react-three-fiber + drei** untuk Arc section. Reasoning:
1. Project sudah React/Next.js — match stack
2. Brand color tokens turquoise/brick perlu kontrol penuh material — R3F kasih ini
3. Animation morphing surface (data update) gampang via react-spring + drei
4. Mobile fallback ke 2D heatmap via React conditional render — clean separation
5. Bundle size acceptable (~200 KB R3F + Three.js core)

---

## 4. Vendor Finance — Examples Reference

| Vendor | Produk | Pendekatan |
|---|---|---|
| **Bloomberg Terminal** | `OVDV <GO>`, `VCUB <GO>` | Smooth shaded surface, wireframe overlay, colorbar di kanan, kontur projection di "floor". Camera default ~30° elevation, ~45° azimuth. Skema warna proprietary (orange→yellow→green→cyan). Background hitam (terminal native) |
| **OptionStrat 3D Vol Surface** | https://optionstrat.com/build/iv-surface/ | Three.js based, smooth surface, turbo-like colormap, axis labels di edge mesh. Mobile-friendly (touch orbit). Hover tooltip menampilkan strike/expiry/IV exact |
| **vol.fyi (crypto)** | https://vol.fyi | Surface untuk BTC/ETH options, Plotly under the hood (terlihat dari DOM). Default view miring sedikit, contours diaktifkan |
| **surfacevol.com** | https://surfacevol.com | Dedicated viewer interactive, fokus quant research |
| **ORATS** | https://orats.com | Predominantly 2D heatmap + skew curves; 3D ada di research view, scientific look (matplotlib-style) |
| **LiveVol / CBOE DataShop** | LiveVol Pro | 2D-first (skew, term-structure separately), 3D opsional |
| **ICE Data Services** | ICE Options Analytics | Smooth surface + point markers untuk raw quotes + fitted overlay |
| **dx Analytics** (open-source ref) | dx-analytics.com | matplotlib mplot3d wireframe — research-style, gak ada UX polish |
| **Deribit** | metrics.deribit.com | Plotly 3D, viridis-ish, time slider |

**Pola konsisten dari semua vendor**:
1. Default camera **bukan top-down dan bukan side**, tapi sekitar (azimuth 30-60°, elevation 25-35°)
2. Selalu ada **colorbar** di kanan yang map IV value → color
3. **Term-structure axis arah ke depan** (Y), strike axis arah ke kanan (X) — convention quant
4. ATM (at-the-money) ditandai dengan **garis vertikal/highlight strip**
5. Dark background dominan (Bloomberg terminal style)

Untuk Flowdesk Arc, ikut convention ini — default camera angle 30° elevation × 45° azimuth, axis Y arah ke depan untuk expiry, ATM strip highlighted.

---

## 5. Camera & Interaction Patterns

### 5.1 Default Camera Position

Industry convention: bukan top-down, bukan side, tapi **3/4 perspective**.

```
camera.position.set(12, 10, 12)   // ekuivalen azimuth ~45°, elevation ~30°
camera.lookAt(0, 2, 0)             // sedikit di atas floor (surface elevated)
```

### 5.2 Projection: Perspective vs Orthographic

- **Perspective** (FOV 40-50°) lebih disukai untuk wow-factor — surface "in your face"
- **Orthographic** untuk pure analysis — Bloomberg punya toggle keduanya

Rekomendasi Flowdesk: perspective default, no toggle (keep simple). FOV 45°.

### 5.3 OrbitControls Config Aman

Setting yang menghindari user "nyasar di space":

- `enablePan = false` — pan bikin user nyasar dari surface
- `enableDamping = true` — smoothness rotation
- `dampingFactor = 0.08`
- `minDistance = 8`, `maxDistance = 35` — clamp zoom
- `minPolarAngle = π/6` — jangan biarkan user lihat dari bawah surface (confusing)
- `maxPolarAngle = π/2.05` — clamp dari side
- `autoRotate = false` default — ON cuma untuk landing/showcase mode
- `autoRotateSpeed = 0.5`

### 5.4 Touch Handling Mobile

- 1 finger → orbit
- 2 finger pinch → zoom
- 2 finger drag → biasanya disable atau optional pan
- **Double-tap → reset camera** (essential di mobile, gampang nyasar)

### 5.5 View Presets

Tambahkan button group "Reset / Front / Side / Top" — pattern OptionStrat & Bloomberg:
- **Reset**: kembali ke default 3/4 perspective
- **Front**: melihat smile (skew curve), camera di sumbu Y
- **Side**: melihat term structure, camera di sumbu X
- **Top**: 2D heatmap projection, camera dari atas

User pakai preset 80% waktu, manual orbit 20%.

---

## 6. Lighting & Shading

### 6.1 Setup Minimal "Premium Look"

3-light setup standar:

- **Ambient**: `0xffffff` intensity 0.35 — base illumination
- **Key directional**: `0xffffff` intensity 1.0, position (10, 18, 10) — dominant light dari atas-kanan
- **Fill directional**: `0x88aaff` intensity 0.25, position (-10, 8, -8) — cool fill dari belakang-kiri (compensate shadow)
- **Optional hemisphere**: `0xffffff` sky / `0x202030` ground intensity 0.2 — skylight feel

Kombinasi ini memberikan surface yang **shaded depth** tanpa overlit atau flat.

### 6.2 Shading Model

- **`MeshStandardMaterial`** (PBR) untuk look modern, `metalness: 0.05–0.15`, `roughness: 0.55–0.7` — **rekomendasi default**
- **`MeshPhongMaterial`** lebih cheap, masih oke untuk mobile
- **Avoid `MeshBasicMaterial`** kecuali pure heatmap mode (no shading) — surface jadi flat visually

### 6.3 Color Ramp / Colormap by IV

Pilihan colormap (Z = IV → color):

| Palette | Source | Use case | Accessibility |
|---|---|---|---|
| **Viridis** | matplotlib | Default scientific, IV mapping | ✅ CVD-safe, perceptually uniform |
| **Plasma** | matplotlib | Dark BG dashboard | ✅ |
| **Inferno** | matplotlib | High-energy, premium dark UI | ✅ |
| **Magma** | matplotlib | Like Inferno, slightly cooler | ✅ |
| **Turbo** | Google | High-contrast spectral, attention-grabbing | ⚠️ luminance not monotone |
| **Jet** | MATLAB legacy | **Avoid** — perceptually broken | ❌ |
| **Cividis** | CVD-optimized | Accessibility-first products | ✅✅ |
| **RdBu / RdYlBu** | ColorBrewer | Diverging — vol *change*, residuals | ✅ |
| **Custom Bloomberg-like** | Orange→Yellow→Cyan | Brand match | depends |
| **Custom Flowdesk** | Brick→Bone→Turquoise | Brand identity | TBD |

**Rekomendasi default Flowdesk Arc**: **Plasma** atau **Inferno** (dark theme, premium look). Custom Flowdesk gradient (`#B8333E` brick → `#1A1D24` mid → `#40E0D0` turquoise) bisa dipertimbangkan tapi perlu test perceptual uniformity — diverging palette match brand, bagus untuk vol *change* mode.

Color **biasanya dipetakan ke IV (Z)**, tapi advanced: bisa ke gradient/skew (`dσ/dK`) untuk highlight smile shape.

### 6.4 Wow-Factor Color Tricks

- **Animated colorbar threshold** — user drag range slider untuk zoom palette ke region 15-30% IV, highlight skew detail
- **Diverging by ATM** — color dari ATM, OTM-call vs OTM-put pakai sisi opposite ramp
- **Glow on extreme** — IV > 50% dapat emissive material slight, surface "berpendar" di wing

---

## 7. Axis Treatment di 3D Space

Tantangan: text di Three.js selalu menghadap kamera (billboarding) atau lock ke axis — pilih satu strategy.

### 7.1 Library: drei `<Text>`

Pakai SDF font dari drei, sharp di semua zoom level:

```jsx
<Text position={[5, 0, -5]} rotation={[-Math.PI/2, 0, 0]}
      fontSize={0.4} color="#aaa" anchorX="center">
  Strike $4500
</Text>
```

### 7.2 Best Practices

1. **Tick labels di edge mesh** (bukan grid line) — kurangi clutter
2. **Axis title** di tengah edge, lebih besar (fontSize 0.6)
3. **Tick marks fisik**: small `<lineSegments>` keluar dari edge ~0.15 unit
4. **Auto-billboard untuk small labels** (`<Billboard>` drei) supaya selalu readable; **fixed orientation untuk axis title** (lebih clean)
5. **Hide far-side axis** — labels di edge yang menghadap kamera saja. Update on `controls.change` event:
   - Hitung dot product camera-to-mesh dengan axis normal
   - `xAxisFront.visible = camDir.z > 0`, `xAxisBack.visible = camDir.z < 0`
6. **Strike axis**: untuk equity options pakai `$` prefix dan thousand-separator. Untuk FX gunakan delta convention (`25Δ P, ATM, 25Δ C`)
7. **Expiry axis**: `7d / 1M / 3M / 6M / 1Y / 2Y` — jangan kalender date raw kecuali zoom in
8. **IV axis**: persen dengan satu desimal (`24.5%`)

### 7.3 Untuk Flowdesk

- Strike axis: `$4500`, `$4550`, `$4600` — monospace
- Expiry axis: `0DTE`, `1d`, `1w`, `1m` — bukan calendar date raw
- IV axis: `24.5%` monospace, label tegak

Color label: `text-bone-2` (`#C9C9C2`) — visible di black BG, tidak compete dengan surface color.

Font: Inter atau IBM Plex Sans (sans untuk label), monospace untuk angka kalau perlu alignment ketat.

---

## 8. Performance Considerations

### 8.1 Rules of Thumb

| Aspek | Rule |
|---|---|
| Mesh resolution | 50×50 = 2,500 verts cukup untuk smooth look. 100×100 = 10k verts mulai berasa di mobile mid-range |
| LOD switching | Switch ke 30×30 saat distance > X, atau saat `devicePixelRatio < 1.5`, atau saat user `isOrbiting` (full res setelah idle 200ms) |
| Frame rate target | 60 fps desktop, 30 fps mobile minimum. Pakai `<PerformanceMonitor>` drei untuk auto-degrade |
| Geometry update | Saat data berubah, **mutate `position.array` + `position.needsUpdate = true` + `computeVertexNormals()`** — JANGAN buat geometry baru tiap frame (GC kill) |
| Antialiasing | `antialias: true` mahal di mobile. Alternatif: FXAA postprocess atau MSAA via `WebGLRenderTarget({ samples: 4 })` |
| Pixel ratio cap | `renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))` — retina 3× = 9× pixel cost |
| Picking/hover | Raycaster di full-res mesh OK 60fps; pakai `throttle(16ms)` di mousemove |
| Suspense / lazy load | Lazy-load Three.js (`React.lazy`) — initial bundle saving 150 KB |
| Web Workers | Surface fitting (SVI calibration) ke worker, post message back grid Z values |
| Instanced markers | Untuk raw quote markers, `InstancedMesh` (1000 quotes = 1 draw call) |

### 8.2 Memory Pitfall

Dispose geometry & material lama saat data refresh:

```js
oldGeometry.dispose()
oldMaterial.dispose()
oldTexture?.dispose()
```

Kalau tidak: dalam 1 jam refresh per 5 detik bisa leak ratusan MB.

### 8.3 Mobile-Specific

- Reduce mesh density (50×50 → 35×35)
- Disable shadows (`shadows={false}` pada Canvas)
- Bigger hit targets untuk hover/picking (raycaster threshold)
- 2D fallback aktif kalau `window.innerWidth < 640` atau `!gl` (WebGL not supported)

### 8.4 Loading States

- **Skeleton 3D box** saat fetching data
- **Progressive**: render coarse mesh first (10×10), refine ke 50×50
- **Spinner** kalau SVI calibration > 500ms
- **Suspense fallback** untuk lazy-loaded canvas

---

## 9. UX Best Practices

### 9.1 When to Show 2D Fallback

- `window.innerWidth < 640` → default 2D heatmap (vertical: expiry, horizontal: strike, color: IV) + skew curve at selected expiry
- WebGL not supported (`!gl` check) → 2D fallback
- User preference (`prefers-reduced-motion`) → 2D atau 3D no-animation
- **Toggle button "2D / 3D" selalu tersedia** — power users hate forced 3D

### 9.2 Mobile Handling

- **Touch hint overlay**: "Drag to rotate, pinch to zoom" yang fade out setelah first interaction (localStorage flag)
- **Reduce mesh density**: 50×50 → 35×35
- **Disable shadows**
- **Bigger hit targets** untuk hover/picking
- **Portrait mode**: rotate camera by 90° atau show "rotate device" prompt

### 9.3 Accessibility (a11y) — sering diabaikan!

- **Keyboard navigation**: arrow keys = orbit, +/- = zoom, R = reset
- **Tab focusable canvas** dengan `aria-label="Volatility surface chart, S&P 500, 5 expiries × 25 strikes. Press arrow keys to rotate."`
- **Screen reader summary**: live region with text "Front-month 25-delta put IV 28.4%, ATM 18.2%, 25-delta call 17.1%. Skew steeply negative."
- **Tabular fallback** linked from chart ("View data as table") — required untuk WCAG
- **Color-blind safe** colormap: viridis ✓, turbo ✗, jet ✗
- **Min contrast** untuk axis labels: 4.5:1 against background

### 9.4 Hover & Tooltip

- Crosshair raycaster di mesh → render tooltip floating
- Format tooltip:
  ```
  Strike     $4485
  Expiry     7d
  IV         24.5%
  ```
- Monospace numbers, sans labels
- Dark card background dengan subtle border
- Position: follow cursor, atau pin to side untuk readability di small screen

### 9.5 Loading & Error States

- **Loading**: skeleton box 3D + spinner di tengah
- **Error fetching data**: panel error dengan retry button
- **No data for selected ticker**: empty state dengan suggestion
- **Stale data warning**: badge "Data 5min old" kalau refresh gagal

### 9.6 Reduced-Motion

Honor `prefers-reduced-motion: reduce`:
- Disable surface morphing animation on data update (snap, not lerp)
- Disable autoRotate
- Disable expanding ring pulse on quote update
- Keep static surface render — orbit still allowed (user-initiated)

---

## 10. Wow-Factor Effects

Untuk Flowdesk Arc bisa premium-feel:

### 10.1 Animated Surface Morphing

Slider `t` dari T-30d → T-now, **lerp** between snapshot grids:

```js
function morph(z0, z1, t) {
  return z0.map((row, i) => row.map((v, j) => v * (1-t) + z1[i][j] * t))
}
```

Atau `BufferGeometryUtils.toMorphAttribute()` — built-in Three.js morph target.

User experience: scrubbing slider, surface "breathe" between historical states. Powerful storytelling untuk vol regime change.

### 10.2 Isolines / Contour Lines

Two ways:
- **Projection ke floor** (Plotly built-in style) — paling clean
- **On-surface contours** via shader fragment — line yang nempel di surface 3D

Untuk Flowdesk, projection ke floor lebih cocok (cleaner, less visual noise).

### 10.3 ATM Term-Structure Highlight

Ribbon mesh (thicker line) tracking K=S(t) across expiries, di-render di atas surface dengan `polygonOffset` untuk avoid Z-fighting. Brand color: brick-glow `#D54452` solid line.

### 10.4 Skew Curve at Selected Expiry

Vertical "blade" plane intersecting surface, atau highlighted row of mesh dengan glow. Click expiry tick → blade activate.

### 10.5 Real-time Pulse on Quote Update

Saat new quote masuk, spawn **expanding ring shader** at strike/expiry coordinate, fade 800ms — feel seperti "live market". Subtle tapi sangat effective. Disable di reduced-motion.

### 10.6 Surface "Fly-In" Entrance Animation

On mount, animate Z scale 0 → 1 over 600ms with easeOutCubic. Pakai `useSpring` (react-spring) di R3F:

```jsx
const { scale } = useSpring({
  from: { scale: 0 },
  to: { scale: 1 },
  config: { duration: 600 }
})
<a.mesh scale-y={scale} ... />
```

Disable di reduced-motion — direct snap render.

### 10.7 Comparison Mode

Two surfaces translucent (`opacity: 0.6`):
- Yesterday vs today (same ticker)
- Two underlyings (ES vs NQ comparison)
- Two timestamps (regime shift)

Color them differently (turquoise vs brick), with **delta surface (difference)** toggle as third surface.

### 10.8 Volumetric / God Rays

Postprocess `GodRaysEffect` (postprocessing lib) — overkill tapi memorable kalau brand membutuhkan. Untuk Flowdesk: skip, keep clean.

### 10.9 Brand-Specific: ASCII-aesthetic

Bisa overlay ASCII grid pattern di background canvas (subtle) untuk match landing page aesthetic. Eksperimental, bisa iterate later.

---

## 11. Architecture Pattern (Production)

```
┌──────────────────────────────────────────────────────┐
│  Data fetch (REST/WS) → raw (K, T, mid IV, bid/ask)  │
└──────────────────────┬───────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────┐
│  Web Worker: SVI/SABR calibration, build N×M grid    │
└──────────────────────┬───────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────┐
│  Zustand store: { grid, strikes, expiries, meta }    │
└─────────┬─────────────────────────────────┬──────────┘
          ▼                                 ▼
   ┌──────────────┐              ┌─────────────────┐
   │ R3F <Canvas> │              │ 2D fallback     │
   │ <VolSurface> │              │ Heatmap+Skew    │
   └──────────────┘              └─────────────────┘
          ▲                                 ▲
          └──────── shared selectors ───────┘
```

**Prinsip**: keep raw quotes & fitted grid both in store — overlay raw markers on fitted surface untuk transparency (user lihat where data is real vs interpolated).

---

## 12. Implementation Checklist

Saat implementasi Arc section di Flowdesk:

- [ ] Pilih stack: **react-three-fiber + drei** default
- [ ] Pisahkan fitting (Web Worker) dari rendering (main thread)
- [ ] Mesh resolution 50×50 default, LOD 30×30 mobile
- [ ] Camera default `(12, 10, 12)` perspective FOV 45°
- [ ] OrbitControls dengan polar clamping
- [ ] Lighting: ambient 0.35 + key directional 1.0 + fill 0.25
- [ ] `MeshStandardMaterial` vertexColors, plasma/inferno ramp
- [ ] Edge axis labels via drei `<Text>`, tick marks, ATM highlight
- [ ] Hover raycaster + tooltip (strike/expiry/IV)
- [ ] Floor contour projection
- [ ] Raw quote markers as `InstancedMesh`
- [ ] 2D fallback toggle + auto on mobile/no-WebGL
- [ ] Keyboard nav, ARIA label, tabular fallback
- [ ] Reset view + preset views (front/side/top)
- [ ] Surface morph animation on data change (with reduced-motion fallback)
- [ ] Dispose old geometry/material on update
- [ ] PixelRatio cap 2, antialias toggle
- [ ] PerformanceMonitor → degrade quality saat <40fps
- [ ] Brand color: turquoise/brick gradient option
- [ ] Dark BG `#000000` murni, no light theme

---

## 13. Stack Recommendation per Use Case

| Use case | Stack | Reasoning |
|---|---|---|
| MVP / prototype 1-2 hari | **Plotly.js** | Out of the box, semua axis/contour/colorbar gratis |
| Production dashboard React, brand-heavy | **react-three-fiber + drei** | Custom styling, integration React state, performa solid |
| Maximum performance, 1M+ data points | **Three.js raw + custom shaders** | Full GPU control, no React reconciliation |
| Sudah pakai mapbox/geospatial | **deck.gl** | Reuse stack |
| Riset internal, no UX | **Plotly Python export HTML** | Quants happy |
| Mobile-first PWA | **R3F + 2D Plotly fallback** | 3D bagus desktop, fallback essential mobile |

**Untuk Flowdesk Arc**: react-three-fiber + drei + react-spring + Web Worker (SVI fitting) + Zustand state + 2D fallback (Plotly atau custom heatmap).

---

## 14. Key Sumber & Link Verifikasi

- **Plotly 3D surface**: https://plotly.com/javascript/3d-surface-plots/
- **Plotly Python equivalent**: https://plotly.com/python/3d-surface-plots/
- **Three.js docs**: https://threejs.org/docs/
- **Three.js examples (height map)**: https://threejs.org/examples/#webgl_geometry_terrain
- **react-three-fiber**: https://r3f.docs.pmnd.rs/
- **drei helpers**: https://github.com/pmndrs/drei
- **Babylon.js terrain**: https://doc.babylonjs.com/features/featuresDeepDive/mesh/creation/set/heightMap
- **deck.gl SimpleMeshLayer**: https://deck.gl/docs/api-reference/mesh-layers/simple-mesh-layer
- **OptionStrat IV surface**: https://optionstrat.com/build/iv-surface/
- **Deribit metrics (crypto vol)**: https://metrics.deribit.com/
- **vol.fyi**: https://vol.fyi
- **ORATS**: https://orats.com
- **CBOE LiveVol**: https://datashop.cboe.com/livevol-pro
- **Colormap research**: https://bids.github.io/colormap/
- **Turbo colormap**: https://research.google/blog/turbo-an-improved-rainbow-colormap-for-visualization/
- **SVI parameterization (Gatheral)**: https://mfe.baruch.cuny.edu/wp-content/uploads/2013/01/OsakaSVI2012.pdf

> Karena search/extract tools error 402 hari ini, tidak bisa fetch screenshot URLs spesifik. Untuk visual reference, cari di Google Images: `"Bloomberg OVDV" volatility surface`, `"OptionStrat IV surface"`, `"Plotly volatility smile 3D"`.

---

## 15. TODO Ketika Web Tools Aktif Lagi

1. Re-fetch screenshot OptionStrat 3D vol surface, capture exact visual style
2. Watch YouTube tutorials latest Three.js + R3F volatility surface
3. Cari GitHub repo `r3f-volatility-surface` atau similar — copy starter pattern
4. Verify Bloomberg OVDV color scheme (mungkin sudah update)
5. Check Plotly v3 (atau version terbaru) breaking changes untuk surface API
6. Capture Convex Value 3D mode (kalau ada) — visually paling premium
7. Cross-check matplotlib colormap perceptual benchmark
8. Test SVI calibration library mana yang fastest di JavaScript (numjs vs custom)

---

**Word count**: ~3,200 kata.

