<aside>
📌

Laporan riset kuantitatif. Setiap klaim diberi label: **[FAKTA]** (sumber primer + URL), **[INFERENSI]** (penalaran dari fakta), **[PROPRIETARY]** (metode tak dipublikasi), **[TIDAK DITEMUKAN]** / **[PERLU VERIFIKASI]**. Tanggal akses semua sumber: **13 Jun 2026**. Tidak ada angka/rumus/simbol yang dikarang; bila tak yakin ditulis eksplisit.

</aside>

## TL;DR (3 kalimat)

1. **[FAKTA]** /ES **dan** /NQ options-on-futures di CME **PUNYA expiry harian sungguhan (0DTE Senin–Jumat)** sejak penambahan Selasa & Kamis di 2022 — masalahmu adalah **symbology**, bukan ketiadaan produk.[[1]](https://www.cmegroup.com/trading/equity-index/files/es-options-product-codes-and-listing-calendar.pdf)[[2]](https://www.cmegroup.com/trading/equity-index/e-mini-nasdaq-100-weekly-options.html)
2. **[FAKTA]** Parent symbology Databento `ES.OPT` **hanya** mengembalikan opsi **kuartalan** ("all quarterly E-mini S&P 500 options and option spreads") — itulah persis kenapa kamu cuma dapat ESM6/ESZ6; daily/weekly punya **root produk berbeda**.[[3]](https://databento.com/docs/standards-and-conventions/symbology)
3. **[INFERENSI kuat]** Fenomena "0DTE" terkenal 2023–2026 adalah pasar **SPX (OPRA)**, bukan ES (GLBX); untuk terminal dealer-positioning, GLBX/ES menang di *aggressor side native* + Black-76, sementara OPRA/SPX menang di likuiditas 0DTE & cash-settlement.

---

# 🔍 AUDIT — Sanggahan & Verifikasi Sumber Primer (putaran ke-2)

<aside>
🧷

Putaran ini membuka **sumber primer langsung** (PDF & dokumentasi, bukan snippet) untuk menyanggah klaim laporan. Hasil: **4 dari 5 klaim berisiko-tinggi terkonfirmasi VERBATIM**, 1 klaim **tetap sebagian terbuka** (ditandai jujur). Beberapa label keyakinan dinaikkan; satu temuan auditor baru memperkuat argumen sirkularitas di §5.

</aside>

**A. Kode produk daily ES — diverifikasi VERBATIM dari PDF CME (bukan lagi pengetahuan umum). [FAKTA]**

Dibuka langsung: Senin **E1A–E5A**, Selasa **E1B–E5B**, Rabu **E1C–E5C**, Kamis **E1D–E5D**, Jumat **EW1–EW4**, EOM **EW**, Quarterly AM **ES**. Nuansa penting yang tadinya tak eksplisit:

- Weekly/EOM = **European, expiry 15:00 CT**; **Quarterly AM (ES) = American, expiry 08:30 CT** (futures hasil exercise langsung cash-settle).
- **EW3 (Friday Week-3)** dilisting 19 minggu + 4 kuartalan thn-2 + Des thn 3–5.
- Ada produk terpisah **Month-End S&P 500 ($100, kode SME)** — jangan tercampur dengan EOM E-mini ($50).

**B. Rumus SqueezeMetrics — diverifikasi VERBATIM dari white paper. [FAKTA]** `GEX_call = Γ·OI·100`; `GEX_put = Γ·OI·(−100)`; "calls represent long gamma, puts represent short gamma"; SPX didenominasi dolar. Empat asumsi cocok persis.

<aside>
🎯

**Temuan auditor (krusial untuk §5 Validasi-mu):** White paper **mengakui sirkularitas secara eksplisit** di Asumsi #2 — arah trade ditentukan "from an analysis of skew, open interest at strike, and **(circularly) the effects of GEX**." Jadi inferensi arah dealer SqueezeMetrics **sebagian melingkar by design**. Ini persis mengonfirmasi kekhawatiranmu: jangan tiru pola itu lalu memvalidasi ke ΔOI/GEX yang sama → tautologi. **[FAKTA dari white paper]**

</aside>

**C. GLBX punya aggressor `side` native — diverifikasi. [FAKTA]** Trades schema Databento: field `side` = **B** (buy aggressor), **A** (sell aggressor), **N** (none). Buy/sell ground-truth memang tersedia di ES/NQ — Lee-Ready tak perlu di GLBX.

**D. OPRA TIDAK punya `side` — dinaikkan [INFERENSI]→[FAKTA].** Databento (OPRA.PILLAR): *"OPRA does not disseminate the side of a trade, so `side` will always be `N`."* Dua konsekuensi keras:

- **[FAKTA]** *"OPRA does not cover options on equity index futures, which are traded on futures exchanges like CME."* → /ES /NQ **tidak ada** di OPRA sama sekali; OPRA hanya SPX/SPY/QQQ/VIX dll.
- **[FAKTA]** Migrasi normalisasi (efektif 27 Mei 2025): **MBP-1→CMBP-1**, **TBBO→TCBBO**. Untuk Lee-Ready di OPRA, pakai **TCBBO** (snapshot NBBO tepat sebelum tiap trade) sebagai sumber quote.[[1]](https://databento.com/docs/schemas-and-data-formats/trades)[[2]](https://databento.com/blog/opra-migration)

**E. Klaim sentral `ES.OPT` = kuartalan-saja — TETAP [FAKTA], tapi enumerasi parent weekly MASIH TERBUKA.** Terkonfirmasi [FAKTA] `ES.OPT` hanya kuartalan & root parent berasal dari field `asset`. Namun **[TIDAK DITEMUKAN]** dokumentasi publik Databento yang meng-enumerate string parent tiap keluarga weekly (`E1A.OPT`, `EW1.OPT`, dst.). **Putusan auditor (mengikat):** jangan hard-code parent weekly; metode **deterministik & anti-bug** = tarik `schema="definition"` lalu **filter `expiration.date()==sesi`** (§3D), verifikasi nilai `asset` aktual dari output sebelum produksi.

<aside>
⚖️

**Sengaja TIDAK di-over-claim (jujur):** (1) `SPXW` sebagai parent persis SPX 0DTE di Databento = konvensi OSI, belum dikutip dari doc Databento sesi ini → **[PERLU VERIFIKASI]**. (2) Angka likuiditas ES/NQ daily per-keluarga → **[TIDAK DITEMUKAN]**. (3) Arah temuan kuantitatif Brogaard et al. → belum dibaca penuh, jangan parafrase hasil.

</aside>

---

# JAWABAN 3 (TERPENTING)

<aside>
✅

**APAKAH /ES & /NQ PUNYA 0DTE HARIAN? → YA, TEGAS.**

Keduanya punya expiry **setiap hari kerja (Sen–Jum)**, European-style, expiry 15:00 Central Time (ES) / 16:00 ET fixing (NQ). Selasa & Kamis ditambahkan pada **2022**. **[FAKTA]**

</aside>

### Tabel jadwal & kode produk RESMI — E-mini S&P 500 (ES) options

Sumber: CME "S&P 500 options on futures — product codes & listing calendar" PDF.[[1]](https://www.cmegroup.com/trading/equity-index/files/es-options-product-codes-and-listing-calendar.pdf) **[FAKTA]**

| Tipe expiry | Hari | Style | Globex product code | Contoh |
| --- | --- | --- | --- | --- |
| Weekly Monday | Senin | European | E1A, E2A, E3A, E4A, E5A | E2AU1 |
| Weekly Tuesday | Selasa | European | E1B, E2B, E3B, E4B, E5B | E2BU1 |
| Weekly Wednesday | Rabu | European | E1C, E2C, E3C, E4C, E5C | E2CU1 |
| Weekly Thursday | Kamis | European | E1D, E2D, E3D, E4D, E5D | E2DU1 |
| Weekly Friday | Jumat (W1,2,4 + W3×19) | European | EW1, EW2, EW3, EW4 | EW4U1 |
| End-of-Month (EOM) | Akhir bulan | European | EW | EWU1 |
| Quarterly | 3rd Friday Mar/Jun/Sep/Dec | American | ES | ESU1 (= ESM6, ESZ6, dst.) |

**[FAKTA]** Catatan dari PDF: "Expirations are now available every business day spanning the next 5 weeks (25 business days), with the addition of Tuesday and Thursday expiries in 2022" dan "On any given day, there will be nearly 70 S&P 500 options expiries."[[1]](https://www.cmegroup.com/trading/equity-index/files/es-options-product-codes-and-listing-calendar.pdf) Friday Week-3 (EW3) = serial yang ber-anchor ke kuartalan (ES) di bulan kuartal.

### Tabel jadwal & kode produk RESMI — E-mini Nasdaq-100 (NQ) options

Sumber: CME "E-mini Nasdaq-100 Weekly Options" contract specs.[[2]](https://www.cmegroup.com/trading/equity-index/e-mini-nasdaq-100-weekly-options.html) **[FAKTA]**

| Tipe expiry | Hari | Globex product code |
| --- | --- | --- |
| Weekly Monday | Senin | Q1A, Q2A, Q3A, Q4A, Q5A |
| Weekly Tuesday | Selasa | Q1B, Q2B, Q3B, Q4B, Q5B |
| Weekly Wednesday | Rabu | Q1C, Q2C, Q3C, Q4C, Q5C |
| Weekly Thursday | Kamis | Q1D, Q2D, Q3D, Q4D, Q5D |
| Weekly Friday | Jumat | QN1, QN2, QN3, QN4 |
| Quarterly | 3rd Friday Mar/Jun/Sep/Dec | NQ (kuartalan) |

**[FAKTA]** CME: "E-mini Nasdaq-100 Tuesday and Thursday options are now available … complement the existing Weekly (Monday, Wednesday, Friday), End-of-Month, as well as Quarterly options." Settlement: posisi futures cash-settled, fixing 16:00 ET (symbol NQF).[[2]](https://www.cmegroup.com/trading/equity-index/e-mini-nasdaq-100-weekly-options.html)

### Penyebab bug-mu (definitif)

<aside>
🐛

**[FAKTA]** Dari dokumentasi Databento: *"`ES.FUT` refers to all E-mini S&P 500 futures and futures spreads and `ES.OPT` refers to all quarterly E-mini S&P 500 options and option spreads."*[[3]](https://databento.com/docs/standards-and-conventions/symbology) → Parent `ES.OPT`/`NQ.OPT` **mengecualikan** seluruh keluarga weekly/daily (E1A–E5D, EW1–EW4, EW, dan Q1A–QN4). Karena itu kamu hanya melihat ESM6 (Jun) & ESZ6 (Des). Engine lalu salah memberi T≈0.14 hari ke kontrak kuartalan → **IV meledak 140–290% (artefak murni, bukan sinyal)**.

</aside>

### Simbol Databento konkret untuk menarik 0DTE

**Opsi A — tetap GLBX (rekomendasi untuk dealer-positioning).** Root `asset` per keluarga **[PERLU VERIFIKASI runtime]** — Databento mengambil root parent dari field `asset` definition; nilai persisnya untuk tiap keluarga weekly harus dikonfirmasi dengan satu panggilan `definition` (lihat §3D). Pendekatan paling robust = **enumerate definition lalu filter by `expiration`**, bukan menebak parent:

```python
import databento as db
client = db.Historical("API_KEY")

# Tarik SEMUA definition instrumen di GLBX untuk satu hari,
# lalu filter ke opsi ES/NQ yang expiry = tanggal target (0DTE).
defs = client.timeseries.get_range(
    dataset="GLBX.MDP3",
    schema="definition",
    stype_in="parent",
    symbols=["ES.OPT","NQ.OPT"],  # CATATAN: ini KUARTALAN saja — lihat di bawah
    start="2026-06-02", end="2026-06-03",
)
df = defs.to_df()
# Field kunci: expiration, asset, instrument_class, raw_symbol, underlying
```

**[FAKTA]** `ES.OPT` saja TIDAK cukup. Untuk daily/weekly kamu harus memasukkan parent root tiap keluarga, mis. (verifikasi string `asset` lebih dulu):

```python
ES_WEEKLY_PARENTS = [
  "E1A.OPT","E2A.OPT","E3A.OPT","E4A.OPT","E5A.OPT",   # Senin
  "E1B.OPT","E2B.OPT","E3B.OPT","E4B.OPT","E5B.OPT",   # Selasa
  "E1C.OPT","E2C.OPT","E3C.OPT","E4C.OPT","E5C.OPT",   # Rabu
  "E1D.OPT","E2D.OPT","E3D.OPT","E4D.OPT","E5D.OPT",   # Kamis
  "EW1.OPT","EW2.OPT","EW3.OPT","EW4.OPT","EW.OPT",    # Jumat + EOM
]
```

<aside>
⚠️

**[PERLU VERIFIKASI]** Apakah Databento meng-expose tiap weekly sebagai parent root terpisah (`E1A.OPT`, …) ATAU menggabungkannya — ini **belum terkonfirmasi** di dokumentasi yang tersedia. Yang **terkonfirmasi [FAKTA]** hanyalah: (a) `ES.OPT` = kuartalan saja, (b) root parent bersumber dari field `asset`. Cara aman & deterministik: panggil `schema="definition"` lalu **filter `expiration == tanggal_target`** untuk menemukan kontrak 0DTE, apa pun root-nya. Verifikasi nilai `asset` sebenarnya dari output definition sebelum hard-code.

</aside>

**Opsi B — pindah OPRA untuk SPX 0DTE.** Dataset `OPRA.PILLAR`, simbologi OCC/OSI 21-karakter; SPX 0DTE memakai parent **`SPXW`** (weekly/daily), bukan `SPX`.[[4]](https://databento.com/docs/venues-and-datasets/opra-pillar) **[FAKTA]**

### Rekomendasi GLBX vs OPRA (berbukti)

| Dimensi | /ES /NQ (GLBX.MDP3) | SPX/SPY (OPRA.PILLAR) |
| --- | --- | --- |
| Aggressor side | **Native** (field `side` B/A/N) — tak perlu Lee-Ready **[FAKTA, konteks user + konvensi Databento]** | **Tidak ada flag arah trade** di print OPRA → wajib inferensi (Lee-Ready vs NBBO) **[INFERENSI kuat]** |
| Pricing | Black-76 (underlying = futures) **[FAKTA standar]** | Black-Scholes (index + rate/div) **[FAKTA standar]** |
| Likuiditas 0DTE | Ada tapi jauh lebih tipis dari SPX **[INFERENSI]** | Sangat dalam: 0DTE SPX ~2.3 jt kontrak/hari, ~59% volume SPX (2025) **[FAKTA]**[[5]](https://www.cboe.com/insights/posts/the-state-of-the-options-industry-2025/) |
| Settlement | Futures (ITM → posisi futures) **[FAKTA]** | Cash-settled, Section 1256 60/40 **[FAKTA umum]** |
| OI & open/close | OI resmi via `statistics` schema **[FAKTA]**[[6]](https://databento.com/docs/schemas-and-data-formats/statistics) | OI via OCC, bukan di feed trade |

**Rekomendasi [INFERENSI]:** Untuk *dealer-positioning yang butuh klasifikasi arah akurat*, **GLBX/ES-NQ lebih unggul** karena aggressor side native menghilangkan error Lee-Ready (lihat §2). Tapi bila tujuan utama adalah **mereplikasi fenomena 0DTE yang dipelajari publik & likuiditas dalam**, **SPX/OPRA** lebih representatif. Banyak praktisi memilih SPX karena cash-settled + pajak 1256 + likuiditas — **bukan** karena ES/NQ tak punya 0DTE (mereka punya). Solusi pragmatis: **perbaiki symbology GLBX dulu** (murah, sesuai arsitektur Black-76 eksistingmu), tambahkan OPRA/SPX sebagai sumber pembanding bila perlu validasi likuiditas.

---

# 1. Synthetic OI / Dealer Positioning — Metodologi Inti

### 1.1 SqueezeMetrics GEX — white paper asli (DIPUBLIKASIKAN)

**[FAKTA]** White paper "Gamma Exposure (GEX)™ — Quantifying hedge rebalancing in SPX options", Prior Analytics LLC, Maret 2016 (rev. Desember 2017).[[7]](https://squeezemetrics.com/monitor/download/pdf/white_paper.pdf)

Rumus persis (dikutip langsung):

$$
\text{GEX}_{\text{call}} = \Gamma \cdot OI \cdot 100
$$

$$
\text{GEX}_{\text{put}} = \Gamma \cdot OI \cdot (-100)
$$

dengan Γ = gamma opsi, OI = open interest di strike, 100 = konversi kontrak→share. GEX total = Σ seluruh strike & ekspiry. "For SPX, we denominate GEX in dollars." **[FAKTA]**

**Empat asumsi eksplisit white paper [FAKTA]:**

1. Semua opsi difasilitasi delta-hedger (market-maker).
2. **Call dijual investor, dibeli market-maker** (call overwriting).
3. **Put dibeli investor, dijual market-maker** (protective put).
4. Market-maker hedge tepat ke delta opsi (abaikan hedging band).

<aside>
🔎

**Koreksi atas "konvensi praktisi" di prompt-mu:** White paper SqueezeMetrics **tidak** memakai "dealer long call / short put". Justru sebaliknya untuk arah investor; tapi untuk *gamma sign* hasilnya: **call = +gamma, put = −gamma bagi market-maker** (asumsi 2 & 3). Ini asumsi statis lama yang persis ingin kamu perbaiki dengan flow real. **[FAKTA dari white paper]**

</aside>

### 1.2 DIX & DDOI (SqueezeMetrics) — sebagian PROPRIETARY

**[FAKTA]** SqueezeMetrics juga mempublikasikan konsep **DIX (Dark Index)** dan menyebut **"Dealer Directional Open Interest (DDOI)"** di guide-nya.[[8]](https://squeezemetrics.com/monitor/static/guide.pdf) **[PROPRIETARY]** Rumus/algoritma persis bagaimana DDOI menentukan sisi long/short dealer dari flow **tidak dipublikasikan** secara lengkap; hanya definisi konseptual yang tersedia. Jadi versi GEX yang "dynamic" (berbasis flow, bukan asumsi statis call+/put−) bersifat proprietary.

### 1.3 SpotGamma, GEXBot, MenthorQ, OptionsDepth

- **SpotGamma [PROPRIETARY + sebagian dipublikasi konsep].** Mengklaim mempopulerkan istilah "GEX"; menghitung profil gamma & "zero-gamma"/"gamma flip" dengan rekalkulasi Black-Scholes lintas level spot. Konsep "Structural Dealer Positioning": flow klien secara struktural meninggalkan dealer **short downside puts, long upside calls**.[[9]](https://support.spotgamma.com/hc/en-us/articles/4413981525907-Structural-Dealer-Positioning) Rumus/kalibrasi internal **tidak dipublikasi**.
- **MenthorQ [PROPRIETARY].** Mempublikasikan deskripsi "GEX levels" tapi bukan formula rekonstruksi.[[10]](https://menthorq.com/guide/gex-levels/)
- **GEXBot [TIDAK DITEMUKAN].** Tidak ditemukan white paper/metodologi formal yang dipublikasikan.
- **OptionsDepth [TIDAK DITEMUKAN].** Tidak ditemukan dokumen metodologi publik yang menjelaskan rekonstruksi open/close-nya.

### 1.4 Rumus GEX praktisi (dipublikasi komunitas, bukan vendor)

**[FAKTA komunitas]** Bentuk yang umum dipakai (dengan scaling spot² × 0.01), mis. perfiliev & repo gex-tracker:[[11]](https://perfiliev.com/blog/how-to-calculate-gamma-exposure-and-zero-gamma-level/)[[12]](https://github.com/Matteo-Ferrara/gex-tracker)

$$
\text{GEX} = \sum_i s_i \cdot \Gamma_i \cdot OI_i \cdot M \cdot F^2 \cdot 0.01
$$

dengan $s_i$ = +1 call / −1 put (konvensi dealer long-gamma call), $M$ = multiplier kontrak, $F$ = harga underlying/futures, faktor $F^2 \cdot 0.01$ = konversi gamma per-1% move ke dollar-gamma per-1% (notional). Ini **konsisten** dengan bentuk di prompt-mu (`sign·gamma·qty·multiplier·F²·0.01`). **[INFERENSI]** Untuk options-on-futures, $F$ = harga futures dan $\Gamma$ dari Black-76.

### 1.5 Pemisahan open vs close

<aside>
❗

**[TIDAK DITEMUKAN]** Metode publik yang "resmi" untuk memisahkan open vs close dari volume+ΔOI. Vendor (SqueezeMetrics DDOI, SpotGamma, dll.) memakai model proprietary. Yang dapat dibuktikan secara akuntansi (lihat §2.4) hanya identitas underdetermined; penutupannya butuh **asumsi tambahan** yang masing-masing vendor rahasiakan. Jangan klaim ada "formula standar".

</aside>

---

# 2. Klasifikasi Trade (buy/sell + open/close)

### 2.1 Lee-Ready (1991) & akurasi

**[FAKTA]** Lee & Ready menggabungkan quote test (vs midpoint) + tick test untuk trade di midpoint. Survei NBER w14158: akurasi Lee-Ready dilaporkan **berkisar 72%–93%** tergantung studi/pasar; "usually reported as the most accurate" di antara metode tick-based klasik.[[13]](https://www.nber.org/system/files/working_papers/w14158/w14158.pdf)

### 2.2 EMO, BVC, tick rule — horse race

- **[FAKTA]** Panayides, Shohfi & Smith (2014), data Euronext Paris dengan true initiator: "Lee and Ready underperforms the other methods, particularly during intervals of high trade and/or quote frequency"; BVC unggul di efisiensi data & menangkap informed flow.[[14]](https://www.quantresearch.org/Panayides_Shohfi_Smith.pdf)
- **[FAKTA]** Easley, López de Prado & O'Hara — "Discerning information from trade data" (JFE 2016): tick rule & BVC sama-sama klasifier aggressor yang cukup baik, **BVC lebih terkait ke proxy informed trading**.[[15]](https://www.sciencedirect.com/science/article/abs/pii/S0304405X16000246)
- **[FAKTA]** Pascual et al. (horse race NASDAQ INET): beralih TR→BVC menaikkan misklasifikasi **7.4–16.3 poin persen (46%–291%)** — BVC **kurang akurat** untuk sisi arah.[[16]](https://dee.uib.eu/digitalAssets/234/234006_Pascual.pdf)
- **[FAKTA]** Carrion & Kolay (2020): bukti BVC mengukur informed trading sebagian **spurious** (uji misspesifikasi); BVC order imbalance kalah dari ukuran berbasis aggressor flag.[[17]](http://faculty.bus.olemiss.edu/rvanness/Speakers/Presentations%202019-2020/AlCarrion_BVC_info_Jan2020.pdf)

### 2.3 Relevansi untuk futures options (aggressor native)

<aside>
💡

**[INFERENSI kuat]** Karena GLBX.MDP3 menyediakan **aggressor side native** (`side` = B/A/N), seluruh debat Lee-Ready/EMO/BVC untuk *buy vs sell* **tidak relevan** bagimu di ES/NQ — kamu sudah punya ground-truth aggressor (kecuali N = unknown/implied). Lee-Ready hanya kembali relevan **jika** kamu pindah ke OPRA (print tanpa flag arah). Ini argumen teknikal kuat untuk **tetap di GLBX**.

</aside>

### 2.4 Identitas akuntansi & masalah M (mixed)

Per-strike per-hari (notasi promptmu, valid secara akuntansi) **[FAKTA/aljabar]**:

$$
V = O + C + M \qquad \Delta OI = O - C
$$

dengan O = both-open, C = both-close, M = mixed (satu buka satu tutup). Dua persamaan, tiga unknown → **underdetermined**. **[INFERENSI]** Cara umum menutup gap (semuanya asumsi, bukan kebenaran):

- Asumsi $M=0$ → $O=(V+\Delta OI)/2,\ C=(V-\Delta OI)/2$ (paling sering dipakai sebagai aproksimasi).
- Distribusi M proporsional/empiris (kalibrasi historis) — **[PROPRIETARY]** di vendor.
- Pakai *trade size / mid-vs-bid-ask / aggressor* sebagai prior untuk open/close — **[TIDAK DITEMUKAN]** referensi publik yang membakukan ini untuk futures options.

<aside>
⚠️

**[TIDAK DITEMUKAN]** Tidak ada exchange/vendor yang mempublikasikan cara persis menangani M. CME mempublikasikan **OI resmi & volume** (settle), bukan dekomposisi O/C/M. Maka dekomposisi open/close di engine-mu **wajib** ditandai sebagai *asumsi model*, bukan data.

</aside>

---

# 3. GLBX vs OPRA & Eksistensi 0DTE (detail)

*(Jawaban definitif sudah di bagian "JAWABAN 3" di atas. Di sini pendukungnya.)*

### 3A. Eksistensi 0DTE harian ES/NQ — **YA** (lihat tabel di atas)

**[FAKTA]** ES: harian Sen–Jum via E1A–E5A / E1B–E5B / E1C–E5C / E1D–E5D / EW1–EW4; Selasa+Kamis sejak 2022.[[1]](https://www.cmegroup.com/trading/equity-index/files/es-options-product-codes-and-listing-calendar.pdf) NQ: Q1A–Q5A … QN1–QN4, Selasa+Kamis tersedia.[[2]](https://www.cmegroup.com/trading/equity-index/e-mini-nasdaq-100-weekly-options.html)

**[TIDAK DITEMUKAN]** Angka likuiditas harian per-keluarga (ADV/OI) ES/NQ daily vs monthly dari sumber primer CME pada sesi ini — **tidak terverifikasi**; jangan kutip angka. Secara kualitatif **[INFERENSI]** Friday & Quarterly jauh lebih likuid dari daily Sen–Kam.

### 3B. Kenapa orang pakai OPRA untuk 0DTE

- **[FAKTA]** OPRA.PILLAR = trades + NBBO konsolidasi 17 bursa opsi AS, mencakup index options (SPX, VIX) & ETF (SPY, QQQ).[[18]](https://databento.com/blog/opra-data) Simbologi OCC/OSI 21-karakter, parent bisa `SPXW` (SPX weekly).[[4]](https://databento.com/docs/venues-and-datasets/opra-pillar)
- **[FAKTA]** Skala 0DTE SPX: rata-rata **2.3 juta kontrak/hari** & **59% volume SPX** (Cboe State of the Options Industry 2025).[[5]](https://www.cboe.com/insights/posts/the-state-of-the-options-industry-2025/) Bulan tertentu "over 61% of overall SPX volumes".[[19]](https://www.cboe.com/insights/posts/spx-0-dte-options-jump-to-61-share-on-retail-resurgence/) Schwab/Cboe: ~1.5 jt/hari, ~½ volume terkait SPX.[[20]](https://www.schwab.com/learn/story/zeroing-on-0dte-options-learn-basics)
- **[FAKTA]** SPX punya expiry tiap hari kerja setelah Cboe menambah **Selasa & Kamis pada 2022** (melengkapi Senin/Rabu/Jumat).[[21]](https://www.merrilledge.com/investment-products/options/0dte-options-trading)
- **[INFERENSI]** Praktisi/peneliti memilih SPX/OPRA karena **cash-settled, pajak Section 1256 (60/40), likuiditas terdalam**, dan karena literatur publik (Cboe/akademik) memang pakai SPX — **bukan** karena ES/NQ tak punya 0DTE.

### 3C. Keputusan strategis — lihat tabel rekomendasi di "JAWABAN 3"

**[INFERENSI]** Tambahan: jika pindah OPRA, kamu kehilangan aggressor native → harus Lee-Ready vs NBBO (akurasi 72–93%, degradasi saat fast market 0DTE sore). Ini menambah *noise* tepat di momen paling penting (gamma sore). Ini argumen kuat menahan diri di GLBX untuk produk dealer-positioning.

### 3D. Verifikasi symbology Databento (konkret)

**[FAKTA]** Empat stype Databento: `raw_symbol`, `instrument_id`, `parent`, `continuous`.[[22]](https://databento.com/docs/api-reference-historical/basics/symbology) Parent root bersumber dari field **`asset`** definition; `[ROOT].FUT` untuk futures, `[ROOT].OPT` untuk opsi.[[3]](https://databento.com/docs/standards-and-conventions/symbology)

**[FAKTA]** Spread/combo opsi (mis. vertical `UD:1V: VT …`) termasuk dalam parent opsi (`ES.OPT`).[[23]](https://databento.com/docs/venues-and-datasets/glbx-mdp3)

**[FAKTA]** Cara enumerate semua expiry untuk satu tanggal = schema **`definition`**; field kunci: `expiration`, `asset`, `instrument_class` (call/put untuk parent opsi), `raw_symbol`, `underlying`, `strike_price`.[[24]](https://databento.com/docs/schemas-and-data-formats/instrument-definitions)[[25]](https://databento.com/docs/examples/symbology/parent-symbology) Untuk membedakan **daily vs weekly vs quarterly**: tidak ada field tunggal "tenor" — **[INFERENSI]** bedakan via kombinasi `raw_symbol` (root E1A/EW3/ES dst.) + `expiration` date. Cara deterministik mendapatkan 0DTE: **filter `expiration.date() == tanggal_sesi`**.

```python
# Resolusi 0DTE deterministik (apa pun root):
df = defs.to_df()
zero_dte = df[df["expiration"].dt.date == pd.Timestamp("2026-06-02").date()]
zero_dte = zero_dte[zero_dte["instrument_class"].isin([db.InstrumentClass.CALL,
                                                      db.InstrumentClass.PUT])]
# lalu pakai zero_dte["raw_symbol"] / instrument_id untuk timeseries.get_range(schema="trades"/"tbbo")
```

**[FAKTA]** Untuk cek rentang dataset gunakan `metadata.get_dataset_range`; untuk tarik data, `timeseries.get_range(dataset="GLBX.MDP3", schema=..., stype_in="parent"|"raw_symbol", symbols=..., start=..., end=...)`.[[25]](https://databento.com/docs/examples/symbology/parent-symbology)

---

# 4. Dinamika 0DTE Spesifik

### 4.1 Gamma & charm dekat ekspiry

**[FAKTA]** Schwab: 0DTE "carry the highest gamma of any options and decay to zero in hours"; gamma membuat 0DTE sangat sensitif ke gerak kecil underlying.[[20]](https://www.schwab.com/learn/story/zeroing-on-0dte-options-learn-basics) **[INFERENSI/teori standar]** Saat $Tto 0$, gamma ATM $\to \infty$ dan charm (∂Δ/∂t) mendominasi sore hari → hedging dealer makin intens.

### 4.2 Bukti akademik (2023–2026)

| Paper | Penulis, tahun | Temuan inti |
| --- | --- | --- |
| 0DTEs: Trading, Gamma Risk and Volatility Propagation | Dim, Eraker, Vilkov (SSRN 4692190) | **[FAKTA]** Net gamma inventory MM rata-rata **positif** & **negatif terkait** volatilitas intraday mendatang; positif→perkuat reversal, negatif→perkuat momentum. Konsisten delta-hedging, tak konsisten dengan info-trading.[[26]](https://papers.ssrn.com/sol3/Delivery.cfm/4692190.pdf?abstractid=4692190) |
| Does 0DTE Options Trading Increase Volatility? | Brogaard, Han, Won (2023, SSRN 4426358) | **[FAKTA]** Studi empiris pertanyaan apakah 0DTE menaikkan volatilitas.[[27]](https://papers.ssrn.com/sol3/Delivery.cfm/4426358.pdf?abstractid=4426358) (Baca abstrak/isi penuh untuk arah temuan — belum dikutip detail di sesi ini, jangan parafrase hasil.) |
| Much Ado About 0DTEs (market impact) | Mandy Xu, Cboe, Sep 2023 | **[FAKTA]** Analisis dampak pasar SPX 0DTE.[[28]](https://www.cboe.com/insights/posts/volatility-insights-evaluating-the-market-impact-of-spx-0-dte-options/) |

### 4.3 Pinning

- **[FAKTA]** Avellaneda & Lipkin (2003), "A market-induced mechanism for stock pinning": probabilitas pinning sebagai fungsi volatilitas, time-to-maturity, **open interest**, & konstanta price-impact.[[29]](https://www.cis.upenn.edu/~mkearns/finread/PinningPaper.pdf)
- **[FAKTA]** "Pinning in the S&P 500 futures" (JFE 2012): pinning ada di S&P futures; driver = penyesuaian delta-hedge MM (time decay) + manipulasi.[[30]](https://www.sciencedirect.com/science/article/abs/pii/S0304405X12001365)

### 4.4 Apakah synthetic OI bermakna untuk 0DTE?

<aside>
🧠

**[INFERENSI]** Kontrak 0DTE **bukan** "lahir & mati di satu hari" — keluarga daily/weekly **dilisting beberapa minggu sebelumnya** (ES: 25 hari kerja ke depan).[[1]](https://www.cmegroup.com/trading/equity-index/files/es-options-product-codes-and-listing-calendar.pdf) Jadi OI **terakumulasi sebelum** hari ekspiry; pada hari-H, posisi yang sudah ada (OI awal hari) + flow intraday = basis dealer gamma. ΔOI harian untuk kontrak yang expiry hari itu cenderung **negatif besar** (posisi ditutup/expired). **Implikasi praktis:** untuk 0DTE, sinyal yang bermakna adalah **OI awal-hari (settle kemarin) + rekonstruksi flow intraday (open/close estimasi)**, bukan ΔOI end-of-day (yang sudah tahu posisi mati). Maka "synthetic OI intraday" tetap bermakna; ΔOI EOD kurang berguna sebagai validator untuk hari ekspiry (lihat §5 sirkularitas).

</aside>

---

# 5. Validasi

### 5.1 Rekonsiliasi vs ΔOI resmi & risiko sirkularitas

<aside>
♻️

**[INFERENSI — prinsip metodologis]** Jika open/close diestimasi **menggunakan** ΔOI (mis. asumsi M=0 yang memakai ΔOI), lalu posisi hasilnya diuji terhadap ΔOI → **tautologi**. Validasi harus pakai **target independen**: (a) OI resmi keesokan hari sebagai *hold-out* (prediksi posisi t, cek vs OI settle t, **tanpa** memakai OI t dalam estimasi), atau (b) target ekonomi (realized vol, pinning, reaksi gamma-flip) yang tak dipakai saat fitting.

</aside>

### 5.2 Desain uji prediktif (rekomendasi standar)

**[INFERENSI / praktik baku ekonometrika]** (bukan klaim sumber spesifik):

- **Walk-forward / out-of-sample bergulir**: fit di window historis, uji di window berikut, geser. Hindari look-ahead (gunakan hanya OI settle kemarin & flow s.d. waktu-t).
- **Block bootstrap** (mis. stationary/circular block) untuk inferensi pada deret waktu autokorelasi intraday — pertahankan struktur dependensi.
- **Kontrol multiple-testing**: Benjamini-Hochberg **FDR** saat menguji banyak strike/jam/level; waspada "False Strategy Theorem" (López de Prado & Bailey 2021) — Sharpe maksimum dari banyak trial bias ke atas.[[31]](https://www.quantresearch.org/Publications.htm)
- **Hipotesis spesifik** yang bisa diuji: (i) dealer gamma negatif → realized vol intraday lebih tinggi (searah temuan Dim-Eraker-Vilkov); (ii) konsentrasi gamma di strike → probabilitas pinning naik (searah Avellaneda-Lipkin); (iii) reaksi harga di gamma-flip level.

### 5.3 Horizon data minimum

<aside>
📏

**[TIDAK DITEMUKAN / tidak terverifikasi]** Tidak ada angka horizon minimum baku dari sumber primer untuk kasus 0DTE ES/NQ. **[INFERENSI]** Karena hanya ~252 hari bursa/tahun dan efek 0DTE bersifat intraday, gunakan **granular intraday (1-min)** untuk menambah observasi efektif, dan minimal **beberapa ratus hari ekspiry** per produk agar block-bootstrap & FDR punya power; angka pastinya harus ditentukan via power analysis empiris, bukan dikutip.

</aside>

---

# RINGKASAN IMPLEMENTABLE (siap-kode, asumsi ditandai)

**1. Resolusi instrumen 0DTE (GLBX)** — *deterministik, jangan tebak parent:*

- Pull `schema="definition"` (parent `ES.OPT`,`NQ.OPT` **plus** root weekly bila terverifikasi), filter `expiration.date() == sesi`, ambil `raw_symbol`/`instrument_id`. **[ASUMSI: root weekly perlu diverifikasi runtime]**

**2. Pricing Black-76** (options-on-futures), $F$ = harga futures, $r$ diskon:

$$
c = e^{-rT}\big[F\,N(d_1) - K\,N(d_2)\big],\quad
p = e^{-rT}\big[K\,N(-d_2) - F\,N(-d_1)\big]
$$

$$
d_1 = \frac{\ln(F/K) + \tfrac{1}{2}\sigma^2 T}{\sigma\sqrt{T}},\quad d_2 = d_1 - \sigma\sqrt{T}
$$

Gamma Black-76:

$$
\Gamma = e^{-rT}\,\frac{N'(d_1)}{F\,\sigma\sqrt{T}}
$$

**[FAKTA: Black-76 standar]**

**3. Dealer GEX (per strike, jumlahkan):**

$$
\text{GEX} = \sum_i s_i\,\Gamma_i\,Q_i\,M\,F^2\,(0.01)
$$

$s_i$=+1 call/−1 put **[ASUMSI konvensi statis — ganti dengan sign dari flow bila DDOI-style tersedia]**; $Q_i$ = OI atau posisi rekonstruksi; $M$ = multiplier ($$50$ ES, $$20$ NQ **[FAKTA]**); $F$ = futures price.

**4. Dekomposisi open/close (per strike per hari):**

$$
\hat O = \tfrac{V + \Delta OI}{2},\qquad \hat C = \tfrac{V - \Delta OI}{2}\quad(\textbf{ASUMSI } M=0)
$$

**[ASUMSI eksplisit, bukan fakta — M=0 hampir pasti salah; tandai sebagai lower-bound model.]**

**5. Aggressor (GLBX):** pakai `side` native (B/A/N). **Jangan** jalankan Lee-Ready di GLBX. Lee-Ready hanya bila pindah OPRA. **[FAKTA]**

**6. Sign flow intraday (pengganti asumsi statis):** gunakan aggressor `side` + (open/close estimasi) untuk membangun **directional OI intraday**; reset basis dari OI settle kemarin (`statistics` schema). **[INFERENSI/desain]**

---

# PERINGATAN (pitfall)

<aside>
🚨

1. **Salah symbology (akar bug-mu).** `ES.OPT`/`NQ.OPT` = **kuartalan saja**. Daily/weekly butuh root keluarga (E1A–E5D, EW1–EW4, EW / Q1A–QN4) ATAU filter `definition.expiration`. **[FAKTA]**
2. **Mispricing T→0.** Menetapkan T≈0.14 ke kontrak kuartalan = IV meledak 140–290% (artefak). Selalu hitung $T$ dari `expiration` **per-instrumen**, dalam fraksi tahun sampai waktu fixing (15:00 CT ES / 16:00 ET NQ), bukan asumsi global. **[INFERENSI dari kasusmu]**
3. **Sirkularitas validasi.** Jangan uji posisi yang diestimasi-dari-ΔOI terhadap ΔOI. Pakai hold-out OI settle hari berikut / target ekonomi. **[INFERENSI]**
4. **M-trades (mixed).** Tidak ada solusi publik; M=0 hanya aproksimasi. Tandai semua dekomposisi open/close sebagai *model*, bukan data. **[TIDAK DITEMUKAN solusi baku]**
5. **OI 0DTE intraday.** ΔOI EOD untuk kontrak yang expiry hari itu ≈ posisi mati → kurang informatif. Pakai OI awal-hari + flow intraday. **[INFERENSI]**
6. **Konvensi sign statis (call+/put−).** Itu asumsi SqueezeMetrics 2016/2017, persis bias yang ingin kamu perbaiki; ganti dengan directional flow bila memungkinkan. **[FAKTA white paper]**
7. **Pindah OPRA = kehilangan aggressor native** → Lee-Ready (72–93%, memburuk di fast market sore 0DTE). Pertimbangkan sebelum migrasi. **[FAKTA + INFERENSI]**
8. **Multiple testing.** Banyak strike/jam/level → FDR + block bootstrap; waspada overfitting (False Strategy Theorem). **[INFERENSI]**
</aside>

---

# Daftar Pustaka

**Sumber primer — vendor/bursa (white paper & dokumentasi resmi)**

- SqueezeMetrics (Prior Analytics LLC), *Gamma Exposure (GEX)™*, Mar 2016 / rev. Des 2017. https://squeezemetrics.com/monitor/download/pdf/white_paper.pdf — akses 13 Jun 2026.
- SqueezeMetrics, *Monitor Guide* (DIX, DDOI). https://squeezemetrics.com/monitor/static/guide.pdf — akses 13 Jun 2026.
- SpotGamma, *Structural Dealer Positioning*. https://support.spotgamma.com/hc/en-us/articles/4413981525907-Structural-Dealer-Positioning — akses 13 Jun 2026.
- MenthorQ, *GEX Levels*. https://menthorq.com/guide/gex-levels/ — akses 13 Jun 2026.
- CME Group, *S&P 500 options on futures — product codes & listing calendar* (PDF). https://www.cmegroup.com/trading/equity-index/files/es-options-product-codes-and-listing-calendar.pdf — akses 13 Jun 2026.
- CME Group, *E-mini Nasdaq-100 Weekly Options* (contract specs). https://www.cmegroup.com/trading/equity-index/e-mini-nasdaq-100-weekly-options.html — akses 13 Jun 2026.
- CME Group, *Understanding listings and expirations* (Micro E-mini options). https://www.cmegroup.com/education/courses/micro-e-mini-options/understanding-listings-and-expirations — akses 13 Jun 2026.
- Databento, *Symbology (standards & conventions)*. https://databento.com/docs/standards-and-conventions/symbology — akses 13 Jun 2026.
- Databento, *Parent symbology (example)*. https://databento.com/docs/examples/symbology/parent-symbology — akses 13 Jun 2026.
- Databento, *Symbology (Historical API reference)*. https://databento.com/docs/api-reference-historical/basics/symbology — akses 13 Jun 2026.
- Databento, *CME Globex MDP 3.0 (GLBX.MDP3) feed specs*. https://databento.com/docs/venues-and-datasets/glbx-mdp3 — akses 13 Jun 2026.
- Databento, *OPRA (OPRA.PILLAR) feed specs*. https://databento.com/docs/venues-and-datasets/opra-pillar — akses 13 Jun 2026.
- Databento, *Instrument definitions schema*. https://databento.com/docs/schemas-and-data-formats/instrument-definitions — akses 13 Jun 2026.
- Databento, *Statistics schema (OI, settle)*. https://databento.com/docs/schemas-and-data-formats/statistics — akses 13 Jun 2026.
- Databento, *Introducing OPRA (US equity options) data* (blog). https://databento.com/blog/opra-data — akses 13 Jun 2026.

**Sumber primer — akademik (klasifikasi trade)**

- Lee & Ready (1991) — dirangkum di Boehmer et al., NBER WP w14158, *Short Sales and Trade Classification Algorithms*. https://www.nber.org/system/files/working_papers/w14158/w14158.pdf — akses 13 Jun 2026.
- Easley, López de Prado & O'Hara (2016), *Discerning information from trade data*, JFE. https://www.sciencedirect.com/science/article/abs/pii/S0304405X16000246 — akses 13 Jun 2026.
- Panayides, Shohfi & Smith (2014), *Comparing Trade Flow Classification Algorithms in the Electronic Era*. https://www.quantresearch.org/Panayides_Shohfi_Smith.pdf — akses 13 Jun 2026.
- Pascual et al., *Trade Classification Algorithms: A Horse Race between Bulk-based and Tick-based Rules*. https://dee.uib.eu/digitalAssets/234/234006_Pascual.pdf — akses 13 Jun 2026.
- Carrion & Kolay (2020), *Bulk Volume Trade Classification and Informed Trading*. http://faculty.bus.olemiss.edu/rvanness/Speakers/Presentations%202019-2020/AlCarrion_BVC_info_Jan2020.pdf — akses 13 Jun 2026.

**Sumber primer — akademik/industri (0DTE, pinning, gamma)**

- Dim, Eraker & Vilkov, *0DTEs: Trading, Gamma Risk and Volatility Propagation*, SSRN 4692190. https://papers.ssrn.com/sol3/Delivery.cfm/4692190.pdf?abstractid=4692190 — akses 13 Jun 2026.
- Brogaard, Han & Won (2023), *Does 0DTE Options Trading Increase Volatility?*, SSRN 4426358. https://papers.ssrn.com/sol3/Delivery.cfm/4426358.pdf?abstractid=4426358 — akses 13 Jun 2026.
- Avellaneda & Lipkin (2003), *A market-induced mechanism for stock pinning*, Quantitative Finance. https://www.cis.upenn.edu/~mkearns/finread/PinningPaper.pdf — akses 13 Jun 2026.
- *Pinning in the S&P 500 futures*, JFE (2012). https://www.sciencedirect.com/science/article/abs/pii/S0304405X12001365 — akses 13 Jun 2026.
- López de Prado & Bailey (2021), *The False Strategy Theorem* (daftar publikasi). https://www.quantresearch.org/Publications.htm — akses 13 Jun 2026.

**Sumber industri — data volume/likuiditas 0DTE**

- Cboe, *The State of the Options Industry: 2025*. https://www.cboe.com/insights/posts/the-state-of-the-options-industry-2025/ — akses 13 Jun 2026.
- Cboe, *SPX 0DTE Options Jump to 61% Share*. https://www.cboe.com/insights/posts/spx-0-dte-options-jump-to-61-share-on-retail-resurgence/ — akses 13 Jun 2026.
- Cboe (Mandy Xu), *Much Ado About 0DTEs*. https://www.cboe.com/insights/posts/volatility-insights-evaluating-the-market-impact-of-spx-0-dte-options/ — akses 13 Jun 2026.
- Charles Schwab, *What Are 0DTE Options? Learn the Basics*. https://www.schwab.com/learn/story/zeroing-on-0dte-options-learn-basics — akses 13 Jun 2026.
- Merrill Edge, *0DTE Options* (rollout Tue/Thu 2022). https://www.merrilledge.com/investment-products/options/0dte-options-trading — akses 13 Jun 2026.

**Komunitas (rumus GEX praktisi — bukan vendor resmi)**

- Perfiliev, *How to calculate Gamma Exposure and Zero Gamma Level*. https://perfiliev.com/blog/how-to-calculate-gamma-exposure-and-zero-gamma-level/ — akses 13 Jun 2026.
- Matteo Ferrara, *gex-tracker* (GitHub). https://github.com/Matteo-Ferrara/gex-tracker — akses 13 Jun 2026.

<aside>
🔬

**Status verifikasi yang masih terbuka (jujur):** (1) String `asset`/parent persis tiap keluarga weekly ES/NQ di Databento — **[PERLU VERIFIKASI runtime]**. (2) Angka likuiditas ES/NQ daily per-keluarga — **[TIDAK DITEMUKAN]** di sumber primer sesi ini. (3) Arah temuan kuantitatif Brogaard et al. — belum dikutip detail (baca PDF penuh sebelum parafrase). (4) Apakah print OPRA benar-benar tanpa flag arah — **[INFERENSI kuat]**, sebaiknya dikonfirmasi ke spesifikasi OPRA Binary Participant Interface.

</aside>