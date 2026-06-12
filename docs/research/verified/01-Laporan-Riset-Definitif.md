# FlowDesk — Laporan Riset Definitif (0DTE Futures Options GEX Terminal)

> 🧭 Laporan riset teknis tingkat institusional untuk **FlowDesk** — terminal real-time GEX/DEX/dealer-positioning untuk 0DTE options on futures (fokus /ES & /NQ, data Databento GLBX.MDP3, pricing Black-76).
> **Tanggal akses sumber:** 12 Juni 2026. **Metodologi:** tiap klaim faktual diberi tag keyakinan — [CONFIRMED: sumber], [INFERRED: alasan], [UNCERTAIN/VERIFY: yang perlu dicek]. Spec bursa dapat berubah; verifikasi ulang sebelum go-live.

> ⚠️ **Catatan integritas sumber:** Saat riset, satu hasil pencarian (PDF "SVI Model Free Wings" di hal.science) memuat upaya *prompt injection*. Konten itu diabaikan total. Paper SVI yang dipakai adalah Gatheral–Jacquier (arXiv:1204.0646), sumber primer yang sah.

> 🔒 **LOCKED CONTRACT** (tidak diubah tanpa label eksplisit "USULAN PERUBAHAN KONTRAK"): /ES M=$50 step5; /NQ M=$20 step10; RTH 09:30–16:00 ET 1-min, replay 90 hari; Black-76; r=ln(1+SOFR); IV-mid Newton→bisection tol 1e-6; dealer long-call/short-put (CALL=+1, PUT=−1); GEX=gamma·VOL·M·F²·0.01 (basis VOL kumulatif sejak RTH); walls=gamma-$ Top-3; day-count real wall-clock ke 16:00 ET; HIRO optional; schema_version=1; Discord OAuth (identify, guilds.members.read) + DESK_ROLE_ID gate.

## Ringkasan Eksekutif Global
FlowDesk secara arsitektur sudah benar pada fondasi (Black-76 untuk options-on-futures, basis Databento GLBX.MDP3, GEX dollar-gamma). Temuan terpenting:
1. **Black-76 adalah pilihan yang tepat dan tervalidasi** untuk options on futures /ES & /NQ — bukan Black-Scholes spot. [CONFIRMED]
2. **Kontradiksi tbbo vs trades.side TERSELESAIKAN:** schema `trades` Databento sudah memuat field `side` (B/A/N = aggressor) yang identik semantiknya dengan `tbbo`. Keputusan #4 (pakai `trades`, tanpa `tbbo`) konsisten dan lebih murah. [CONFIRMED]
3. **GAP terbesar tetap validasi.** Tanpa harness rekonsiliasi VOL-GEX/DDOI vs delta-OI resmi (`statistics`) dan uji prediktif berkontrol, angka GEX tidak terbukti benar — hanya "self-consistent". Track G memberi desain harness implementable.
4. **Metodologi VOL-kumulatif + tanda statis punya bias struktural** (aggressor ≠ customer; double-count round-trip; tanpa decay). DDOI (Track D) adalah layer paralel measurable — prioritas v3.
5. **GLBX ≠ SPX vendor:** /ES & /NQ futures-settled, multiplier $50/$20, underlying = harga futures; SPX/NDX index cash-settled multiplier $100. Angka GEX TIDAK cocok angka-per-angka dgn vendor SPX. Validasi harus **struktural**. [INFERRED+CONFIRMED]

---
# TRACK A — 0DTE Futures Options: Mekanika & Universe Instrumen
## A.1 Ringkasan
0DTE = opsi pada hari yang sama dengan expiry-nya. Pada CME dimungkinkan oleh **daily expirations (Senin–Jumat)** untuk opsi pada futures equity index utama (ES, NQ, RTY). Futures-settled, gaya Eropa untuk weekly/daily; gamma meledak saat T→0. [CONFIRMED: CME S&P futures product page; CME NQ Weekly specs]
## A.2 0DTE options on futures vs index/ETF
- **A.2.1** Options on futures: underlying = kontrak futures (mis. ESM6). Harga teoretis pakai forward = harga futures, didiskon Black-76. [CONFIRMED]
- **A.2.2** Options on index (SPX/NDX): underlying indeks tunai, cash-settled, multiplier $100, Eropa. ETF (SPY/QQQ): fisik, Amerika, multiplier 100.
- **A.2.3** Implikasi FlowDesk: delta/gamma dihitung terhadap F (futures price), bukan spot. Sudah benar. [INFERRED]
## A.3 Expiry, Settlement, Exercise Style
- **A.3.1** Weekly & EOM ES/NQ = European-style; American hanya quarterly klasik. [CONFIRMED]
- **A.3.2** Settlement: exercise → posisi futures cash-settled; ITM pada hari terakhir auto-exercised. Threshold ITM ≥ 0.01 index point. [CONFIRMED]
- **A.3.3** Fixing = **VWAP futures 30 detik terakhir 3:59:30–4:00:00 p.m. ET** (2:59:30–3:00:00 CT), simbol **ESF**/**NQF**. Hanya outright trades. [CONFIRMED]
- **A.3.4** Day-count real wall-clock ke 16:00 ET konsisten dgn mekanika expiry. [CONFIRMED]
## A.4 Mengapa fenomena gamma 0DTE muncul
- **A.4.1** T→0 → gamma ATM → ∞ → dealer re-hedge agresif.
- **A.4.2** Dealer long gamma → stabilkan; short gamma → perkuat tren. [CONFIRMED]
- **A.4.3** Pertumbuhan 0DTE >150% (2020–2025) dikaitkan supresi realized vol intraday. [CONFIRMED]
## A.5 Universe Instrumen — Tabel Master Spec
Semua diakses 12 Jun 2026.

| Produk | Underlying | Multiplier | Tick futures | Opsi harian? | Settlement | Catatan 0DTE |
|---|---|---|---|---|---|---|
| /ES E-mini S&P 500 | S&P 500 fut | $50 | 0.25 = $12.50 | Ya, Mon–Fri | Futures-settled → cash | Inti FlowDesk; step 5 (locked) |
| /NQ E-mini Nasdaq-100 | Nasdaq-100 fut | $20 | 0.25 = $5.00 | Ya, Mon–Fri | Futures-settled → cash | Inti FlowDesk; step 10 (locked) |
| /RTY E-mini Russell 2000 | Russell 2000 fut | $50 | 0.10 = $5.00 | Ya, Mon–Fri (Mon/Wed + Tue/Thu + Friday weeklies) | Futures-settled → cash | Ekspansi prioritas 1. [DIKOREKSI 12-Jun-2026: sebelumnya "Tue/Thu" — bertentangan A.5.1; CME konfirmasi efektif Mon–Fri] |
| /YM E-mini Dow | DJIA fut | $5 | 1.0 = $5.00 | Sebagian (weekly) | Futures-settled → cash | Likuiditas opsi lebih tipis |
| MES/MNQ/M2K/MYM (micros) | idem index | $5/$2/$5/$0.50 | — | Opsi micro terbatas | Futures-settled → cash | OI/likuiditas tipis; kurang ideal GEX |
| /CL WTI Crude | WTI fut | $1,000 | 0.01 = $10 | Weekly (LO) | Futures-settled (fisik) | Dinamika dealer beda |
| /GC Gold (OG opsi) | Gold fut | $100 | 0.10 = $10 | Weekly; expire 12:30 CT | Futures-settled | Likuiditas 0DTE rendah |
| /ZN 10Y T-Note | 10Y note fut | $1,000 per pt | 1/64 | 3×/minggu (Mon/Wed/Fri) | Futures-settled | Tick fraksional |

- **A.5.1** Daily (Mon–Fri) terkonfirmasi untuk **ES, NQ, RTY**. [CONFIRMED: IBKR]
- **A.5.2** ZN tiga expiry mingguan (Mon/Wed/Fri) — bukan harian penuh. [CONFIRMED]
- **A.5.3** CL satu-satunya weekly crude options likuid; bukan daily. [CONFIRMED]
- **A.5.4** Seluruh produk tercakup GLBX.MDP3. [CONFIRMED: Databento]
## A.6 /ES & /NQ vs SPX/NDX
- **A.6.1** Multiplier beda (ES=$50, NQ=$20 vs SPX=$100). [CONFIRMED]
- **A.6.2** Underlying beda: futures price (basis/carry) vs index cash. [INFERRED]
- **A.6.3** Pool OI berbeda → walls/flip di level berbeda. [INFERRED]
- **A.6.4** Validasi harus struktural, bukan $GEX absolut vs vendor SPX. [INFERRED — dasar Track G]
## A.7 Pemetaan ke FlowDesk

| Temuan | Status | Rekomendasi + Prioritas |
|---|---|---|
| ES $50/step5, NQ $20/step10, futures-settled European | Cocok (locked) | Pertahankan. P0 |
| Fixing 16:00 ET (ESF/NQF VWAP 30s) | Cocok | Pakai 16:00 ET sebagai T=0. P1 |
| RTY daily tersedia | Hilang | Ekspansi #1: tambah RTY. P2 |
| Micros & CL/GC/ZN | Hilang | Tunda. P3 |
| GLBX ≠ SPX vendor | Risiko salah-validasi | Validasi struktural (Track G). P1 |

## A.9 Pertanyaan Terbuka
- A.9.1 [VERIFY] Strike step persis daily ES (5) & NQ (10) dari definition schema GLBX.
- A.9.2 [VERIFY] RTY daily step = 10 & tick 0.10 untuk semua seri.
- A.9.3 [VERIFY] Kalender holiday/half-day yang menggeser fixing 16:00 ET.

---
# TRACK B — Databento GLBX.MDP3 Schema
## B.1 Ringkasan
GLBX.MDP3 = normalisasi feed CME Globex MDP 3.0. Schema minimum cukup: **definition** (instrument_id↔kontrak, strike, tipe, expiry, multiplier), **mbp-1 atau bbo-1m** (mid→IV), **statistics** (OI & settlement→walls/validasi), **trades** (aggressor side→HIRO & basis VOL-GEX). tbbo/mbp-10/bbo-1s opsional. [CONFIRMED]
## B.2 Timestamps
- `ts_recv` = waktu capture; `ts_event` = matching-engine (Tag 60), presisi ns. [CONFIRMED]
- Harga fixed-point (skala 1e-9 DBN). [CONFIRMED]
## B.3 Schema per-schema
- **B.3.1 definition:** instrument_id, raw_symbol, tipe (CALL/PUT/future), strike_price, expiration, underlying, multiplier, min tick. Wajib. [CONFIRMED] *(Audit: klaim "instrument_id reset/unik per hari" diturunkan ke [VERIFY] — remap harian via definition tetap aman.)*
- **B.3.2 statistics:** daily volume, **open interest**, prelim & final **settlement**, official OHL. Wajib untuk OI, settlement, **delta-OI resmi keesokan hari** (jantung Track G). [CONFIRMED]
- **B.3.3 trades:** `side` A=sell aggr, B=buy aggr, N=none; + price, size, ts_event, instrument_id, action=T. Wajib HIRO & VOL. [CONFIRMED]
- **B.3.4 mbp-1:** bid/ask px+sz level 0. Utama untuk mid→IV. [CONFIRMED]
- **B.3.5 mbp-10:** 10 level book. Opsional (tak perlu GEX). [INFERRED]
- **B.3.6 bbo-1m/1s:** snapshot BBO interval time-space. **bbo-1m cocok** cadence 1-menit FlowDesk. [CONFIRMED]
- **B.3.7 tbbo:** BBO saat trade (trade space); action=T; side + snapshot bid/ask. [CONFIRMED]
- **B.3.8 ohlcv:** bar agregat; ts_event=awal interval. [CONFIRMED]
- **B.3.9 cbbo/cmbp-1/tcbbo:** konsolidasi; tak relevan single-venue. [INFERRED]
## B.4 Derivabilitas (hemat biaya)
MBP-1 → BBO/TBBO/Trades. Ambil `trades`+`bbo-1m` langsung lebih murah daripada full book. [CONFIRMED]
## B.5 Kecukupan schema untuk GEX
- IV/mid: bbo-1m. gamma/delta: F(futures)+K,T(definition)+σ+r. OI walls: statistics. HIRO: trades.side. forward: futures price langsung. Semua cukup. [CONFIRMED]
## B.6 KONTRADIKSI: tbbo+bbo-1m (riset lama) vs trades.side tanpa tbbo (#4)
- **B.6.1** `trades` & `tbbo` sama-sama punya `side` semantik identik (A/B/N). [CONFIRMED]
- **B.6.2** `tbbo` menambah snapshot BBO saat trade → memungkinkan Lee-Ready/quote-based. `trades` tak bawa quote.
- **B.6.3** trades-saja: lebih murah, side CME dari matching engine (andal). tbbo: bisa audit kualitas side, tapi mahal & redundan untuk mid.
- **B.6.4 REKOMENDASI:** **Pertahankan #4** (trades.side). Tambah `tbbo` HANYA sbg dataset validasi sampel (beberapa hari) untuk ukur fraksi side=N. [INFERRED]
## B.7 Biaya & rate-limit ingest
- **B.7.1** Databento ditagih per volume; schema ramping (trades+bbo-1m+statistics+definition) jauh lebih murah dari mbp-10/tbbo. [CONFIRMED arah; VERIFY angka $]
- **B.7.2** 2 instrumen × 90 hari RTH 1-menit volume kecil; bottleneck = trades tick untuk HIRO. [INFERRED]
## B.8 Pemetaan ke FlowDesk

| Temuan | Status | Rekomendasi + Prioritas |
|---|---|---|
| trades.side cukup (tanpa tbbo) | Cocok (#4) | Pertahankan; tbbo hanya sampel. P1 |
| bbo-1m ideal mid 1-menit | Feed masih stub | Wiring bbo-1m untuk IV. P1 |
| statistics = OI+settlement+delta-OI | Belum dipakai validasi | Ingest harian untuk harness G. P0 |
| definition = instrument_id, strike, multiplier | Diperlukan | Snapshot definition harian. P0 |
| mbp-10/tbbo penuh | Tidak dipakai | Jangan ingest produksi. P3 |

## B.10 Pertanyaan Terbuka
- B.10.1 [VERIFY] StatType persis di statistics untuk OI & final settlement GLBX.
- B.10.2 [VERIFY] Fraksi trades side=N pada opsi ES/NQ 0DTE.
- B.10.3 [VERIFY] Stabilitas instrument_id lintas hari (remap via definition).
- B.10.4 [VERIFY] Harga ingest historis aktual trades opsi 90 hari.

---
# TRACK C — Pricing & Greeks (Black-76)
## C.1 Ringkasan
Black-76 memodelkan forward/futures log-normal, diskon e^{−rT}. Forward = harga futures F. Semua greek (delta, gamma, vega, theta, vanna, charm) bentuk tertutup. r=ln(1+SOFR) → rate kontinu. [CONFIRMED]
## C.2 Notasi
d1 = [ln(F/K)+½σ²T]/(σ√T); d2 = d1 − σ√T. [CONFIRMED]
## C.3 Harga
- Call: c = e^{−rT}[F·Φ(d1) − K·Φ(d2)]
- Put: p = e^{−rT}[K·Φ(−d2) − F·Φ(−d1)] [CONFIRMED]
## C.4 Delta (terhadap F)
- Δ_call = e^{−rT}·Φ(d1); Δ_put = −e^{−rT}·Φ(−d1). Ada discount factor e^{−rT} (beda BS spot). [CONFIRMED]
## C.5 Gamma
- Γ = e^{−rT}·φ(d1)/(F·σ·√T). Sama call & put. [CONFIRMED]
- **C.5.1** T→0 → Γ_ATM→∞. Floor T & cap Γ. [INFERRED]
## C.6 Vega, Theta, Vanna, Charm
- Vega = F·e^{−rT}·φ(d1)·√T. [CONFIRMED]
- Theta: bentuk lengkap dari referensi, hati-hati tanda; per-hari /365. [CONFIRMED]
- **Vanna** = ∂Δ/∂σ = −e^{−rT}·φ(d1)·d2/σ (call=put). [CONFIRMED & LOCKED 12-Jun-2026: cocok FD ~1e-10]
- **Charm** = ∂Δ/∂t = r·e^{−rT}·N(d1) + e^{−rT}·φ(d1)·d2/(2T) (call); put kurangi r·e^{−rT}. [CONFIRMED & LOCKED 12-Jun-2026: cocok FD ~1e-8]
## C.7 Rate r = ln(1+SOFR)
- **C.7.1** SOFR overnight ≈3.60% per 9 Jun 2026. [CONFIRMED]
- **C.7.2** r=ln(1+SOFR) → continuously-compounded konsisten e^{−rT}. [CONFIRMED]
- **C.7.3** 0DTE: pengaruh r minimal tapi tetap benar dipakai. [INFERRED]
- **C.7.4** [VERIFY] overnight vs Term SOFR — untuk T<1 hari overnight paling tepat.
## C.8 IV dari mid: Newton → bisection
- Newton dgn vega; fallback bisection saat vega→0; tol 1e-6 + max-iter + guard; floor/cap σ; skip strike bila mid<intrinsic. [CONFIRMED]
## C.9 Validasi test cases
- Uji vs QuantLib/MATLAB; parity c−p=e^{−rT}(F−K)<1e-6; FD-bump; round-trip IV. [CONFIRMED+INFERRED]
## C.10 Pemetaan ke FlowDesk

| Temuan | Status | Rekomendasi + Prioritas |
|---|---|---|
| Black-76 + forward=F | Cocok (locked) | Pertahankan. P0 |
| r=ln(1+SOFR) | Cocok | Verifikasi overnight SOFR. P2 |
| Newton→bisection tol 1e-6 | Cocok (locked) | Guard vega→0, floor/cap σ, max-iter. P1 |
| Gamma T→0 meledak | Risiko numerik | Floor T & cap Γ. P1 |
| Vanna/charm | Di luar Snapshot | Unit-test tanda lalu field opsional. P2 |
| Golden tests | Terbatas | Tambah parity+FD-bump+round-trip IV. P1 |

## C.12 Pertanyaan Terbuka
- C.12.1 [VERIFY] (DITUTUP 12-Jun) Bentuk eksak & tanda vanna/charm — sudah dikunci via validasi numerik.
- C.12.2 [VERIFY] Sumber SOFR (overnight vs term) & jadwal update.
- C.12.3 [VERIFY] Kebijakan T floor dekat 16:00 ET.

---
# TRACK D — Dealer Positioning Theory (GEX/DEX/DDOI)
## D.1 Ringkasan
GEX = jumlah hedging dolar per pergerakan underlying. Asumsi dealer long-call/short-put = aproksimasi praktisi, valid level indeks. GEX-VOL = proxy cepat; **DDOI** (SqueezeMetrics) lebih benar teoretis (rekonstruksi arah dari signed flow, diverifikasi ΔOI). [CONFIRMED]
## D.2 Asumsi dealer long-call/short-put
- Valid "to some extent on an index level". Tidak valid saat ritel jual call masif atau call-buying frenzy single-stock. Untuk /ES /NQ customer net buyer of puts → dealer short put. DEALER_SIGN_CALL=+1, PUT=−1 default wajar tapi sumber bias yang DDOI perbaiki. [CONFIRMED]
## D.3 Formula inti
- **D.3.1 GEX per opsi:** ≈ Γ × OI × M × F² × 0.01. FlowDesk pakai VOL gantikan OI + tanda dealer. [CONFIRMED]
- **D.3.2 DEX:** Σ (sign × Δ × Q × M × F). [CONFIRMED]
- **D.3.3 Gamma flip:** harga di mana net dealer gamma ganti tanda. Atas flip = stabil; bawah = tak stabil. [CONFIRMED]
- **D.3.4 Walls:** strike |dollar gamma| terbesar; gamma-$ Top-3 (locked). [CONFIRMED]
## D.4 Regime gamma
- Positif → redam volatilitas (range/pin); Negatif → perkuat tren. [CONFIRMED]
- **D.4.3** Buis et al. (2023) "Gamma Positioning and Market Quality": positive gamma turunkan vol; negative naikkan. [CONFIRMED: SSRN 4109301; S0165188924000721]
## D.5 KRITIK VOL-kumulatif + tanda statis
- **D.5.1** Aggressor ≠ customer; tanda statis bisa salah arah. [CONFIRMED]
- **D.5.2** Double-count round-trip menggelembungkan eksposur. [INFERRED]
- **D.5.3** No decay/no expiry unwind sampai reset harian. [INFERRED]
- **D.5.4** Sensitif klasifikasi: salah dealer-sign membalik kontribusi strike. [INFERRED]
## D.6 Rancangan DDOI (layer paralel, MEASURABLE)
- DDOI = arah dealer net per (expiry,strike,tipe) dari signed flow, diverifikasi ΔOI keesokan hari. Algoritma: klasifikasi trade → bin open/close → akumulasi posisi sintetik → verifikasi vs ΔOI resmi. Status: ditunda v3 (#1). [CONFIRMED]
## D.7 Pemetaan ke FlowDesk

| Temuan | Status | Rekomendasi + Prioritas |
|---|---|---|
| GEX = Γ·Q·M·F²·0.01 | Cocok (locked, VOL) | Pertahankan; VOL default v1. P0 |
| Dealer long-call/short-put | Cocok (locked) | Dokumentasikan sbg aproksimasi. P1 |
| Walls gamma-$ Top-3 | Cocok (#2) | Tambah cross-check OI-wall. P2 |
| Bias VOL-kumulatif | Divergen dari ideal | Bangun DDOI paralel v3 + ukur. P2 |
| Gamma flip & regime | Cocok | Validasi prediktif (Track G). P1 |

## D.9 Pertanyaan Terbuka
- D.9.1 [VERIFY] Rasio open/close empiris untuk binning DDOI.
- D.9.2 [VERIFY] Apakah dealer short-put bertahan pada hari put-selling overlay.
- D.9.3 [VERIFY] Sensitivitas lokasi flip terhadap VOL vs OI vs DDOI.

---
# TRACK E — Order Flow & HIRO
## E.1 Ringkasan
HIRO (SpotGamma) estimasi dampak hedging dealer dari tiap trade opsi, dijumlahkan sepanjang hari. FlowDesk dari trades.side (B/A/N) — sah karena CME publish aggressor di matching-engine. Alternatif (tick rule, Lee-Ready) akurasi ~72–81%. [CONFIRMED]
## E.2 Aggressor side
- **E.2.1** trades.side: A=sell, B=buy, N=none. Bukan inferensi. Paling andal. [CONFIRMED]
- **E.2.2** Tick rule ~77.66% (Nasdaq). [CONFIRMED: Ellis/Michaely/O'Hara]
- **E.2.3** Lee-Ready (1991) ~72.8–81%. [CONFIRMED: Theissen 72.8%]
- **E.2.4** Quote-based/midpoint. [CONFIRMED]
- **E.2.5** Karena side venue tersedia, fallback hanya untuk side=N. [INFERRED]
## E.3 Formula HIRO
- **E.3.1** HIRO = Σ s·Δ·q·M·F, s=+1 (buy aggr)/−1 (sell aggr). [CONFIRMED konseptual]
- **E.3.2** Konvensi tanda = dampak hedge dealer (bukan arah customer). [INFERRED]
- **E.3.3** Dekomposisi calls/puts, 0DTE vs longer, estimasi retail. [CONFIRMED]
## E.4 Validasi HIRO
- Korelasikan kumulatif HIRO intraday vs return /ES /NQ (event study saat HIRO flip); ukur fraksi side=N; windowing flow-alert. [CONFIRMED+INFERRED]
## E.5 Pemetaan ke FlowDesk

| Temuan | Status | Rekomendasi + Prioritas |
|---|---|---|
| HIRO dari trades.side | Cocok (#4) | Konvensi tanda = hedge dealer. P1 |
| HIRO optional field | Cocok (#5) | Tetap optional. P2 |
| Fraksi side=N | Belum diukur | Ukur; fallback Lee-Ready via tbbo sampel. P2 |
| Dekomposisi 0DTE/calls/puts | Sebagian | Tambah toggle next-expiry & calls/puts. P3 |
| Validasi HIRO vs harga | Hilang | Event study (Track G). P1 |

## E.7 Pertanyaan Terbuka
- E.7.1 [VERIFY] Akurasi side CME vs benchmark independen (N di blok/spread).
- E.7.2 [VERIFY] Penanganan multi-leg/spread trades di HIRO.
- E.7.3 [VERIFY] Korelasi empiris HIRO→return /ES /NQ 90 hari.

---
# TRACK F — Vol Surface, Expected Move, Vanna/Charm Exposure
## F.1 Ringkasan
SVI (Gatheral) parameterisasi smile; versi arbitrage-free (Gatheral–Jacquier 2012/2013). Expected move dari ATM straddle/IV. VEX/CHEX = sensitivitas delta dealer terhadap IV & waktu. Integrasi Snapshot sbg field opsional. [CONFIRMED]
## F.2 SVI untuk 0DTE
- Raw SVI: w(k)=a+b{ρ(k−m)+√[(k−m)²+σ²]}. Arbitrage-free g(k)≥0. 0DTE strike sedikit → pertimbangkan quadratic/regularisasi. [CONFIRMED+INFERRED]
## F.3 Expected Move
- EM ≈ ATM straddle, atau F·σ_ATM·√T. Update tiap menit untuk 0DTE. [CONFIRMED+INFERRED]
## F.4 VEX & CHEX
- VEX: Σ sign·vanna·Q·M. IV turun (post-FOMC) → vol-compression rally. [CONFIRMED]
- CHEX: Σ sign·charm·Q·M; charm besar menjelang 16:00 ET → end-of-day pin. [CONFIRMED]
## F.5 Integrasi Snapshot
- Tambah vex/chex/expected_move/surface_iv sbg field opsional schema_version berikut (additive). surface.py panggil dari engine setelah IV per-strike. [INFERRED]
## F.6 Sticky-strike vs sticky-delta
- Default sticky-strike (lebih sederhana intraday short-dated), dokumentasikan. [CONFIRMED+INFERRED]
## F.7 Pemetaan ke FlowDesk

| Temuan | Status | Rekomendasi + Prioritas |
|---|---|---|
| SVI arbitrage-free | surface.py terisolasi | Wiring ke engine; regularisasi 0DTE. P2 |
| Vanna/charm (VEX/CHEX) | Di luar Snapshot | Field opsional schema_version+1. P2 |
| Expected move | Cek | Tambah EM dari ATM straddle. P3 |
| Sticky-strike | Implisit | Dokumentasikan default. P3 |

## F.9 Pertanyaan Terbuka
- F.9.1 [VERIFY] Parameterisasi terbaik smile 0DTE (SVI vs quadratic vs SABR).
- F.9.2 [VERIFY] Sticky-strike vs sticky-delta empiris ES/NQ.
- F.9.3 [VERIFY] (DITUTUP) Bentuk eksak vanna/charm.

---
# TRACK G — Validasi & Backtesting (GAP TERBESAR)
## G.1 Ringkasan
FlowDesk baru punya self-consistency (golden internal). Harness 3 lapis: **(G.4)** rekonsiliasi posisi dealer sintetik vs delta-OI resmi; **(G.5)** uji prediktif struktur GEX vs harga + kontrol multiple-testing; **(G.6)** golden test. Karena GLBX≠SPX, validasi **struktural**. [INFERRED+CONFIRMED]
## G.2 Data & desain
- 90 hari RTH 1-menit /ES /NQ. Sumber bbo-1m, trades, statistics, definition. Walk-forward **60 in-sample / 30 OOS**; threshold tak pernah dipilih di test. Look-ahead guard: OI(T) ex-post. [CONFIRMED+INFERRED]
## G.3 Baselines (wajib)
- Random/permutation (wall acak), naive persistence, VWAP-revert. Tanpa baseline hit-rate tak bermakna. [INFERRED]
## G.4 Lapis 1 — Rekonsiliasi vs delta-OI resmi
- Tujuan: arah posisi dealer sintetik konsisten dgn ΔOI = OI(T)−OI(T−1) per strike/tipe.
- Metrik: **sign-agreement** (baseline acak 50%), **Spearman rank IC**, **weighted directional error**.
- LULUS bila OOS sign≥60% **dan** Spearman≥0.2 (p<0.05). MARGINAL 55–60%. GAGAL <55%. DDOI "lebih baik" via McNemar. [CONFIRMED+INFERRED]
## G.5 Lapis 2 — Uji prediktif
- **H1 (Pinning):** gamma-positif → close tertarik ke wall vs gamma-negatif.
- **H2 (Reaksi level):** sentuhan wall lebih sering memantul vs level acak.
- **H3 (Regime vol):** RV lebih rendah di atas gamma-flip.
- Metrik: |close−wall|/ATR (t-test/Mann-Whitney), hit-rate bounce (binomial), event study ±15 menit, IC.
- Kontrol: **Benjamini-Hochberg FDR**, **block bootstrap** per-hari, pra-registrasi hipotesis.
- LULUS bila p_FDR<0.05 OOS & CI bootstrap tak memuat baseline. Jika gagal: laporkan (Global Rule #4). Sertakan biaya tick; pisahkan signifikansi statistik vs ekonomi. [INFERRED]
## G.6 Lapis 3 — Golden
- Pertahankan parity/FD-bump CI. Golden TIDAK membuktikan kebenaran ekonomi. Tambahan: determinisme (replay byte-identical), invarian (Σ per-strike=agregat), monotonisitas gamma vs T. [INFERRED]
## G.7 Output harness
- Report metrik + status LULUS/MARGINAL/GAGAL; grafik event-study/distribusi/scatter/HIRO; artefak audit (param/split/seed). [INFERRED]
## G.8 Pemetaan ke FlowDesk

| Temuan | Status | Rekomendasi + Prioritas |
|---|---|---|
| Rekonsiliasi vs delta-OI resmi | Hilang (gap terbesar) | Bangun Lapis 1 pakai statistics. P0 |
| Uji prediktif flip/walls | Hilang | Bangun Lapis 2 + FDR/bootstrap. P0 |
| Self-consistency golden | Sebagian | Perluas (determinisme, invarian). P1 |
| Train/test walk-forward | Hilang | 60/30 split, threshold OOS terkunci. P1 |
| Validasi struktural | Risiko salah-paham | Tegakkan prinsip struktural. P0 |

## G.10 Pertanyaan Terbuka
- G.10.1 [VERIFY] ΔOI cukup granular per-strike harian di GLBX statistics untuk ES/NQ 0DTE.
- G.10.2 [VERIFY] Definisi operasional "sentuhan wall" & "memantul".
- G.10.3 [VERIFY] 90 hari cukup untuk power statistik H1–H3.

---
# TRACK H — Backend & Compute Architecture
## H.1 Ringkasan
Engine **deterministik, calendar-free, tick-by-tick** → Snapshot per-menit per-instrumen. Pisahkan pure compute dari orchestration. Kontrak data tunggal (pydantic↔zod) via codegen. Replay & live pakai adapter interface sama. [INFERRED+CONFIRMED]
## H.2 Engine murni / calendar-free
- Determinisme: tidak ada now()/random tanpa seed; waktu = bagian event (ts_event). Calendar-free: day-count dari timestamp; holiday disuntik sbg data. `compute_snapshot(events_up_to_t, session_state) -> Snapshot`. [CONFIRMED+INFERRED]
## H.3 Kontrak pydantic↔zod
- Single source of truth: JSON Schema dari pydantic → zod (json-schema-to-zod) di CI. schema_version=1 embedded & divalidasi. Golden fixture divalidasi pydantic DAN zod. [CONFIRMED+INFERRED]
## H.4 Feed adapter
- `FeedAdapter.stream(instrument, start, end) -> Iterator[Event]`. Historical (Databento batch/replay) & live (stub sekarang — GAP). Ordering by ts_event + buffer out-of-order. [CONFIRMED+INFERRED]
## H.5 Worker + session state machine
- PRE_OPEN → RTH_OPEN → NEAR_CLOSE → SETTLED/EXPIRED, dipicu ts_event. Per-minute emit Snapshot. Idempoten upsert (instrument, minute, schema_version). [INFERRED]
## H.6 Stale & expired
- Stale quote → mid stale → IV low-quality. Setelah 16:00 ET fixing → stop emit, roll expiry. [INFERRED]
## H.7 Throughput
- 2 instrumen × 390 menit = 780 Snapshot/hari (trivial). Bottleneck = strike × trades/menit untuk HIRO; vektorisasi numpy. [INFERRED]
## H.8 Pemetaan ke FlowDesk

| Temuan | Status | Rekomendasi + Prioritas |
|---|---|---|
| Engine deterministik calendar-free | Cocok | Audit sumber non-determinisme. P1 |
| pydantic↔zod kontrak | Risiko drift | Codegen JSON Schema CI + golden fixture. P1 |
| Feed adapter seragam | Live = stub | Implement Databento Live gateway. P0 |
| Session state machine | Sebagian | Formalkan transisi by ts_event. P2 |
| Idempotensi/replay | Perlu dipastikan | Upsert key (instr,minute,schema_ver). P1 |

## H.10 Pertanyaan Terbuka
- H.10.1 [VERIFY] Latensi & rate-limit Databento Live multi-schema.
- H.10.2 [VERIFY] Handling out-of-order/late packet di batas menit.
- H.10.3 [VERIFY] Toolchain codegen pydantic→zod.

---
# TRACK I — Database & Storage (Time-Series)
## I.1 Ringkasan
Snapshot historis di **TimescaleDB hypertable** (partisi waktu, kompresi ~90%, retention). **Redis** hot cache Snapshot terakhir. Field array: **JSONB** default v1. [CONFIRMED]
## I.2 Skema TimescaleDB
- Hypertable `snapshots(time, instrument, schema_version, payload JSONB)`; space partition instrument; compression policy segment-by instrument; retention 90/180 hari; range-scan chunk exclusion. [CONFIRMED]
## I.3 Field array (trade-off)

| Opsi | Kelebihan | Kekurangan |
|---|---|---|
| JSONB (price_grid/gamma/delta) | Fleksibel, query partial, schema-evolution mudah | Lebih besar dari biner; parsing overhead |
| Kolom array (FLOAT[]) | Native, kompresi baik, akses elemen | Skema kaku; grid panjang variabel kurang nyaman |
| Blob terkompresi (msgpack/parquet) | Terkecil; cepat baca utuh | Tak bisa query elemen SQL; opaque |

- **I.3.1** Rekomendasi: JSONB v1; revisit bila profiling. [INFERRED]
## I.4 Volume
- 2 instrumen × 90 hari × 390 menit = **70.200 Snapshot**; ratusan MB → puluhan MB setelah kompresi. Sangat kecil. [INFERRED]
## I.5 Redis hot cache
- Key `snapshot:{instrument}:latest`; pub/sub untuk push ke WebSocket. [CONFIRMED+INFERRED]
## I.6 Migrasi schema
- schema_version per row; v1 locked; field opsional baru (vex/chex) = additive. [INFERRED]
## I.7 Pemetaan ke FlowDesk

| Temuan | Status | Rekomendasi + Prioritas |
|---|---|---|
| Timescale hypertable + kompresi | Sesuai | Hypertable(time,space=instrument)+compression. P1 |
| Retention 90-day | Belum tentu di-set | add_retention_policy/drop_chunks. P2 |
| JSONB untuk grid | Default | JSONB v1; revisit bila profiling. P2 |
| Redis hot cache | Sesuai | snapshot:{instr}:latest + pub/sub. P1 |
| schema_version migrasi | Ada (v1) | Field baru additive only. P2 |

## I.9 Pertanyaan Terbuka
- I.9.1 [VERIFY] Ukuran rata-rata Snapshot ES/NQ untuk estimasi storage.
- I.9.2 [VERIFY] Perlu continuous aggregates Timescale?
- I.9.3 [VERIFY] Strategi backup/PITR.

---
# TRACK J — Frontend (WebGL Financial Heatmap)
## J.1 Ringkasan
Heatmap exposure (price × strike) via **WebGL**: data → texture/VBO, fragment shader → colormap **OKLab** (perceptually uniform, turquoise→crimson tanpa banding). Re-render per-menit murah (update texture). [CONFIRMED]
## J.2 Rendering pipeline
- Upload grid → Float32 texture; update via texSubImage2D per-menit. Shader hitung warna di GPU. Normalisasi signed [−1,1] → crimson/turquoise OKLab. [CONFIRMED]
## J.3 Colormap OKLab
- Gradien perseptual-uniform; interpolasi di OKLab → sRGB di shader; LUT bila perlu. [CONFIRMED]
## J.4 Overlay & interaksi
- Levels (walls/flip) garis horizontal; HIRO line overlay; timeline scrubber dari cache; dim/freeze saat stale. [INFERRED]
## J.5 Best practice
- Reuse buffer; rAF hanya saat berubah; instancing untuk marker. [CONFIRMED]
## J.6 Pemetaan ke FlowDesk

| Temuan | Status | Rekomendasi + Prioritas |
|---|---|---|
| WebGL heatmap + shaders | Cocok | texSubImage2D per-menit. P1 |
| OKLab colormap (turquoise/crimson) | Cocok (oklab module) | Interpolasi OKLab di shader/LUT. P2 |
| Overlay levels/HIRO | Sebagian | Layer terpisah; scrubber dari cache. P2 |
| Dim/freeze state | Sebagian | Formalkan; dim saat stale. P3 |
| Dashboard TRACE-style penuh | Gap | Roadmap panel gabung. P3 |

## J.8 Pertanyaan Terbuka
- J.8.1 [VERIFY] Resolusi grid optimal vs performa GPU.
- J.8.2 [VERIFY] Perlu WebGL2/instancing atau WebGPU?
- J.8.3 [VERIFY] Normalisasi warna per-snapshot vs global.

---
# TRACK K — Auth & Entitlement (Discord OAuth)
## K.1 Ringkasan
Gating via **Discord OAuth2** scope `identify` + `guilds.members.read`. Alur: code grant → token → GET /users/@me → GET /users/@me/guilds/{guild.id}/member → verifikasi DESK_ROLE_ID → signed session cookie. Ancaman: CSRF (state param), token leakage (server-side httpOnly), over-scoping. [CONFIRMED]
## K.2 Scope & endpoint
- identify → user id/username (tanpa email). guilds.members.read → member object + roles[]. Minimal scope (jangan email/guilds.join). [CONFIRMED]
## K.3 Verifikasi membership + role
- Cek DESK_ROLE_ID ∈ member.roles; tolak 403 bila tidak. Verifikasi guild.id benar (cegah spoofing). [CONFIRMED+INFERRED]
## K.4 Session cookie
- Signed (HMAC/JWT), httpOnly + Secure + SameSite. Token Discord server-side. Re-check role periodik. [CONFIRMED]
## K.5 Ancaman & mitigasi
- CSRF → state param terikat sesi. Token leakage → TLS + httpOnly. Redirect URI whitelist. Rotate session id setelah login. [CONFIRMED]
## K.6 Pemetaan ke FlowDesk

| Temuan | Status | Rekomendasi + Prioritas |
|---|---|---|
| OAuth identify + guilds.members.read | Cocok (locked) | Minimal scope. P0 |
| DESK_ROLE_ID gate | Cocok (locked) | Cek role + verifikasi guild id. P0 |
| Signed session cookie | Cocok (auth.py) | httpOnly+Secure+SameSite; rotate id. P1 |
| CSRF state param | Pastikan ada | State param terikat sesi + validasi. P0 |
| Re-check role berkala | Kemungkinan hilang | Re-verifikasi periodik (entitlement.py). P2 |

## K.8 Pertanyaan Terbuka
- K.8.1 [VERIFY] Rate-limit Discord API saat login burst.
- K.8.2 [VERIFY] Kebijakan refresh token & masa berlaku sesi.
- K.8.3 [VERIFY] Cache hasil verifikasi role (TTL)?

---
# TRACK L — Sintesis & Rekonsiliasi (Final)
## L.1 Executive Summary
FlowDesk berdiri di atas fondasi yang **benar secara matematis & arsitektural**, tetapi belum **terbukti benar secara empiris**.
1. **Fondasi solid (A–C, H–K):** Black-76 tepat; Databento GLBX.MDP3 cukup; arsitektur deterministik + Timescale/Redis + WebGL/OKLab + Discord OAuth sesuai best practice. Tak ada rekomendasi menyentuh LOCKED CONTRACT.
2. **Metodologi sinyal (D–F) valid sbg proxy, tapi punya bias yang harus didokumentasi & diukur:** VOL-kumulatif + tanda statis = aproksimasi; DDOI (v3) jalur perbaikan measurable. HIRO sah; vanna/charm siap diekspos additive.
3. **Prioritas absolut = Track G (validasi):** sampai harness rekonsiliasi delta-OI & uji prediktif berjalan, angka GEX "plausibly correct", bukan "proven correct".
## L.2 Rekonsiliasi Kontradiksi Lintas-Track

| Kontradiksi | Posisi A | Posisi B | Resolusi |
|---|---|---|---|
| Sumber aggressor side | Riset lama: lock tbbo + bbo-1m | Keputusan #4: trades.side tanpa tbbo | trades.side cukup (side identik tbbo, matching engine). tbbo → hanya sampel validasi. (B.6) |
| Basis kuantitas GEX | OI (teori klasik/DDOI) | VOL kumulatif (#1) | VOL = proxy intraday (OI lagging). VOL v1; DDOI paralel v3 & ukur vs ΔOI. (D.5–D.6, G.4) |
| Validasi vs vendor | Cocokkan angka dgn SPX vendor | GLBX ≠ SPX | Validasi STRUKTURAL (flip/wall/regime). (A.6, G.1) |
| Surface/vanna/charm | Sudah ada di kode | Tidak masuk Snapshot | Field OPSIONAL (schema_version+1), additive. (F.5) |

## L.3 Tabel Keputusan Master

| Topik | Status | Rekomendasi | Prioritas | Keyakinan |
|---|---|---|---|---|
| Black-76 options-on-futures | Cocok (locked) | Pertahankan; golden test | P0 | CONFIRMED |
| Schema Databento minimal | Sebagian (feed stub) | definition+bbo-1m+trades+statistics | P0 | CONFIRMED |
| trades.side untuk HIRO | Cocok (#4) | Ukur fraksi side=N | P1 | CONFIRMED |
| GEX basis VOL | Cocok (#1) | VOL v1; DDOI paralel v3 | P2 | CONFIRMED konsep |
| Harness rekonsiliasi ΔOI | Hilang | Bangun Lapis 1 (statistics) | P0 | INFERRED+CONFIRMED |
| Uji prediktif flip/walls | Hilang | Bangun Lapis 2 (FDR/bootstrap) | P0 | INFERRED |
| Live feed | Stub | Databento Live gateway | P0 | CONFIRMED gap |
| pydantic↔zod kontrak | Risiko drift | Codegen JSON Schema CI | P1 | CONFIRMED |
| TimescaleDB + Redis | Sesuai | Hypertable+compression+retention; Redis | P1 | CONFIRMED |
| WebGL/OKLab heatmap | Cocok | texSubImage2D/menit; OKLab shader | P1 | CONFIRMED |
| Discord OAuth + role gate | Cocok (locked) | State param CSRF; httpOnly | P0 | CONFIRMED |
| Vanna/charm (VEX/CHEX) | Terisolasi | Field opsional schema_version+1 | P2 | CONFIRMED |
| Ekspansi RTY | Hilang | Tambah setelah G lulus | P2 | CONFIRMED |

## L.4 Open Questions Prioritas (butuh data, bukan opini)
1. [VERIFY] Granularitas ΔOI per-strike harian di GLBX statistics — prasyarat Lapis 1.
2. [VERIFY] Fraksi side=N pada trades opsi 0DTE.
3. [VERIFY] Apakah struktur GEX futures prediktif untuk /ES /NQ intraday (H1–H3).
4. [VERIFY] (DITUTUP) Bentuk eksak & tanda vanna/charm vs QuantLib.
5. [VERIFY] Biaya ingest historis aktual & rate-limit Databento Live.
6. [VERIFY] Parameterisasi surface terbaik untuk 0DTE.
## L.5 Roadmap Riset/Empiris Berurut
1. **Fase 0 — Data foundation (P0):** ingest definition+statistics harian + trades/bbo-1m RTH 90 hari; resolusi instrument_id; verifikasi granularitas ΔOI.
2. **Fase 1 — Harness Lapis 1 (P0):** rekonsiliasi VOL-GEX vs ΔOI; baseline & kriteria lulus/gagal.
3. **Fase 2 — Harness Lapis 2 (P0):** uji prediktif walk-forward 60/30 + FDR + block bootstrap.
4. **Fase 3 — Live feed (P0) & kontrak pydantic↔zod (P1).**
5. **Fase 4 — Hardening (P1):** Timescale compression/retention; Redis; golden diperluas; numerik IV.
6. **Fase 5 — Fitur lanjutan (P2):** DDOI paralel; field vex/chex/EM; ekspansi RTY.
7. **Fase 6 — UX TRACE-style (P3).**
## L.7 Status Acceptance Criteria

| Kriteria | Status |
|---|---|
| Tiap track 5 bagian | ✅ A–K lengkap; L = sintesis |
| Klaim ber-sumber & ber-tag | ✅ CONFIRMED/INFERRED/VERIFY |
| Kontradiksi direkonsiliasi | ✅ L.2 + B.6 |
| Universe + spec + tanggal akses | ✅ A.5 (12 Jun 2026) |
| Track G harness implementable | ✅ G.4–G.7 |
| Tak ada rekomendasi sentuh LOCKED CONTRACT | ✅ Semua additive/v3 |
