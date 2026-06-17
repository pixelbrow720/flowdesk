# Handoff — FlowDesk FOG Page (Heatmap TRACE-Style)

## Server Status
- **Dashboard**: `apps/dashboard` port **4325**
- **Dev command**: `cd apps/dashboard; node node_modules/next/dist/bin/next dev -p 4325`
- **Log**: `$env:TEMP\flowdesk-dashboard.log`
- **Data**: `apps/dashboard/public/data/ES_2026-06-09.json` (390 frames, 5.7MB) + `NQ_2026-06-09.json` (12.2MB)
- **URL**: `http://localhost:4325/fog`

## Engine Backend (sudah OK, jangan diubah)
- **Pipeline**: DBN raw → CSV cache → snapshot JSON via `gen_session_snapshots.py`
- **Forward**: Put-call parity fallback (`_forward_from_parity` di `historical.py`)
- **FOG field**: `engine/fog.py` — TRACE B7 field projection (Black-76 re-eval per hypothetical price, aggregated). SUDAH BENAR secara konsep.
- **Data yang tersedia**: `fog.price_grid[]`, `fog.gamma[]`, `fog.delta[]` per menit (390 frames × ~87-90 price levels)

## File yang Dimodifikasi

### 1. `apps/dashboard/src/app/fog/page.tsx`
- Selector: cuma GEX & DEX (VEX/CEX dihapus)
- Fetch real snapshot JSON dari `/data/ES_2026-06-09.json`
- Panel kiri: scrollable (`overflow-y-auto` + `fog-scroll` class), tooltip hover (billion, percentile, 5m/30m/60m delta)
- Panel kanan: `<GexHeatmap>` sebagai chart utama (bukan candlestick overlay)
- Stats overlay: pakai frame terakhir (bukan mid-session), harga kuning = 7390.35 (aktual)

### 2. `apps/dashboard/src/components/fog/GexHeatmap.tsx` (REWRITE IN PROGRESS)
- **Status**: sudah ditulis ulang, belum diverifikasi visual
- **Color mapping**: turquoise `#0FB5A8` (positif) ↔ hitam ↔ crimson `#B5002E` (negatif)
- **Symmetric scale**: `max(|minVal|, |maxVal|)` — Bookmap-style
- **Smoothing**: sigmaTime=2.5 (temporal), sigmaPrice=3.0 (price axis)
- **Rendering**: canvas kecil (1px/cell) → browser upscales dengan bilinear interpolation
- **Contour lines**: marching squares di 4 level
- **Forward price line**: bone white, prominent
- **Aggregate gamma line**: turquoise, sum ±5 strikes from forward

### 3. `apps/dashboard/src/app/globals.css`
- Tambah `.fog-scroll` scrollbar styling

### 4. `apps/dashboard/src/components/fog/PriceChart.tsx`
- Kembali ke candlestick sederhana (bukan default chart utama, heatmap yang utama)

## Masalah yang Perlu Diperbaiki

### CRITICAL: Panel kiri & kanan tidak sync price axis
- Panel kiri: price ladder (strike harga)
- Panel kanan: heatmap (price_grid dari fog)
- **Solusi**: Gunakan shared axis. Heatmap dan panel kiri harus punya price range yang sama. Saat ini heatmap build axis sendiri dari `price_grid` union, yang bisa beda dari panel kiri.

### HIGH: Visual heatmap belum match SpotGamma TRACE
User kasih feedback:
1. Efek senter/bloom belum benar — harusnya depth-of-saturation (warna pekat = kuat), bukan additive white glow
2. Ada banding/streak vertikal — butuh smoothing lebih agresif
3. Garis hijau di TRACE = aggregate gamma sekitar forward (sum ±5-10 strike)
4. Color scale harus symmetric (max of abs min/max) agar smooth
5. Contour lines harus halus dan menunjukkan "zone borders"

### MEDIUM: NaN handling
- `price_grid` bergeser antar frame → tepi coverage → NaN → harusnya fade ke hitam, bukan streak keras

## Reference Visual (dari user)
- SpotGamma TRACE heatmap: https://www.spotgamma.com/trace
- Dokumentasi resmi:
  - Gamma Heatmap: https://support.spotgamma.com/hc/en-us/articles/33608037264787
  - Delta Pressure: https://support.spotgamma.com/hc/en-us/articles/33608084842643
- Color: positif = biru/teal (low vol/stability), negatif = merah (high vol), netral = hitam
- Contour lines = "zone borders" dan "large shifts"

## Langkah Selanjutnya (Priority Order)

1. **Fix panel sync** — heatmap dan panel kiri harus share price axis yang sama
   - Gunakan `axis.strike_min` dan `axis.strike_max` dari snapshot (bukan union price_grid)
   - Atau: panel kiri render berdasarkan heatmap axis

2. **Fix heatmap visual** — sesuai feedback user:
   - Aggressive smoothing (sigmaTime=3-5, sigmaPrice=4-6)
   - Depth-of-saturation colormap (power curve)
   - Symmetric color scale
   - NaN → fade to black (bukan streak)
   - Aggregate gamma line (sum ±5 strikes from forward)

3. **Test visual** — refresh browser, compare dengan screenshot SpotGamma TRACE

4. **Optional**: Tambah toggle metric (GEX/DEX) yang switch heatmap color

## Brand Colors (Locked Contract)
- Turquoise deep: `#0FB5A8`
- Crimson deep: `#B5002E`
- Bone-0: `#FAFAF7`
- Ink-0: `#000000`
- Rule: `#161618`

## Engine Files (JANGAN UBAH tanpa test)
- `services/engine/src/engine/fog.py` — field projection (sudah benar)
- `services/engine/src/engine/feed/historical.py` — parity forward + expiry disambiguation
- `services/engine/tests/test_historical.py` — 15 tests pass
