# REKOMENDASI KEPUTUSAN — Backend FlowGreeks

> **STATUS (2026-06-12): kelima keputusan SUDAH DIPUTUSKAN user & DIEKSEKUSI.**
> Keputusan: **#1→A** (VOL-GEX tetap), **#2→B** (wall gamma-$), **#3→A** (day-count jam-riil, default di-flip), **#4→A** (trades.side), **#5→A** (field `hiro` opsional, tanpa bump schema_version).
> Engine + API + contracts hijau; golden fixture di-rebaseline; JSON sesi FE 2026-06-09 diregen. Doc di bawah dipertahankan sebagai rekaman opsi/tradeoff + rencana item berat (§4.B) yang BELUM dibangun (DDOI, metrik proprietary).

> Dokumen keputusan untuk user. Tiap poin: (a) status kode sekarang, (b) apa kata
> riset, (c) tradeoff, (d) rekomendasi, (e) opsi A/B/C yang bisa dipilih.
> Disusun oleh sesi backend otonom (2026-06-12). Semua item §4.A sudah dikerjakan &
> hijau; dokumen ini hanya untuk hal yang **menyentuh locked contract / divergensi**
> dan **item berat** yang sengaja TIDAK dibangun tanpa approval.

Status verifikasi saat dokumen ditulis:
- engine: **157 passed**, ruff **All checks passed**, mypy modul baru (`surface.py`,
  `hiro.py`) **no issues**.
- api: **75 passed**.
- mypy `engine` package menampilkan ~16 error **pre-existing** di file yang TIDAK
  disentuh sesi ini (`snapshot.py`, `feed/__init__.py`, `field.py:48` scipy-stub,
  `field.py:103` `FieldArrays.to_dict`). Sengaja tidak diutak-atik (locked core,
  risiko T-01..T-10). Lihat catatan di akhir.

---

## DIVERGENSI #1 — GEX berbasis VOL vs OI/DDOI

**(a) Kode sekarang.** `GEX_strike = gamma · VOL · M · F² · 0.01`, VOL kumulatif sejak
RTH open. Net GEX>0 → pinning (turquoise), <0 → volatile (crimson). Ini **locked
contract** (STITCHING_GUIDE §2).

**(b) Riset.** mega-riset & riset-spotgamma: SpotGamma sesungguhnya pakai **DDOI**
(Daily Dealer Open Interest) — perubahan OI yang sudah di-sign per dealer-convention,
bukan volume harian. VOL overcounts intraday churn (buka-tutup posisi yang tidak
mengubah inventaris dealer).

**(c) Tradeoff.**
- VOL: real-time, tidak butuh OI settle (OI baru tersedia T+1), match mockup `1.png`.
  Tapi overcount churn, bisa lebih "noisy" sore hari.
- DDOI: lebih dekat ke positioning sebenarnya, tapi butuh kalibrasi signing (Lee-Ready /
  tick-rule) + OI yang lag 1 hari → tidak murni real-time untuk hari berjalan.

**(d) Rekomendasi.** **JANGAN cabut VOL-GEX.** Jadikan DDOI sebagai **jalur v3 paralel**
(field baru `gex_ddoi` opsional), tampilkan side-by-side untuk validasi struktural,
flip default hanya setelah DDOI terbukti ordinal-konsisten dgn VOL pada data 9–10 Jun.

**(e) Opsi.**
- **A (rekomendasi):** pertahankan VOL default; bangun DDOI sebagai layer v3 opsional + kalibrasi.
- **B:** ganti total ke DDOI (melanggar locked contract; butuh approval eksplisit + regen golden).
- **C:** hybrid — VOL untuk intraday live, DDOI untuk overnight/"prior day" baseline.

---

## DIVERGENSI #2 — Call/Put Wall by OI vs gamma-$ IV-weighted

**(a) Kode sekarang.** Wall = `argmax(OI)` per sisi, static, Top-3. Locked: "wajib persis
SpotGamma". (`levels.compute_levels`.)

**(b) Riset.** Riset 6D (H-D1, bobot 70%): wall yang lebih benar = **gamma-dollar
IV-weighted** (`Σ gamma·OI·M·F²` per strike), bukan OI mentah. OI mentah bisa salah
tunjuk saat ada strike OI-besar tapi gamma-kecil (jauh OTM, deep ITM).

**(c) Tradeoff.** Tension nyata: locked contract minta match SpotGamma per-angka, tapi
riset bilang metodologi SpotGamma sendiri ≈ gamma-$. Catatan §6: GLBX-ES ≠ SpotGamma-SPX,
jadi match per-angka **mustahil** apa pun metodenya — validasi hanya struktural.

**(d) Rekomendasi.** Karena match per-angka mustahil (semesta beda), **pindah ke gamma-$
weighted wall** lebih defensible secara metodologi. Tapi ini **menyentuh locked level
semantics** → butuh approval. Sementara: sediakan `walls_gamma_dollar` sebagai field
diagnostik opsional di samping wall-by-OI, bandingkan ordinal.

**(e) Opsi.**
- **A:** pertahankan OI-wall (status quo, locked) + tambah `walls_gamma_dollar` diagnostik.
- **B (rekomendasi metodologis):** flip ke gamma-$ weighted wall (butuh approval, update doc level).
- **C:** dua set wall ditampilkan FE (OI = "OI Wall", gamma-$ = "Gamma Wall"), user lihat keduanya.

---

## DIVERGENSI #3 — Day-count 0DTE: `0.5/365` vs jam-riil

**(a) Kode sekarang.** `DEFAULT_T_EXPIRY = 0.5/365` (`api/worker.py` +
`scripts/gen_session_snapshots.py`). Konstanta — tidak peka jam.

**(b) Riset.** mega-riset §F/§I **KRITIKAL**: 0DTE harus pakai **jam-riil ke settlement**.
Gamma/theta 0DTE meledak non-linear menjelang close; `0.5/365` flat menggambar profil yang
salah pada pagi (T terlalu kecil) & sore (T terlalu besar).

**(c) Tradeoff.** Mengubah default **menggeser SEMUA angka snapshot** + golden fixture +
**bisa pecahkan T-01..T-10**. Ini blocker keras kalau di-flip sembarangan.

**(d) Rekomendasi & STATUS.** Sudah **diimplementasikan sebagai fungsi baru
`t_expiry_from_clock(ts)`** (jam-riil ke settlement 16:00 ET, sesuai §4.A.3) **TANPA
mengganti default**. Default lama tetap `0.5/365`. Tinggal user approve flip.

**(e) Opsi.**
- **A (rekomendasi):** flip default ke `t_expiry_from_clock` SETELAH regen golden + verifikasi
  T-01..T-10 di-rebaseline secara sadar.
- **B:** pertahankan `0.5/365` (status quo), `t_expiry_from_clock` hanya untuk modul v3 (HIRO/surface).
- **C:** flip hanya untuk pricing intraday live, golden test tetap pakai konstanta (dua jalur).

---

## DIVERGENSI #4 — `tbbo` vs `bbo-1m`+`trades`

**(a) Kode sekarang.** Adapter baca `trades` (size) + `bbo-1m` (quote). `trades.side`
(aggressor) tersedia di CSV tapi sebelumnya diabaikan.

**(b) Riset.** Untuk HIRO, `trades.side` (B/A/N) **sudah cukup** untuk signing aggressor.
`tbbo` (trade+book-at-trade) cuma "nice to have" untuk verifikasi quote-at-trade.

**(c) Tradeoff.** tbbo = 1 schema ingest tambahan (biaya Databento + storage) untuk
marginal akurasi. `trades.side` sudah memberi sign langsung dari CME.

**(d) Rekomendasi & STATUS.** **Pakai `trades.side`, tidak perlu tbbo.** Sudah
diimplementasikan: `get_hiro_trades` mengonsumsi `side`+`price`+`size` per-leg (§4.A.4).

**(e) Opsi.**
- **A (rekomendasi):** `trades.side` only. Selesai, tidak ada aksi lanjutan.
- **B:** tambah tbbo ingest untuk validasi silang (biaya naik, akurasi marginal).

---

## KEPUTUSAN #5 (SCHEMA) — Field HIRO di Snapshot

**(a) Kode sekarang.** HIRO hidup **terisolasi** di `engine/hiro.py` (`HiroSnapshot`,
`HiroSeries`, `.to_dict()`). **Belum** masuk `schema.py`/`snapshot.ts`.

**(b) Konteks.** HIRO perlu ditampilkan FE (garis ungu/biru di `1.png`). Cepat-lambat
harus sampai ke kontrak. Preseden: field `ohlc` dulu ditambah sebagai **opsional
non-breaking TANPA bump schema_version**.

**(c) Tradeoff.**
- Opsional non-breaking (ikut preseden `ohlc`): tidak melanggar locked `schema_version 1`,
  FE lama tetap jalan. Tapi field opsional → konsumen harus handle absen.
- Bump `schema_version`→2: eksplisit, tapi **melanggar locked contract** (schema_version 1
  terkunci) → butuh approval + update zod mirror + semua validator.

**(d) Rekomendasi.** **Opsional non-breaking, TANPA bump** (ikuti preseden `ohlc`).
Bentuk: `hiro?: { total, calls, puts, zerodte, retail, cumulative[] }` di `Snapshot`,
mirror byte-for-byte di `snapshot.ts`. **Tunggu konfirmasi sebelum menyentuh schema.py.**

**(e) Opsi.**
- **A (rekomendasi):** tambah `hiro` opsional, tanpa bump schema_version (preseden ohlc).
- **B:** bump schema_version→2 (butuh approval; ubah locked contract + semua validator).
- **C:** HIRO tetap di luar Snapshot — disajikan via endpoint/JSON terpisah (`/hiro`), FE fetch sendiri.

> Setelah #5 disetujui: WAJIB regen JSON sesi FE
> (`scripts/gen_session_snapshots.py … --date 2026-06-09`) supaya `/preview/real` memuat HIRO.

---

## ITEM BERAT (§4.B) — JANGAN bangun tanpa approval; rencana + risiko saja

### 6. DDOI engine (Bagian 6A)
- **Kenapa berat:** butuh signing OI-delta per dealer-convention (Lee-Ready/tick-rule),
  kalibrasi vs ΔOI aktual, dan OI lag T+1. Proprietary di SpotGamma.
- **Rencana bila di-approve:** (1) ambil `statistics` OI harian; (2) sign ΔOI dgn tick-rule
  pada `trades`; (3) akumulasi DDOI per strike; (4) kalibrasi koefisien vs gamma-$ pada 9–10 Jun;
  (5) ekspos `gex_ddoi` paralel dgn VOL-GEX (jangan cabut VOL).
- **Risiko:** salah signing → arah rezim flip; lag OI → bukan real-time; kalibrasi overfit ke 2 hari data.
- **Terkait Divergensi #1.** Rekomendasi: jangan bangun sampai #1 diputuskan.

### 7. Proprietary metrics (Volatility Trigger / Hedge Wall / Risk Pivot / SG Acceleration / Absolute Gamma)
Semua **proprietary** SpotGamma — tidak terdokumentasi resmi. Pendekatan **proxy** yang
bisa dibangun bila di-approve (tandai jelas sebagai proxy, bukan replika):
- **Absolute Gamma:** `Σ |gamma·OI·M·F²|` per strike → strike dgn total gamma absolut
  tertinggi. Paling aman (definisi jelas). **Proxy paling defensible.**
- **Volatility Trigger:** strike di mana net-GEX dealer flip tanda (≈ gamma-flip versi OI).
  Proxy: cari zero-crossing profil GEX-by-OI.
- **Hedge Wall:** strike dgn konsentrasi hedging flow terbesar — proxy dari HIRO累积 per strike.
- **Risk Pivot / SG Acceleration:** paling buram; **jangan** proxy tanpa spesifikasi user.
- **Risiko umum:** menamai proxy dgn nama SpotGamma menimbulkan ekspektasi match yang
  mustahil (semesta GLBX-ES ≠ SPX). Bila dibangun, beri label "proxy/derived", bukan nama asli.

---

## CATATAN: mypy baseline pre-existing (engine package)
`mypy -p engine` memunculkan ~16 error di file yang TIDAK disentuh sesi ini:
`snapshot.py` (Axis/AxisLike protocol + arg-type gamma/delta), `feed/__init__.py:62`
(`quote_schema: str|None`), `field.py:48` (scipy missing stub), `field.py:103`
(`FieldArrays.to_dict` generic). Modul baru sesi ini (`surface.py`, `hiro.py`) **bersih**.
Ini bukan regresi sesi ini; perbaikan menyentuh locked core → diserahkan ke keputusan user
agar tidak membahayakan gate T-01..T-10.
