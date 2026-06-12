# FlowDesk — Status Implementasi vs FlowGreeks-Riset-Lengkap.md

> Dibuat 2026-06-11. Membandingkan implementasi nyata FlowDesk dengan cetak biru di
> `../research/archive/FlowGreeks-Riset-Lengkap.md` (Bagian 1–6). Tujuan: peta jujur "apa yang
> sudah dibangun" vs "apa yang belum", per bagian dokumen, dengan rujukan file.
>
> **Legenda status:** ✅ SELESAI · 🟡 SEBAGIAN · ❌ BELUM ADA · ⚠️ DIVERGENSI (kode beda dari riset, perlu keputusan)

---

## Ringkasan eksekutif

FlowGreeks (visi di dokumen) = **satu mesin greek + state engine** yang melahirkan
TRACE (heatmap stok), HIRO (flow), vol surface, dan exposure lanjutan (GEX/DEX/VEX/CHEX).
Roadmap dokumen: **MVP-1/2/3** (engine + GEX/DEX + walls + HIRO) → **v2** (TRACE heatmap + vol) → **v3** (vanna/charm + 3D) → **v4** (alert/backtest).

**Posisi FlowDesk sekarang:** sisi **TRACE/stok SELESAI dan kuat** (engine Black-76, IV, GEX/DEX VOL-based, field projection B7 sejati, walls/flip, heatmap topografi + kontur, strike-plot bar, candle OHLC, zoom, key-levels navbar). **Engine HIRO/flow SELESAI** (signed-trade path + akumulator + field `hiro` opsional). Vanna/charm + SVI surface + expected move = **fondasi engine SELESAI** (terisolasi). 3D + modul sistem = belum ada (v3–v4). Sisa besar: **rendering FE** (garis HIRO, dashboard TRACE match 1.png).

Kelima keputusan metodologi (di §Divergensi) **sudah diputuskan user (2026-06-12) & dieksekusi**: VOL-GEX tetap (#1A), wall gamma-$ (#2B), day-count jam-riil (#3A), trades.side (#4A), field hiro opsional (#5A).

---

## BAGIAN 1 — TRACE (heatmap gamma / stok)

| Item dokumen | Status | Bukti / catatan |
|---|---|---|
| Black-76 greeks (delta, gamma, vega) | ✅ | `services/engine/src/engine/black76.py` — delta/gamma/vega/theta **+ vanna + charm** (fungsi murni + test FD). |
| IV solver NR→bisection, mid, tol 1e-6 | ✅ | `engine/iv.py` — Brenner-Subrahmanyam seed, arbitrage-bounded, T-02/T-03 |
| GEX per strike = γ·M·F²·0.01, put −1 | 🟡⚠️ | `engine/exposure.py` — formula benar TAPI pakai **VOL**, bukan OI (lihat Divergensi #1) |
| Konvensi dealer long-call/short-put | ✅ | `exposure.py` `DEALER_SIGN_CALL=+1`, `DEALER_SIGN_PUT=−1` (T-04) |
| **Field projection = re-eval BS di grid harga (BUKAN smear)** | ✅ | `engine/field.py` — di-upgrade ke B7 sejati: re-eval Black-76 lintas price_grid, vektorisasi numpy/scipy. **Persis rekomendasi §1.7.** |
| Sumbu waktu×harga, 1 menit | ✅ | Snapshot per menit; heatmap 2D time×price di `apps/web/lib/heatmap/field-2d.ts` |
| Heatmap diverging OKLab + simetris 0 | ✅ | `lib/heatmap/shaders.ts` — turquoise→hitam→crimson, normalisasi `±maxAbs` |
| Kontur topografi (isoline) | ✅ | shaders.ts — 12 level kontur anti-aliased di atas warna mulus |
| Overlay harga | ✅ | `components/heatmap/heatmap-overlay.tsx` — price trace + (baru) candle OHLC 1m/5m |
| Strike plot bar (sharey heatmap) | ✅ | `components/chart/profile-line.tsx` — bar horizontal turquoise/crimson, shared Y-scale |
| Proyeksi forward 5 hari | ❌ | Hanya intraday RTH; tak ada proyeksi multi-hari |

**Kesimpulan Bagian 1:** ~90% selesai. Yang barusan dikerjakan (B7 field + bar + kontur + candle) menutup gap metodologi terpenting. Sisa: GEX VOL-vs-OI (divergensi), forward 5-hari (belum).

---

## BAGIAN 2 — HIRO (hedging flow real-time)

| Item dokumen | Status | Catatan |
|---|---|---|
| HIRO delta-notional kumulatif | ✅ | `engine/hiro.py` — `HiroState`/`hiro_series`, `HIRO_t = Σ s·δ·q·M·F` sejak RTH open |
| Klasifikasi aggressor side (A/B/N) | ✅ | `aggressor_sign`; `HistoricalSimAdapter.get_hiro_trades` signed per-trade per-leg |
| Breakdown Total/Calls/Puts/0DTE/Retail | ✅ | `HiroSnapshot` (retail = proxy odd-lot heuristik, indikatif) |
| Field `hiro` opsional di Snapshot | ✅ | `schema.py` + `snapshot.ts` (Divergensi #5 → opsi A, tanpa bump) |
| Garis kumulatif (FE) | 🟡 | data per-menit tersedia di `hiro.total`; garis direkonstruksi FE dari urutan frame (FE menyusul) |
| Divergence price-vs-HIRO | ❌ | indikator turunan (FE/analitik), belum |

**Kesimpulan Bagian 2:** engine HIRO **SELESAI** (signed-trade path + akumulator + breakdown + field Snapshot opsional). Sisa: rendering garis di FE + indikator divergence (dikerjakan saat FE dibangun).

---

## BAGIAN 3 — Modul ekspansi 0DTE

### 3A. Volatility — 🟡 SEBAGIAN
- IV surface SVI raw (`surface.py`) — ✅ `fit_svi` (Nelder-Mead, no-butterfly guard), reuse `iv.py`
- Expected move — ✅ `expected_move` (lognormal) + `expected_move_from_straddle` (0.85×)
- VIX-proxy /ES /NQ (model-free) — ❌ belum
- Skew 25Δ, term structure — ❌ belum (SVI params expose skew via rho; helper turunan belum)
- Realized vol (Garman-Klass / Yang-Zhang) — ❌ belum
- **Catatan:** output `surface.py` masih terisolasi (belum masuk Snapshot) — keputusan schema lanjutan bila perlu ditampilkan FE.

### 3B. Exposure greek lanjutan — 🟡 SEBAGIAN
- Vanna — ✅ `black76.vanna` (fungsi murni + test FD)
- Charm — ✅ `black76.charm` (fungsi murni + test FD)
- VEX/CHEX agregasi (Σ vanna·exp·M·F·1%vol / Σ charm·…) — ❌ belum (fondasi greek sudah ada)
- DDOI engine (signed flow → ΔOI) — ❌ belum (item berat, Divergensi #1 → v3)

### 3C. Dinamika 0DTE — 🟡 SEBAGIAN
- Gamma pinning konsep — implisit di field, tak eksplisit
- Afternoon-drift charm — fondasi `charm` ada; agregasi pressure belum
- ✅ **Day-count:** kini jam-riil ke settlement via `t_expiry_from_clock` (Divergensi #3 → opsi A, default di worker + gen). `0.5/365` hanya saat `t_expiry` di-pin.

### 3D. Visualisasi 3D — 🟡 SEBAGIAN
- Heatmap 2D + kontur ✅ · time-scrubbing (scrubber) ✅
- 3D gamma/IV surface (three.js) — ❌ belum ada

### 3E. Modul sistem — ❌ BELUM ADA
- Alerting, regime detection (HMM), backtesting, cross /ES↔/NQ — tak ada
- (Regime sederhana sign+stability% ada di `engine/snapshot.py::_regime`)

---

## BAGIAN 4 — Adaptasi CME / Databento / Black-76

| Item | Status | Catatan |
|---|---|---|
| GLBX.MDP3, tanpa OPRA | ✅ | Dokumen §5.0 konfirmasi ini benar |
| Black-76 (underlying F, tanpa q) | ✅ | `black76.py` |
| Multiplier $50 ES / $20 NQ | ✅ | `engine/snapshot.py` `MULTIPLIER` |
| Schema `definition`/`statistics`/`trades`/`bbo-1m` | ✅ | `engine/feed/historical.py` ingest 4 schema |
| ⚠️ `tbbo` untuk flow | ❌ | Pakai `bbo-1m` + `trades`. Dokumen rekomendasi `tbbo` untuk HIRO (lihat Divergensi #4) |
| Aggressor side native | ❌ | Field `side` ADA di CSV tapi belum dikonsumsi (cuma volume) |
| OHLC futures per menit | ✅ | Baru ditambah: `historical.py::get_ohlc`, field `ohlc` opsional di schema |

---

## BAGIAN 5 — Spek teknis (backend/FE/DB/infra)

Mayoritas **selaras**. Divergensi minor:
- WS full-JSON (dokumen usul MessagePack/biner) — 🟡 belum, tapi belum jadi bottleneck
- Hot-path: **numpy vektorisasi** (dokumen usul Numba) — ✅ cukup, regen field ~18s tanpa Numba
- Cold-path DuckDB/Polars analitik — ❌ belum ada
- Python target 3.11 (mesin dev: 3.14; ada inkompat argparse `%`, sudah di-patch)
- Stack inti (FastAPI + Redis + Timescale + Next.js + Discord DESK) — ✅ selaras

---

## BAGIAN 6 — Reverse-engineering proprietary (A–I)

> Bagian terdalam dokumen. Mayoritas adalah **target v2–v4** dan eksplisit proprietary/perlu kalibrasi.

| Black-box | Status | Catatan |
|---|---|---|
| **A. Synthetic OI / DDOI** | ❌⚠️ | Inti gap metodologi. FlowDesk pakai VOL mentah, bukan signed-flow DDOI + rekonsiliasi ΔOI |
| **B. Zero Gamma (gamma flip)** | ✅ | `engine/levels.py::gamma_flip` — cumulative zero-crossing terinterpolasi = persis **H-B1 (85%)** |
| **B. Volatility Trigger** | ❌ | Tak ada (proprietary, perlu proxy gamma-centroid) |
| **B. Risk Pivot** | ❌ | Tak ada |
| **C. Hedge Wall** | ❌ | Tak ada |
| **D. Call/Put Wall** | ✅ | by **gamma-$** (`gamma·OI` per sisi) = H-D1 (70%), Divergensi #2 → opsi B dieksekusi |
| **D. Absolute Gamma** | ❌ | Tak ada (`largest_gex` mendekati tapi by VOL net, bukan total \|gamma\|) |
| **E. HIRO klasifikasi** | ✅ | = Bagian 2; engine `hiro.py` SELESAI (signed-trade + breakdown + field opsional) |
| **F. IV per kontrak (mid+NR)** | ✅ | `engine/iv.py` = H-F1 (80%) |
| **F. SVI surface** | ✅ | `engine/surface.py::fit_svi` (raw SVI, no-butterfly guard) = H-F3. Terisolasi (belum di Snapshot) |
| **F. Expected move** | ✅ | `engine/surface.py::expected_move` (lognormal) + `_from_straddle` (0.85×) = H-F5 |
| **G. Colormap norm** | ✅ | Simetris-0 + **percentile clip 98** (H-G1): `field.percentile_abs`/`normalize_signed`, paritas FE `field-2d.ts`. Spike 0DTE tunggal tak membakar skala |
| **H. SG Acceleration** | ❌ | Tak ada (proprietary) |
| **I. Charm/Vanna Pressure** | 🟡 | Fondasi `black76.vanna`/`charm` ✅; agregasi VEX/CHEX pressure belum |

---

## DIVERGENSI — SUDAH DIPUTUSKAN (user, 2026-06-12)

> Kelimanya sudah dieksekusi di kode. Detail opsi & tradeoff: `methodology-decisions.md`.

### #1 ✅ GEX berbasis VOL (opsi A — TETAP)
- **Keputusan:** pertahankan `GEX = γ·VOL·M·F²·0.01` (locked). DDOI jadikan jalur v3 dengan kalibrasi, JANGAN cabut VOL-GEX.
- **Kode:** `engine/exposure.py` tidak berubah. DDOI belum dibangun (item berat, nunggu v3).

### #2 ✅ Call/Put Wall by GAMMA-DOLLAR (opsi B — FLIP)
- **Keputusan:** walls = argmax **gamma-$** (`gamma·OI` per sisi), bukan raw OI. Validasi struktural saja (GLBX-ES ≠ SPX, match angka mustahil).
- **Kode:** `engine/levels.py` (`_walls` rank by `gamma_side·OI_side`); builder feed solved `ChainRow` (gamma+OI). `StrikeOI.gamma` default 1.0 → fixtur OI-only tetap reduksi ke OI. Test diskriminatif di `test_field_levels.py`.

### #3 ✅ Day-count jam-riil 0DTE (opsi A — FLIP default)
- **Keputusan:** default kini `t_expiry_from_clock(ts)` → jam-riil ke 16:00 ET. `0.5/365` lama hanya dipakai bila `t_expiry` di-pin eksplisit (test).
- **Kode:** `api/worker.py` (`_t_expiry_for` per tick) + `scripts/gen_session_snapshots.py`. Golden fixture di-rebaseline.

### #4 ✅ `trades.side` cukup (opsi A — tanpa tbbo)
- **Keputusan:** HIRO pakai aggressor `side` dari `trades` CSV; tbbo tidak perlu.
- **Kode:** `HistoricalSimAdapter.get_hiro_trades` mengonsumsi `side`+`price`+`size` per-leg.

### #5 ✅ Field HIRO opsional di Snapshot (opsi A — tanpa bump)
- **Keputusan:** `hiro?` ditambah sebagai field opsional non-breaking (preseden `ohlc`), `schema_version` tetap 1.
- **Kode:** `engine/schema.py` + `packages/contracts/src/snapshot.ts` (byte-for-byte) + wiring builder/worker/gen. Garis intraday direkonstruksi FE dari urutan frame per-menit (bukan path per-trade di tiap frame).

---

## Peta roadmap dokumen → status

| Fase | Modul | Status FlowDesk |
|---|---|---|
| **MVP-1/2** | Black-76 + IV + GEX/DEX + walls/flip + strike plot | ✅ SELESAI (+ B7 field, candle, zoom, key-levels) |
| **MVP-3** | HIRO flow (aggressor side, delta-notional) | ✅ engine SELESAI (`hiro.py` + field opsional); garis FE menyusul |
| **v2** | TRACE heatmap re-eval grid + kontur | ✅ SELESAI (lebih cepat dari roadmap) |
| **v2** | Vol module (SVI, VIX-proxy, RV/IV, skew, EM) | 🟡 SVI + EM ✅ (`surface.py`, terisolasi); VIX-proxy/RV/skew belum |
| **v3** | Vanna/Charm exposure + afternoon-drift | 🟡 vanna/charm greek ✅ (`black76`); agregasi VEX/CHEX belum |
| **v3** | 3D surface + time-scrubbing | 🟡 scrubbing ✅, 3D ❌ |
| **v4** | Alert + regime detection + backtest + cross-index | ❌ belum (regime sederhana ✅) |

---

## Rekomendasi langkah berikut (urut ROI)

**Sudah dikerjakan sesi backend (2026-06-12):** vanna+charm (`black76`), percentile-clip parity (`field`), day-count jam-riil (#3A), HIRO engine + field opsional (#5A), wall gamma-$ (#2B), SVI surface + expected move (`surface.py`). Engine + API + contracts hijau; golden di-rebaseline; JSON sesi FE 2026-06-09 diregen.

Sisa (urut ROI):
1. **Frontend TRACE dashboard match `1.png`** — rendering: heatmap + exposure profile + garis HIRO (ungu/biru) dari `hiro.total` per-menit. Pekerjaan FE terbesar yang tersisa.
2. **VEX/CHEX agregasi + Charm/Vanna Pressure** — fondasi greek (`vanna`/`charm`) sudah ada; tinggal agregasi `Σ vanna·exp·M·F·1%vol` dan afternoon-drift.
3. **Surface ke Snapshot (bila perlu di FE)** — `surface.py` masih terisolasi; keputusan schema lanjutan bila SVI/EM mau ditampilkan.
4. **DDOI engine (A)** — paling berat + proprietary; kalibrasi vs ΔOI. Keputusan sadar (Divergensi #1 → v3); JANGAN cabut VOL-GEX.
5. **VIX-proxy / realized-vol / skew helpers** — turunan dari surface yang sudah ada.

> **Catatan validasi (dari dokumen):** GLBX-ES ≠ SpotGamma-SPX. Level FlowDesk TIDAK akan match angka-per-angka vs SpotGamma (semesta opsi beda). Validasi = **struktural** (arah rezim, urutan ordinal level, timing), bukan nilai absolut.
