# PROMPT UNTUK SESI BARU — Implementasi Backend FlowGreeks (engine-only)

> Salin SELURUH isi di bawah garis ini ke sesi Claude Code baru. Prompt ini self-contained.
> Tujuan: kerjakan semua implementasi BACKEND/ENGINE yang aman & aditif secara otonom,
> dan untuk apa pun yang menyentuh locked contract / divergensi metodologi: BERHENTI,
> tulis rekomendasi, tunggu persetujuan user. Frontend dikerjakan terpisah saat user bangun.

---

Kamu adalah engineer otonom di proyek **FlowDesk** (monorepo di working dir ini). Baca dulu, lalu kerjakan.

## 0. WAJIB DIBACA DULU (jangan skip)
1. `CLAUDE.md` (root) — arsitektur Snapshot, locked contract, perintah build/test.
2. `STITCHING_GUIDE.md` — locked contract lengkap (§2) + gate akseptasi PRD **T-01..T-10** (§7). **Regresi di gate ini = blocker keras.**
3. `Research/FlowDesk-Implementation-Status.md` — peta jujur "sudah vs belum", per-bagian, dengan path file. **INI peta kerjamu.**
4. `Research/mega-riset.md` + `Research/FlowGreeks-Riset-Lengkap.md` — cetak biru metodologi (rumus HIRO/vanna/charm/SVI/expected-move, klasifikasi aggressor, dll). Penanda klaim: [FAKTA]/[INFERENSI]/[PROPRIETARY]/[TIDAK TERDOKUMENTASI].

Apa itu FlowDesk: terminal opsi 0DTE GEX/DEX untuk /ES & /NQ (CME, Databento GLBX.MDP3, Black-76). Semua berputar di **satu struktur Snapshot** (pydantic di `services/engine/src/engine/schema.py`, dimirror zod di `packages/contracts/src/snapshot.ts` — keduanya HARUS byte-for-byte sama). Status: sisi TRACE/stok selesai; **HIRO/flow = NOL**; vanna/charm/vol surface = belum ada.

## 1. ATURAN KERJA SESI INI (penting)
- **BACKEND/ENGINE SAJA.** Jangan sentuh rendering frontend (`apps/web/components/**`, shader, candle, dst) — itu dikerjakan user saat bangun. Boleh sentuh `packages/contracts` HANYA jika perlu mirror schema (lihat keputusan di §4).
- **Aditif & non-breaking.** Jangan ubah perilaku yang sudah lewat T-01..T-10. Tambah fungsi/modul baru; jangan cabut yang ada.
- **Jangan ubah locked contract tanpa persetujuan.** Warna, font, 12 ENV key, dealer long-call/short-put, schema_version 1 — semua terkunci.
- **Untuk SETIAP hal yang menyentuh locked contract ATAU salah satu dari 4 divergensi (lihat §3): BERHENTI.** Jangan putuskan sendiri. Tulis opsi + rekomendasimu + tradeoff ke `Research/REKOMENDASI-keputusan.md`, lalu lanjut ke item aman berikutnya.
- **Verifikasi tiap perubahan** (mypy strict=true di kedua service):
  ```bash
  cd services/engine && pytest && ruff check . && mypy
  cd ../api && pytest && ruff check . && mypy
  ```
  Kalau menambah perilaku, tambah test. Jangan klaim selesai kalau ada test merah.
- **Jangan commit** kecuali diminta; cukup stage/biarkan di working tree + laporkan. (User akan review saat bangun.)

## 2. DATA TERSEDIA (9 Juni 2026 — sudah di disk, tidak perlu download)
- `data/raw/{trades,bbo-1m,definition,statistics}/{ES,NQ}_20260609_20260610.csv`
- **`trades` CSV sudah punya kolom aggressor `side`** (`B`=beli agresif/at-ask, `A`=jual agresif/at-bid, `N`=netral). HIRO siap dibangun dari sini. **Tidak perlu tbbo** (lihat Divergensi #4).
- OHLC 1m futures diturunkan dari trade futures via `HistoricalSimAdapter.get_ohlc` (`services/engine/src/engine/feed/historical.py`).
- Adapter saat ini **hanya membaca `size`** dari trades (`_load_trades`), **kolom `side` diabaikan**. HIRO butuh kamu mengonsumsi `side` + `price` per-trade per-leg opsi.
- Regenerasi JSON sesi untuk FE setelah perubahan engine (FE `/preview/real` memuat `ES_2026-06-09.json` dari `apps/web/public/sessions/`):
  ```bash
  cd services/engine
  PYTHONPATH=src python scripts/gen_session_snapshots.py \
    --date 2026-06-09 --data-dir <ABS_PATH_KE>/data/raw \
    --out ../../apps/web/public/sessions --quote-schema bbo-1m
  ```
  (Cek `.env`/`DATA_DIR` untuk path data-dir yang benar.)

## 3. EMPAT DIVERGENSI + 1 KEPUTUSAN SCHEMA — BUTUH PERSETUJUAN USER
Jangan eksekusi sepihak. Untuk tiap poin, tulis ke `Research/REKOMENDASI-keputusan.md`: (a) status kode sekarang, (b) apa kata riset, (c) tradeoff, (d) rekomendasimu, (e) opsi A/B/C yang bisa user pilih. Detail latar ada di `FlowDesk-Implementation-Status.md` §Divergensi.

- **#1 GEX berbasis VOL vs OI/DDOI.** Kode: `GEX=γ·VOL·M·F²·0.01` (locked). Riset: OI/DDOI signed. Rekomendasi awal: JANGAN cabut VOL-GEX; jadikan DDOI jalur v3 dengan kalibrasi.
- **#2 Call/Put Wall by OI vs gamma-$ IV-weighted.** Kode: argmax OI (locked "wajib persis SpotGamma"). Riset 6D: gamma-$ (H-D1 70%) lebih benar. Tension nyata.
- **#3 Day-count 0DTE: `0.5/365` vs jam-riil.** Kode: `DEFAULT_T_EXPIRY=0.5/365` (`services/api/src/api/worker.py` + `scripts/gen_session_snapshots.py`). Riset §F/§I KRITIKAL: harus jam-riil ke settlement. **Catatan: mengubah ini menggeser SEMUA angka snapshot & golden fixture + bisa pecahkan T-01..T-10.** Maka: implementasi sebagai fungsi/param baru `t_expiry_from_clock(ts)` TANPA mengganti default — default lama tetap, tunggu persetujuan untuk flip.
- **#4 `tbbo` vs `bbo-1m`+`trades`.** Untuk HIRO, `trades.side` sudah cukup (tersedia). tbbo cuma "nice to have". Rekomendasi: pakai `trades.side`, tidak perlu tbbo.
- **#5 (keputusan schema) Field HIRO di Snapshot.** HIRO menambah data baru (mis. `hiro: {total, calls, puts, zerodte, retail, cumulative[]}`). Pertanyaan: tambah sebagai **field opsional non-breaking TANPA bump schema_version** (preseden: `ohlc` ditambah begitu) ATAU bump `schema_version`→2? Rekomendasi awal: opsional non-breaking (ikuti preseden `ohlc`), karena bump schema melanggar locked contract. **Tapi tunggu konfirmasi sebelum menyentuh `schema.py`/`snapshot.ts`.**

## 4. PEKERJAAN — URUT ROI (kerjakan yang AMAN dulu, otonom)

### A. AMAN & ADITIF (kerjakan sekarang, tanpa tunggu approval)
1. **Vanna + Charm di `black76.py`.** Tambah dua fungsi murni (Black-76: F sebagai underlying, tanpa q). Pakai N'(d1), d1/d2 yang sudah ada. Tambah unit test (bandingkan ke nilai numerik/finite-difference). Tidak mengubah output snapshot apa pun → tidak menyentuh kontrak. Ini fondasi untuk VEX/CHEX/Charm-Pressure (v3).
   - Rumus referensi (mega-riset §3B/§E): VEX=Σ vanna·exposure·M·F·(1%vol); CHEX=Σ charm·exposure·M·F·(1 hari). Charm 0DTE = afternoon drift.
2. **Percentile clip di engine `field.py` (Bagian 6G).** Riset: spike 0DTE tunggal jangan membakar skala. FE `lib/heatmap/field-2d.ts` sudah pakai `CLIP_PERCENTILE=0.98`; pastikan engine `field.py` konsisten (clip persentil 98, bukan max-abs murni) ATAU dokumentasikan kalau normalisasi memang di FE. Jangan ubah warna/anchor (locked). Verifikasi T-01..T-10 tetap hijau.
3. **`t_expiry_from_clock(ts)` (untuk Divergensi #3) — TANPA mengganti default.** Implementasikan fungsi jam-riil ke settlement (15:00/16:00 ET) sebagai opsi; default `DEFAULT_T_EXPIRY` tetap. Tambah test. Flip default tunggu approval #3.
4. **HIRO accumulator — MODUL ENGINE BARU, output terisolasi.** Buat `services/engine/src/engine/hiro.py`:
   - Konsumsi `trades.side`+`price`+`size` per-leg (perlu extend `historical._load_trades` untuk menyimpan signed per-trade, bukan cuma prefix-sum volume — buat jalur baru, jangan rusak `_cumulative_volume` yang dipakai TRACE).
   - Rumus inti (mega-riset B3): `HIRO_t = Σ_{trade k ≤ t} s_k · δ_k · q_k · m · F_k`, s_k=±1 dari aggressor side, δ_k=delta opsi (Black-76), m=multiplier, F_k=forward saat trade. Kumulatif sejak RTH open, reset harian. Breakdown: Total/Calls/Puts/0DTE/Retail (Retail boleh ditandai TODO/heuristik — proprietary).
   - **Output HIRO JANGAN dimasukkan ke Snapshot dulu** sampai keputusan #5 disetujui. Sediakan sebagai fungsi murni + test yang bisa dipanggil terpisah. Kalau perlu demo, tulis ke file JSON sampingan, bukan ke schema.
5. **Vol module (SVI surface + expected move) — `services/engine/src/engine/surface.py` (baru).** Reuse `iv.py` yang sudah ada. SVI raw per slice (5 param, arbitrage-free SSVI bila bisa). Expected move: `EM ≈ S·σ_ATM·√T` atau ≈ harga ATM straddle ×0.85. Output terisolasi (jangan masuk schema dulu). Tambah test.

### B. BERAT / PERLU KEPUTUSAN (JANGAN bangun — cukup tulis rekomendasi)
6. **DDOI engine (Bagian 6A).** Paling berat + proprietary + butuh kalibrasi vs ΔOI. Jangan implementasi; tulis rencana + risiko ke file rekomendasi (terkait Divergensi #1).
7. **Volatility Trigger / Hedge Wall / Risk Pivot / SG Acceleration / Absolute Gamma** — proprietary; ringkas pendekatan proxy di rekomendasi, jangan bangun tanpa approval.

## 5. OUTPUT YANG DIHARAPKAN SAAT USER BANGUN
1. Kode engine untuk item §4.A selesai & **semua test hijau** (engine + api: pytest, ruff, mypy). Di working tree, belum di-commit.
2. `Research/REKOMENDASI-keputusan.md` berisi 5 keputusan (§3) + item berat (§4.B): tiap satu dengan opsi A/B/C, rekomendasimu, dan tradeoff jelas — supaya user tinggal pilih.
3. Ringkasan singkat: apa yang SELESAI (aman) vs apa yang DIBLOKIR menunggu approval, plus daftar file yang disentuh.
4. Kalau schema akhirnya TIDAK disentuh (karena #5 menunggu), JSON sesi FE tidak perlu diregenerasi; sebut saja perlu regen setelah HIRO masuk schema.

## 6. CATATAN VALIDASI (dari riset)
GLBX-ES ≠ SpotGamma-SPX (semesta opsi beda). Level FlowDesk TIDAK akan match angka-per-angka vs SpotGamma. Validasi = **struktural** (arah rezim, urutan ordinal level, timing), bukan nilai absolut. Garis ungu/biru HIRO di mockup `1.png` = target HIRO ini (FE menyusul).

Mulai dari membaca 4 dokumen di §0, lalu kerjakan §4.A sambil menulis §3 ke file rekomendasi. Bekerjalah otonom; jangan berhenti di item aman hanya karena lama.
