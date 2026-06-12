# FlowDesk — Audit Red-Team & Harness Validasi (Fase 1 + Fase 2)

> 🔴 **Mode red-team:** dokumen ini mengaudit laporan riset FlowDesk dengan asumsi *ada kesalahan*. Tujuannya menemukan error, bukan mengonfirmasi. **Temuan error nyata: 1** (kontradiksi internal baris RTY) + 2 tag yang diturunkan. Laporan utama TIDAK ditulis ulang; hanya dikoreksi titik-titik yang terbukti salah.

> ⚠️ **Prompt injection ditemukan lagi & diabaikan:** beberapa halaman dok Databento (`schemas-and-data-formats/status`, `statistics`, `instrument-definitions`) memuat blok `[OBFUSCATED PROMPT INJECTION]` di menu. Diabaikan total; hanya konten teknis schema yang dipakai.

## 1. BLUF (Bottom Line Up Front)
- **Fase 1 — Fakta eksternal:** dari klaim material prioritas yang diuji ulang ke sumber primer, **mayoritas VERIFIED**. **Tidak ada FABRICATED-SOURCE** — keempat sitasi akademik nyata & angkanya cocok persis.
- **Error paling serius ditemukan:** baris **RTY** di tabel A.5 ("Tue/Thu") bertentangan dengan A.5.1 ("Mon–Fri"). Diselesaikan dengan sumber CME → RTY memang Mon–Fri (gabungan Mon/Wed + Tue/Thu + Friday). **SUDAH DIKOREKSI.**
- **Gate matematika (Fase 1→2): LULUS.** Vanna & charm Black-76 di-RE-DERIVE dan dicocokkan numerik vs finite-difference (~1e-8 s/d 1e-13). Item [UNCERTAIN] lama sudah dikunci. Parity & round-trip IV <1e-6.
- **Fase 2 — Verdict empiris: TIDAK ADA.** Tidak ada akses repo FlowDesk maupun data Databento /ES /NQ. Harness siap-jalan diserahkan + dijalankan pada data **sintetik** (uji pipa saja). **Tidak ada angka hasil empiris yang diklaim.**

## 2. FASE 1 — Verification Ledger
Verdict ∈ {VERIFIED, PARTIAL, UNVERIFIED, CONTRADICTED, FABRICATED-SOURCE}.

| Lokasi | Klaim | Apa kata sumber (kutip pendek) | Verdict | Koreksi |
|---|---|---|---|---|
| A.3.3 | Fixing = VWAP 30s terakhir s/d 16:00 ET, simbol ESF | CME Weekly/EOM FAQ: "VWAP in E-mini S&P 500 futures, traded during the 30-second period leading up to 3:00 p.m. CT ... 'ESF'" (3:00pm CT = 4:00pm ET) | VERIFIED | — |
| A.3.2 | Auto-exercise ITM ≥ 0.01 | CME RTY FAQ: "Any options that are at least 0.01 index point in the money will be exercised"; Schwab: ITM by $0.01 | VERIFIED | — |
| A.5 (RTY) | Tabel: RTY "Tue/Thu weekly European" | CME: ada Tue/Thu FAQ + Mon/Wed weeklies + Friday; IBKR: "Monday through Friday ... Russell 2000" | CONTRADICTED (internal vs A.5.1) | DIKOREKSI → "Mon–Fri (Mon/Wed + Tue/Thu + Friday)" |
| A.5 | ES $50/tick0.25=$12.50; NQ $20; RTY $50/0.10=$5.00 | RJO/CME: ES 1pt=$50, tick $12.50; CME course: RTY $50×index, 0.10=$5.00 | VERIFIED | — |
| B.3.3 / B.3.7 | `trades` & `tbbo` punya `side` B/A/N | Databento trades & tbbo schema: "side ... A sk for a sell aggressor ... B id for a buy aggressor ... N one" | VERIFIED | — |
| B.3.2 | `statistics` = OI + prelim/final settlement + OHL | Databento statistics: "daily volume, open interest, preliminary and final settlement prices, and official open, high, and low" | VERIFIED | — |
| B.3.1 | `instrument_id` reset/unik per hari | Dok hanya menyebut "numeric instrument ID"; tidak ada pernyataan eksplisit reset harian di sumber yang dibuka | PARTIAL/UNVERIFIED | Tag diturunkan ke [VERIFY]; remap harian via definition tetap aman |
| C.3–C.5 | Black-76 harga/delta(e^-rT)/gamma/vega | LME Black'76 + blackscholes Greeks; re-derive + FD cocok | VERIFIED (numerik) | — |
| C.6 | Vanna = −e^{−rT}φ(d1)d2/σ; charm bentuk eksak | Re-derive sendiri; FD match ~1e-10 (vanna), ~1e-8 (charm) | VERIFIED & LOCKED | [UNCERTAIN] dihapus; charm call = r·e^{−rT}N(d1)+e^{−rT}φ(d1)d2/(2T) |
| C.7 | SOFR ≈3.60%; r=ln(1+SOFR) | FRED SOFR 2026-06-09 = 3.60; Macrotrends "3.60% as of June 9, 2026"; konversi benar | VERIFIED | overnight vs term tetap [VERIFY] (C.7.4) |
| D.3.1 | GEX = Γ·Q·M·F²·0.01 (per 1% move, $) | Derivasi unit: Δdelta=Γ·(0.01F); hedge$=Δdelta·M·F=Γ·M·F²·0.01. Unit: (1/px)(px²)($/px)=$ ✓ | VERIFIED (derivasi) | — |
| D.4.3 | Buis et al., SSRN 4109301 / S0165188924000721 | SSRN abstract_id=4109301 cocok; JEDC vol 164 (2024) 104880, DOI 10.1016/j.jedc.2024.104880 | VERIFIED | — |
| E.2 | Ellis/Michaely/O'Hara: quote 76.4%, tick 77.66%, LR 81.05% (JFQA 2000 35(4) 529–551) | ResearchGate/RePEc: "76.4%, 77.66%, and 81.05%"; JFQA vol 35(4) 529–551, Dec 2000 | VERIFIED | — |
| E.2 | Theissen 2001: Lee/Ready 72.8% (JIFMIM 11(2) 147–165) | ScienceDirect S1042443100000482: "Lee/Ready method classifies 72.8%"; vol 11(2) 147–165 | VERIFIED | — |
| F.2 | Gatheral–Jacquier SVI arXiv:1204.0646 | arXiv:1204.0646 "Arbitrage-free SVI volatility surfaces", Gatheral & Jacquier, 2012 rev 2013 | VERIFIED | — |

### 2.1 Koreksi yang diterapkan ke laporan utama
1. **A.5 baris RTY** — "Tue/Thu" → "Mon–Fri (Mon/Wed + Tue/Thu + Friday weeklies)", dengan catatan koreksi inline.
2. **C.6 vanna/charm** — tag [UNCERTAIN] dihapus; bentuk eksak charm dikunci + catatan validasi numerik.
3. **B.3.1 instrument_id** — klaim "reset/unik per hari" diturunkan ke [VERIFY].

### 2.2 Sumber palsu (FABRICATED-SOURCE)
**TIDAK ADA.** Keempat sitasi akademik nyata, nomor/DOI mengarah ke paper yang benar, dan angka yang dikutip cocok dengan abstrak/teks sumber.

### 2.3 Hasil uji numerik greeks (dapat diaudit ulang)
Konvensi: F=futures, T tahun, r=ln(1.036)=0.0353671, φ/N = pdf/cdf normal. Skrip: `black76_validate.py`.

| Test case | Besaran | Analitik | Finite-difference | \|selisih\| |
|---|---|---|---|---|
| ATM 1DTE: F=5000 K=5000 T=0.002740 σ=0.20 | gamma | 7.6209387e-3 | 7.6208228e-3 | 1.2e-7 |
| idem | vanna (∂Δ/∂σ) | 1.0439642e-2 | 1.0439642e-2 | 9.5e-13 |
| idem | charm (∂Δ/∂t) | −3.6329123e-1 | −3.6329123e-1 | 3.8e-10 |
| idem | parity c−p vs e^{−rT}(F−K) | 0 | 0 | 0 |
| idem | round-trip IV (input 0.20) | 0.20000000 | via Newton | 0 |
| OTM 1DTE: F=5000 K=5050 (d2≠0) | vanna | 1.2194060e+0 | 1.2194060e+0 | 2.4e-10 |
| idem | charm | −4.4502225e+1 | −4.4502225e+1 | 1.7e-8 |
| ITM 0.5DTE /NQ: F=18000 K=17900 σ=0.25 | vanna | −7.9309523e-1 | −7.9309523e-1 | 7.7e-10 |

**Greek Black-76 yang dikunci (referensi implementasi):**
```
d1=(ln(F/K)+½σ²T)/(σ√T), d2=d1−σ√T
Δ_call=e^{−rT}N(d1), Δ_put=−e^{−rT}N(−d1)
Γ=e^{−rT}φ(d1)/(Fσ√T), Vega=Fe^{−rT}φ(d1)√T
Vanna=−e^{−rT}φ(d1)d2/σ (call=put)
Charm_call=∂Δ/∂t=r·e^{−rT}N(d1)+e^{−rT}φ(d1)d2/(2T); Charm_put=Charm_call−r·e^{−rT}
```

> **GATE FASE 1→2: LULUS.** Matematika greeks (vanna/charm) & derivasi GEX terkunci dan cocok numerik; tidak ada FABRICATED-SOURCE; error internal RTY diperbaiki.

## 3. FASE 2 — Status Validasi Empiris

> 🚫 **Tidak ada akses ke repo FlowDesk (`exposure.py`, `black76`, `feed/live.py`, schema snapshot) maupun data Databento /ES /NQ 90 hari.** Karena itu TIDAK ADA verdict empiris. Yang diserahkan: (a) harness siap-jalan, (b) rencana eksekusi, (c) bukti harness berjalan pada data **sintetik** (uji pipa belaka). Angka sintetik di bawah **bukan** validasi produk.

### 3.1 Tabel metrik per-hipotesis (status)

| Lapis / Hipotesis | Metrik | Kriteria LULUS | Status pada data NYATA |
|---|---|---|---|
| Lapis 1 — rekonsiliasi ΔOI | sign-agreement, Spearman IC, weighted-dir-error | OOS sign≥60% & Spearman≥0.2 (p<0.05) | PENDING — butuh `statistics` Databento |
| Lapis 2 — H1 pinning | \|close−wall\|/ATR pos vs neg gamma + block bootstrap | p_FDR<0.05 OOS & CI tak memuat baseline | PENDING — butuh bar 1-min + walls |
| Lapis 2 — H2 reaksi level | hit-rate bounce vs random/persistence/VWAP-revert | CI bootstrap di atas baseline | PENDING |
| Lapis 2 — H3 regime vol | RV di atas vs di bawah gamma-flip | p_FDR<0.05 OOS | PENDING |
| Lapis 3 — golden | parity, FD-bump, round-trip IV, determinisme, invarian | semua <toleransi | SEBAGIAN LULUS (parity/FD/IV sudah; determinisme/invarian butuh kode engine) |

### 3.2 Bukti harness berjalan (SINTETIK — bukan hasil produk)
Menjalankan `flowdesk_validation_harness.py --source synthetic` sukses end-to-end: Lapis 1 menghasilkan sign-agreement ~0.62 (MARGINAL) dan Lapis 2-H1 "FAIL/INCONCLUSIVE". **Angka ini artefak generator sintetik** (mis. net-gamma sintetik tak pernah positif) dan sengaja TIDAK ditafsirkan sebagai kebenaran /ES /NQ. Fungsinya hanya membuktikan pipa + statistik (Spearman, Benjamini-Hochberg FDR, block bootstrap) tereksekusi tanpa dependensi scipy.

### 3.3 Rencana eksekusi (saat akses tersedia)
1. Ganti `load_synthetic` dengan loader Databento (`definition`, `statistics`, `trades`, `bbo-1m`), RTH, 90 hari, /ES /NQ; resolusi instrument_id↔kontrak per hari.
2. Verifikasi **granularitas ΔOI per-strike harian** benar-benar ada (prasyarat; jika tidak, Lapis 1 gugur — laporkan apa adanya).
3. Walk-forward 60/30, threshold dikalibrasi HANYA di in-sample.
4. Jalankan Lapis 1–3; keluarkan tabel metrik + grafik (event-study, distribusi jarak-ke-wall, scatter Δsintetik vs ΔOI, HIRO vs harga); simpan seed/split/parameter.
5. Sertakan biaya tick saat menilai "tradeable"; **pisahkan signifikansi statistik vs ekonomi**.

## 4. Divergensi KODE vs DOKUMEN (2.0)

> ❓ **UNVERIFIED — tidak dapat dinilai.** Tanpa akses repo, klaim laporan tentang `exposure.py` (DEALER_SIGN_CALL=+1/PUT=−1, VOL kumulatif sejak RTH), `schema_version=1`, `black76`/greeks, dan `feed/live.py` (stub) **tidak bisa dibandingkan dengan kode aktual**. Ini tetap GAP terbuka, bukan "cocok". Saat repo tersedia: jalankan `black76_validate.py` terhadap modul greeks asli & diff konstanta tanda + basis VOL.

## 5. Verdict Akhir (tiga kategori)

| Kategori | Verdict | Dasar |
|---|---|---|
| (a) Benar secara matematis | **TERBUKTI** (Black-76 greeks, vanna/charm, GEX-factor, parity, IV) | Re-derive + FD numerik <1e-8; derivasi unit GEX; §2.3 |
| (b) Benar secara empiris (produk di /ES /NQ) | **BELUM DIUJI** (bukan terbukti, bukan disanggah) | Tidak ada data/repo; harness diserahkan, hanya jalan sintetik |
| (c) Masih GAP | Empiris Lapis 1–2; divergensi kode–dokumen; biaya ingest; granularitas ΔOI; SOFR overnight/term | §3.1, §4, daftar [VERIFY] |

## 6. Revised Confidence & Gap Terpenting
- **Fondasi matematika/data:** keyakinan **TINGGI** (naik) — greeks terkunci numerik, sumber & sitasi terverifikasi, satu kontradiksi internal diperbaiki.
- **Kebenaran produk (prediktif):** keyakinan **TIDAK DAPAT DINYATAKAN** — tetap pada level "plausibly correct". Tidak boleh disebut "terbukti".
- **Gap #1 (paling penting):** akses data Databento + repo untuk menjalankan Lapis 1 (rekonsiliasi ΔOI). Tanpa ini, seluruh klaim arah-dealer FlowDesk belum berdiri di atas bukti.
- **Gap #2:** verifikasi granularitas ΔOI per-strike; jika tidak tersedia, Lapis 1 harus didesain ulang.
- **Gap #3:** divergensi kode vs dokumen belum bisa dinilai.

*Tidak ada rekomendasi di halaman ini yang mengubah LOCKED CONTRACT. Semua usulan bersifat aditif atau berupa uji.*
