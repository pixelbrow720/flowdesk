<aside>
🧭

**Tujuan dokumen:** membongkar metodologi, matematika, dan encoding visual heatmap gamma SpotGamma TRACE sampai level yang cukup untuk **replikasi 1:1 dari nol**, plus pembanding OptionsDepth, GEXBOT, dan MenthorQ.

Setiap klaim ditandai **[FAKTA]** (terdokumentasi + sumber) atau **[INFERENSI]** (kesimpulan teknis saya). Bagian yang tidak dipublikasi ditandai **[PROPRIETARY]** dengan strategi reverse-engineering.

</aside>

<aside>
⚖️

**Legenda penanda**

- **[FAKTA]** — dinyatakan eksplisit di sumber resmi/primer (link disertakan).
- **[INFERENSI]** — kesimpulan rekayasa saya dari prinsip kuantitatif standar; bukan klaim resmi vendor.
- **[PROPRIETARY]** — model/parameter internal vendor yang tidak dipublikasikan.
- **[TIDAK TERDOKUMENTASI]** — saya tidak menemukan sumber; jangan dianggap fakta.
</aside>

## Ringkasan eksekutif

TRACE adalah visualisasi **medan tekanan hedging dealer** pada ruang **(waktu × harga)** untuk opsi SPX, dibangun di atas *Options Inventory Model* milik SpotGamma, update **tiap 1 menit** dengan **proyeksi forward 5 hari**, dan punya tiga lensa: **Gamma, Delta Pressure, Charm Pressure**, plus panel **Strike Plot**.[[1]](https://support.spotgamma.com/hc/en-us/articles/33607907909011-What-is-SpotGamma-TRACE)[[2]](https://spotgamma.com/nexusfi/)

Inti matematika yang bisa direplikasi (terdokumentasi resmi SpotGamma):

$$
GEX_{strike} = \Gamma_{opsi} \times OI \times \text{Contract Size} \times S^2 \times 0.01
$$

dengan konvensi dealer **long call / short put** pada produk indeks, dan put dikalikan −1.[[3]](https://spotgamma.com/gamma-exposure-gex/)[[4]](https://support.spotgamma.com/hc/en-us/articles/15246735925395-DDOI-Dealer-Directional-Positioning)

Yang **proprietary** adalah: (a) cara mereka menentukan *siapa* yang long/short dari klasifikasi tiap trade (Options Inventory Model / Synthetic OI), (b) parameter smoothing/kontur visual, (c) Volatility Trigger & Risk Pivot. Bagian inilah yang harus di-reverse-engineer.

---

# A. KONSEP & TUJUAN

## A1. Apa yang sebenarnya divisualisasikan TRACE, dan kenapa time × price?

**Apa yang dipetakan.** TRACE memvisualkan **bagaimana aktivitas pasar opsi menekan pergerakan harga intraday SPX** — yaitu zona support/resistance dan zona volatilitas tinggi, lewat strike plot + heatmap.[[1]](https://support.spotgamma.com/hc/en-us/articles/33607907909011-What-is-SpotGamma-TRACE) **[FAKTA]** Pada lensa Gamma (default Market Maker), warna menyatakan area realized volatility lebih tinggi/rendah; kekuatan zona ditunjukkan kedalaman warna (biru tua / merah tua).[[1]](https://support.spotgamma.com/hc/en-us/articles/33607907909011-What-is-SpotGamma-TRACE) **[FAKTA]**

**Kenapa (waktu × harga), bukan cuma profil per strike?** Karena gamma dealer **tidak statis** — ia berubah sepanjang hari karena dua hal:

1. **Waktu** → time-decay (charm) mengubah gamma/delta tiap menit; pengaruh 0DTE makin besar mendekati close.[[5]](https://www.optionsdepth.com/resouce/market-makers-gamma-exposure-projection) **[FAKTA — dinyatakan OptionsDepth; konsep identik dipakai TRACE]**
2. **Harga** → gamma adalah fungsi jarak spot ke strike, jadi nilainya beda di tiap level harga hipotetis.[[3]](https://spotgamma.com/gamma-exposure-gex/) **[FAKTA]**

Profil 1-D "GEX by strike" hanya snapshot satu titik waktu. Untuk menangkap **evolusi medan** (kapan & di mana tekanan menguat/meluruh) butuh sumbu kedua = waktu. OptionsDepth menyebut produk mereka secara eksplisit "a projection across time and underlying price".[[6]](https://www.youtube.com/watch?v=RyQ6dJWyhrw) **[FAKTA]** Jadi formatnya adalah **permukaan/medan** GEX, bukan kurva. **[INFERENSI: alasan desain]**

> Sumber: SpotGamma TRACE support, SpotGamma GEX page, OptionsDepth Gamma Exposure Projection.
> 

## A2. Cara trader membaca "karakter harga" dari medan ini + intuisi warna

**Aturan baca (terdokumentasi):**

- **Zona biru = MM gamma positif → volatilitas rendah / pinning.** Harga cenderung *support/resistance* dan menempel. Pinning paling mungkin di zona biru (impact terbesar saat EOD).[[7]](https://support.spotgamma.com/hc/en-us/articles/33608037264787-What-is-the-Gamma-Heatmap) **[FAKTA]**
- **Zona merah = MM gamma negatif → volatilitas tinggi.** Harga bergerak cepat menembus area ini.[[7]](https://support.spotgamma.com/hc/en-us/articles/33608037264787-What-is-the-Gamma-Heatmap) **[FAKTA]**
- **Zona putih (light mode) / hitam (dark mode) = transisi netral, sedikit hedging.**[[7]](https://support.spotgamma.com/hc/en-us/articles/33608037264787-What-is-the-Gamma-Heatmap) **[FAKTA]**

**Mekanisme di balik warna (intuisi):**

- Gamma positif → dealer "buy the dip, sell the rip" → meredam gerak (mean-reverting, range sempit).[[3]](https://spotgamma.com/gamma-exposure-gex/) **[FAKTA]**
- Gamma negatif → dealer hedge searah gerak → memperbesar gerak (pro-cyclical, vol meledak).[[3]](https://spotgamma.com/gamma-exposure-gex/) **[FAKTA]**

**Ridge / valley (topografi)** — analogi resmi OptionsDepth: permukaan tinggi = gamma besar = seperti "mendaki gunung", harga sulit menembus → support/resistance (gamma peaks, garis hijau). Lembah = gamma rendah = "path of least resistance", harga mudah lewat (gamma troughs, garis kuning).[[5]](https://www.optionsdepth.com/resouce/market-makers-gamma-exposure-projection) **[FAKTA — OptionsDepth]**

**Gamma flip / Zero Gamma** = level harga di mana net gamma dealer menyilang dari positif ke negatif; di atasnya pasar stabil, di bawahnya destabil.[[3]](https://spotgamma.com/gamma-exposure-gex/) **[FAKTA]** Di heatmap, ini tampak sebagai **batas warna biru→merah** yang membelah medan secara horizontal. **[INFERENSI: representasi visual]**

**Delta Pressure lens:** zona biru di bawah harga = dukungan beli (dealer harus beli futures), zona merah = jual; garis kontur rapat sering menuntun harga ke target penutupan.[[8]](https://spotgamma.com/options-delta-pressure-explained/)[[9]](https://www.youtube.com/watch?v=UTuPIirTsfY) **[FAKTA]**

> Sumber: SpotGamma Gamma Heatmap support, Delta Pressure explained, OptionsDepth projection.
> 

---

# B. DATA & MATEMATIKA

## B3. Perhitungan GEX (Gamma Exposure) — rumus lengkap

### Rumus per kontrak (terdokumentasi SpotGamma)

$$
GEX_{i} = \Gamma_{i} \times OI_{i} \times \text{ContractSize} \times S^{2} \times 0.01
$$

dengan **aturan kritis: hasil opsi PUT dikalikan −1** (karena asumsi dealer short put).[[3]](https://spotgamma.com/gamma-exposure-gex/) **[FAKTA]**

Versi setara di support center SpotGamma:

$$
GEX = \Gamma \times OI \times \text{ContractMultiplier} \times S^{2}, \qquad NetGEX = \sum Call\,GEX - \sum Put\,GEX
$$

dijumlahkan ke seluruh strike & ekspirasi.[[10]](https://support.spotgamma.com/hc/en-us/articles/15214161607827-GEX-Gamma-Exposure-Explained-What-It-Is-and-How-SpotGamma-Uses-It) **[FAKTA]**

### Pembongkaran tiap faktor

| Faktor | Arti | Catatan |
| --- | --- | --- |
| `Γ` (gamma unit) | ∂²V/∂S² per 1 lembar, dari Black-Scholes | Harus dihitung ulang saat S berubah (lihat B7) [FAKTA] |
| `OI` | Open Interest (kontrak outstanding) | Basis posisi; lihat OI vs Volume di bawah |
| `ContractSize` = 100 | Multiplier 1 kontrak = 100 lembar | Standar opsi ekuitas/indeks [FAKTA] |
| `S²` | Spot kuadrat | 1× S mengubah gamma share→delta share menjadi $; 1× S lagi dari faktor 1% (0.01·S) [INFERENSI penurunan] |
| `0.01` | Per gerakan 1% | GEX = $ notional yang harus di-hedge per **1% move** [FAKTA] |

**Penurunan faktor notional / "$ per 1% move":** gamma = perubahan delta per $1 move. Dikali OI×100 → perubahan delta share agregat per $1. Dikali S → nilai $ per $1 move. Dikali (0.01·S) → nilai $ per **1%** move ⇒ total faktor `S² × 0.01`.[[11]](https://www.reddit.com/r/algotrading/comments/g4poro/how_does_squeezemetrics_calculate_gex_dealer/)[[12]](https://unusualwhales.com/information/what-is-gamma-exposure-gex) **[INFERENSI didukung sumber: konvensi "per 1% move" dipakai mayoritas platform]**

> Catatan: SqueezeMetrics whitepaper memakai varian `OI × Γ × 100 × spot` (denominasi share→$), tanpa S² eksplisit; perbedaan ada karena faktor "per 1%" diterapkan terpisah.[[11]](https://www.reddit.com/r/algotrading/comments/g4poro/how_does_squeezemetrics_calculate_gex_dealer/) **[FAKTA]**
> 

### Konvensi tanda dealer (penting & beda per produk)

- **Produk INDEKS (SPX):** dealer dimodelkan **long call, short put**. Alasan: ubiquity dari collar & covered call membuat customer net jual call / beli put, jadi dealer di sisi seberang.[[4]](https://support.spotgamma.com/hc/en-us/articles/15246735925395-DDOI-Dealer-Directional-Positioning) **[FAKTA]**
- **Single-stock (Equity Hub):** SpotGamma memodelkan dealer **short call DAN short put**.[[4]](https://support.spotgamma.com/hc/en-us/articles/15246735925395-DDOI-Dealer-Directional-Positioning) **[FAKTA]**
- Konvensi "naif" umum publik: call gamma +, put gamma −.[[13]](https://perfiliev.com/blog/how-to-calculate-gamma-exposure-and-zero-gamma-level/) **[FAKTA]**

### Open Interest vs Volume

- OI resmi hanya update **semalam (overnight)** — snapshot kemarin.[[3]](https://spotgamma.com/gamma-exposure-gex/) **[FAKTA]**
- SpotGamma memakai **OI & Volume Adjustment model / Options Inventory Model** untuk **mengestimasi perubahan posisi intraday dari volume trade live**, menghasilkan GEX near-real-time.[[3]](https://spotgamma.com/gamma-exposure-gex/)[[1]](https://support.spotgamma.com/hc/en-us/articles/33607907909011-What-is-SpotGamma-TRACE) **[FAKTA]**
- Model dihitung pada **4 ekspirasi terdekat termasuk 0DTE**.[[3]](https://spotgamma.com/gamma-exposure-gex/) **[FAKTA]**
- **Cara persis volume diklasifikasi (buy vs sell, customer vs dealer) = [PROPRIETARY].** Disebut "proprietary algorithms" + "multiple new data feeds".[[14]](https://support.spotgamma.com/hc/en-us/articles/39946919887891-What-is-the-Equity-Hub-Synthetic-OI-Open-Interest-Model)

> Sumber: SpotGamma GEX page, GEX support article, DDOI article, Synthetic OI model, SqueezeMetrics thread, Perfiliev.
> 

## B4. Perhitungan DEX (Delta Exposure) & beda dengan GEX

### Rumus DEX (terdokumentasi pihak ketiga, konsisten)

$$
DEX = \sum_{i} \delta_{i} \times OI_{i} \times 100 \times S \times sign_i
$$

dengan `sign = +1` call, `−1` put (konvensi dealer), δ = delta Black-Scholes.[[15]](https://flashalpha.com/concepts/dex) **[FAKTA — FlashAlpha; rumus generik industri]**

### Perbedaan inti GEX vs DEX

| Aspek | GEX (Gamma) | DEX / Delta Pressure |
| --- | --- | --- |
| Greek | Γ (orde-2) | δ (orde-1) |
| Faktor S | `S²·0.01` (per 1% move) | `S` (notional delta) |
| Membaca | Stabilitas vs volatilitas (besarnya hedging) | Arah/bias direksional (push beli/jual) |
| Lensa TRACE | Gamma | Delta Pressure |

**Beda makna:** GEX = *seberapa agresif* dealer harus re-hedge (magnitudo → volatilitas/pinning). Delta Pressure = *ke arah mana* dealer dipaksa beli/jual futures (zona biru = beli/support, merah = jual/resistance).[[8]](https://spotgamma.com/options-delta-pressure-explained/)[[16]](https://support.spotgamma.com/hc/en-us/articles/15350839753875-What-is-the-SpotGamma-Delta-Model) **[FAKTA]** SpotGamma menyebut Delta Pressure = "net change in options delta positioning across all prices and time frames".[[1]](https://support.spotgamma.com/hc/en-us/articles/33607907909011-What-is-SpotGamma-TRACE) **[FAKTA]**

> Catatan terminologi: "Delta Pressure" di TRACE adalah **perubahan/net delta hedging** sepanjang harga & waktu, bukan sekadar DEX statis. Detail transformasi persisnya **[PROPRIETARY]**.
> 

> Sumber: FlashAlpha DEX, SpotGamma Delta Pressure & Delta Model, TRACE support.
> 

## B5. Model greeks, sumber IV, dan rate

- **Model:** SpotGamma secara eksplisit menyuruh pakai **Black-Scholes** untuk menghitung ulang unit gamma tiap opsi pada rentang harga hipotetis.[[3]](https://spotgamma.com/gamma-exposure-gex/) **[FAKTA]**
- **Black-Scholes vs Black-76:** SPX adalah opsi indeks Eropa cash-settled ⇒ Black-Scholes-Merton (dengan dividend yield q) adalah model alami. **[INFERENSI]** Black-76 dipakai bila underlying adalah **futures** (mis. opsi pada /ES). TRACE memetakan **SPX options** (lalu di-overlay ke price), jadi BSM-on-index lebih tepat. **[INFERENSI]** Vendor tidak menyebut model futures untuk TRACE — **[TIDAK TERDOKUMENTASI untuk pilihan BS vs B76 secara spesifik]**.
- **Sumber IV:** **[TIDAK TERDOKUMENTASI di SpotGamma].** Praktik standar industri: solve IV dari **mid price** (rata-rata bid/ask) tiap kontrak via **Newton-Raphson** (atau bisection jika vega kecil/near-expiry).[[17]](https://www.interactivebrokers.com/campus/ibkr-quant-news/black-scholes-option-pricing-formula-the-backbone-of-modern-option-pricing/) **[INFERENSI didukung sumber generik]**
- **Risk-free rate:** **[TIDAK TERDOKUMENTASI].** Standar modern = kurva **SOFR / OIS** per tenor; ditambah **dividend yield SPX** untuk variannya Merton.[[18]](https://arxiv.org/html/2506.17511v1) **[INFERENSI didukung sumber metodologi SPX]**

> Sumber: SpotGamma GEX blueprint (Black-Scholes), IBKR Black-Scholes, arXiv dataset SPX (rate+dividend).
> 

## B6. Pembentukan matriks heatmap

**Struktur (dikonfirmasi sebagian):**

- **Sumbu X = waktu intraday.** Update **tiap 1 menit** (+ proyeksi forward 5 hari via calendar dropdown).[[1]](https://support.spotgamma.com/hc/en-us/articles/33607907909011-What-is-SpotGamma-TRACE)[[7]](https://support.spotgamma.com/hc/en-us/articles/33608037264787-What-is-the-Gamma-Heatmap) **[FAKTA — resolusi 1 menit untuk intraday]**
- **Sumbu Y = level harga / strike SPX.** Heatmap & strike plot disusun agar level kiri (gamma/delta/OI) match dengan price action di kanan pada sumbu harga yang sama.[[19]](https://support.spotgamma.com/hc/en-us/articles/39946617292691-What-is-the-Synthetic-OI-Live-Price-SG-Levels-Chart) **[FAKTA untuk chart Synthetic OI; INFERENSI bahwa TRACE align serupa]**
- **Nilai sel = net $ gamma (atau delta/charm) MM** pada (harga, waktu) itu. **[INFERENSI — konsisten dgn deskripsi "impact of options across time and strike price"]**[[1]](https://support.spotgamma.com/hc/en-us/articles/33607907909011-What-is-SpotGamma-TRACE)

**Dari mana nilai per (waktu, strike) berasal:** snapshot posisi (Options Inventory Model) di tiap menit → untuk tiap kolom waktu `t`, ambil inventory dealer saat itu, lalu evaluasi greek-nya pada grid harga `y`. **[INFERENSI]** Untuk kolom **forward** (masa depan), waktu-ke-ekspirasi dikurangi sehingga greek dihitung ulang dengan `T` lebih kecil (efek charm/decay). **[INFERENSI]**

> Sumber: TRACE support (1-min, 5-day), Gamma Heatmap support, Synthetic OI Live Price chart.
> 

## B7. "Field projection" — smear/kernel ATAU re-evaluasi gamma? (ini kunci)

**Jawaban yang paling didukung bukti: re-evaluasi gamma di tiap level harga hipotetis — BUKAN smear Gaussian.**

Bukti primer:

- SpotGamma Phase 3: "Using a Black-Scholes formula, **recalculate the unit gamma for every option across a wide range of hypothetical spot levels** (±10%)… Run the GEX formula across all levels."[[3]](https://spotgamma.com/gamma-exposure-gex/) **[FAKTA]**
- OptionsDepth: "calculating the **entire gamma exposure** of MM portfolios and **projecting it throughout the session** … instead of a linear value, a **surface map**."[[5]](https://www.optionsdepth.com/resouce/market-makers-gamma-exposure-projection) **[FAKTA]**
- Moomoo (penjelasan generik kurva GEX agregat): "for each assumed price, **gamma of every option is recalculated**, all strikes & expirations summed."[[20]](https://www.moomoo.com/us/learn/detail-gamma-exposure-gex-understanding-dealer-hedging-flows-and-key-levels-107906-260473079) **[FAKTA — generik]**

**Mekanisme (rekonstruksi):**

1. Bangun grid harga hipotetis `S_y` (mis. ±5–10% dari spot, langkah 1–5 poin SPX).
2. Untuk tiap `S_y` dan tiap kontrak: hitung ulang `Γ(S_y, K, T, σ_K, r, q)` via Black-Scholes (σ tetap = IV strike itu, atau digeser sticky-strike/sticky-moneyness — **[PROPRIETARY/asumsi]**).
3. Net-kan dengan tanda dealer & inventory → `NetGamma$(S_y, t)`.
4. Ulangi untuk tiap kolom waktu `t`. Hasil = matriks/permukaan halus secara alami (karena Γ(S) sendiri smooth & berbentuk lonceng di sekitar strike).

**Kenapa terlihat "di-smear"?** Karena gamma Black-Scholes terhadap S **secara intrinsik berbentuk kurva lonceng** (puncak di sekitar strike, melebar saat IV/T besar). Jadi penghalusan muncul **dari matematika gamma itu sendiri**, bukan kernel buatan. **[INFERENSI kuat]** Smoothing visual tambahan (interpolasi bilinear/contour) mungkin ada tapi **[TIDAK TERDOKUMENTASI]**.

> Alternatif (kalau mau cepat & murah): smear tiap strike-GEX dengan kernel Gaussian sepanjang harga. Ini **aproksimasi** yang menghasilkan tampilan mirip, tapi **secara metodologis berbeda** dari re-evaluasi BS dan kurang akurat di near-expiry. **[INFERENSI]**
> 

> Sumber: SpotGamma GEX Phase 3, OptionsDepth projection, Moomoo aggregated GEX.
> 

---

# C. ENCODING VISUAL (untuk replikasi persis)

## C8. Colormap & normalisasi

- **Diverging, berpusat di nol.** Biru = gamma positif, merah = gamma negatif, netral = putih (light) / hitam (dark).[[7]](https://support.spotgamma.com/hc/en-us/articles/33608037264787-What-is-the-Gamma-Heatmap) **[FAKTA]** OptionsDepth: positif biru, negatif merah.[[5]](https://www.optionsdepth.com/resouce/market-makers-gamma-exposure-projection) **[FAKTA]**
- **Simetri & domain:** karena diverging dan netral tepat di 0, titik tengah colormap = 0 ⇒ `vmin = −vmax`, `vmax = max|GEX|`. **[INFERENSI — standar diverging colormap; vendor tak publikasi angka]**
- **Anti-skew outlier:** **[TIDAK TERDOKUMENTASI].** Opsi standar yang menghasilkan tampilan TRACE:
    - **Percentile clipping** (mis. clip ke kuantil 98–99 dari |GEX|), atau
    - **Signed-log / symlog**: `sign(x)·log(1+|x|/c)`, atau
    - **Robust scaling** per-frame.
    
    Ini perlu agar 0DTE spike tidak "membakar" seluruh skala. **[INFERENSI]**
    

> Rekomendasi replikasi: diverging `RdBu` (dibalik) atau colormap custom biru→hitam/putih→merah, `TwoSlopeNorm(vcenter=0)` + clipping persentil.
> 

> Sumber: Gamma Heatmap support, OptionsDepth projection.
> 

## C9. Efek "topografi" — kontur eksplisit atau gradient?

**Keduanya, tapi kontur eksplisit ADA.**

- OptionsDepth: **garis isoline eksplisit** — gamma peaks = garis hijau, troughs = garis kuning; juga ada mode 3D surface.[[5]](https://www.optionsdepth.com/resouce/market-makers-gamma-exposure-projection) **[FAKTA]**
- SpotGamma Delta Pressure: "**dense contour lines** often guide price toward closing levels" ⇒ ada isoline.[[8]](https://spotgamma.com/options-delta-pressure-explained/) **[FAKTA]**

**Teknik render (rekonstruksi):** heatmap kontinu (gradient warna) **+ overlay kontur** dihasilkan via **marching squares** (mis. `d3-contour` di web, `matplotlib.contour` di Python) pada field `NetGamma$(y,t)`. Garis ridge/valley = isoline pada level tertentu / lokal maxima-minima sepanjang sumbu harga. **[INFERENSI kuat]**

> Sumber: OptionsDepth (peaks/troughs lines, 3D), SpotGamma Delta Pressure (contour lines).
> 

## C10. Overlay garis harga aktual

- **SpotGamma:** harga real-time dioverlay di atas medan; "Real Time Updates" chart = harga live vs level, sumbu Y = harga, X = waktu.[[21]](https://support.spotgamma.com/hc/en-us/articles/15350634159123-What-is-the-Real-Time-Updates-index-chart) **[FAKTA]** Bentuk persis (candle vs line) di TRACE **[TIDAK TERDOKUMENTASI eksplisit]**; demo menunjukkan price action overlay.
- **OptionsDepth:** memakai **marker kuning = harga close candlestick** untuk timeframe terpilih, di atas surface/heatmap.[[5]](https://www.optionsdepth.com/resouce/market-makers-gamma-exposure-projection) **[FAKTA]**
- **Sumbu Y bersama:** ya — harga & medan berbagi sumbu harga yang sama agar overlay sejajar.[[19]](https://support.spotgamma.com/hc/en-us/articles/39946617292691-What-is-the-Synthetic-OI-Live-Price-SG-Levels-Chart) **[FAKTA untuk chart SG; INFERENSI untuk TRACE]**

> Replikasi: plot candle/line dengan sumbu y = harga, x = waktu, di layer paling atas (alpha penuh) di atas heatmap.
> 

> Sumber: SpotGamma Real-Time chart, Synthetic OI Live Price chart, OptionsDepth.
> 

## C11. Panel kiri "GEX by Strike" (Strike Plot) & alignment

- **Strike Plot** menampilkan **GEX, OI, Net OI** sebagai **bar berwarna per strike**; **call = oranye, put = biru**; biru = positif (support), merah = negatif (resistance) untuk GEX.[[22]](https://support.spotgamma.com/hc/en-us/articles/33608227551379-What-is-the-Strike-Plot-in-TRACE)[[3]](https://spotgamma.com/gamma-exposure-gex/) **[FAKTA]**
- **Hubungan dgn heatmap:** Strike Plot = **profil 1-D pada sumbu harga yang sama** dengan sumbu Y heatmap; ia adalah "irisan" snapshot saat ini, heatmap = evolusinya sepanjang waktu. Chart SG dirancang "to match up price action on the right with levels on the left".[[19]](https://support.spotgamma.com/hc/en-us/articles/39946617292691-What-is-the-Synthetic-OI-Live-Price-SG-Levels-Chart) **[FAKTA align kiri-kanan; INFERENSI bahwa strike plot share y-axis dgn heatmap]**
- Ada **0DTE toggle** untuk isolasi posisi same-day.[[22]](https://support.spotgamma.com/hc/en-us/articles/33608227551379-What-is-the-Strike-Plot-in-TRACE) **[FAKTA]**

> Replikasi: subplot kiri berbagi `sharey` dengan heatmap; bar horizontal per strike, dwiwarna call/put.
> 

> Sumber: Strike Plot support, GEX page, Synthetic OI Live Price chart.
> 

## C12. Key levels: Call Wall, Put Wall, Gamma Flip — hitung & gambar

- **Call Wall** = strike dgn **konsentrasi net call gamma tertinggi** (resistance utama).[[3]](https://spotgamma.com/gamma-exposure-gex/) **[FAKTA]**
- **Put Wall** = strike dgn **net put gamma terbesar (paling negatif)** (support utama).[[3]](https://spotgamma.com/gamma-exposure-gex/) **[FAKTA]**
- **Gamma Flip / Zero Gamma** = harga di mana **kurva net GEX agregat menyilang nol** (dari profil GEX vs hypothetical price). Cari root: `Σ NetGEX(S) = 0`.[[3]](https://spotgamma.com/gamma-exposure-gex/)[[23]](https://flashalpha.com/tools/gamma-exposure) **[FAKTA]**
- **Volatility Trigger™ & Risk Pivot** = level **[PROPRIETARY]** SpotGamma (bukan crossover OI sederhana; dari distribusi gamma dealer).[[3]](https://spotgamma.com/gamma-exposure-gex/)

**Gambar:** garis horizontal (level harga) melintang penuh di heatmap pada y = level; Call/Put Wall sering dilabeli; Gamma Flip = batas rezim. **[INFERENSI representasi]**

> Sumber: SpotGamma GEX page (definisi semua level), FlashAlpha gamma flip.
> 

---

# D. REPLIKASI

## DATA CONTRACT (tipe data input final)

```python
# === INPUT MENTAH (per snapshot waktu t) ===
OptionQuote = {
    "expiry": date,            # tanggal ekspirasi
    "strike": float,           # K
    "type": "C" | "P",
    "bid": float, "ask": float,# untuk mid -> solve IV
    "open_interest": int,      # OI resmi (overnight)
    "volume": int,             # volume kumulatif hari ini
    "iv": float | None,        # bila vendor sediakan; else solve
}

MarketState = {
    "timestamp": datetime,     # resolusi 1 menit
    "spot": float,             # S (SPX)
    "risk_free_curve": Callable[[float], float],  # r(T); SOFR/OIS [INFERENSI]
    "dividend_yield": float,   # q SPX [INFERENSI]
}

# === POSISI DEALER (hasil Options Inventory Model — PROPRIETARY) ===
# Aproksimasi reverse-engineer: signed_position per kontrak
DealerPosition = {
    "contract_id": str,
    "signed_qty": float,       # + long, - short (sisi dealer)
}

# === OUTPUT: FIELD UNTUK HEATMAP ===
GammaField = {
    "time_axis": List[datetime],          # X (kolom)
    "price_axis": List[float],            # Y (grid harga hipotetis)
    "values": np.ndarray,                 # shape [n_price, n_time], net $ gamma per 1%
    "price_overlay": List[(datetime, float)],  # harga aktual / close
    "key_levels": {"call_wall": float, "put_wall": float, "gamma_flip": float},
}
```

## ALGORITMA RENDER (langkah + pseudo-code end-to-end)

**Langkah konseptual:**

1. Ambil chain + spot + rate/div tiap menit.
2. Solve IV per kontrak dari mid (Newton-Raphson) bila tak tersedia.
3. Tentukan posisi dealer (Inventory Model; lihat reverse-engineering).
4. Bangun grid harga hipotetis `S_y`.
5. Untuk tiap (kolom waktu t) × (level harga S_y): re-evaluasi gamma BS tiap kontrak, kalikan signed qty & faktor notional, jumlahkan → `field[y, t]`.
6. Hitung key levels (walls = argmax/argmin net gamma per strike; flip = root NetGEX(S)=0).
7. Render: heatmap diverging (norm center 0 + clip persentil) → overlay kontur (marching squares) → overlay garis harga → panel kiri strike plot (sharey).

```python
from scipy.stats import norm
import numpy as np

def bs_gamma(S, K, T, sigma, r, q):
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = (np.log(S/K) + (r - q + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    return np.exp(-q*T) * norm.pdf(d1) / (S * sigma * np.sqrt(T))

def bs_delta(S, K, T, sigma, r, q, is_call):
    d1 = (np.log(S/K) + (r - q + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    return (np.exp(-q*T)*norm.cdf(d1)) if is_call else (np.exp(-q*T)*(norm.cdf(d1)-1))

def solve_iv(mid_price, S, K, T, r, q, is_call):
    sigma = 0.20
    for _ in range(100):                     # Newton-Raphson
        price = bs_price(S, K, T, sigma, r, q, is_call)
        vega  = bs_vega(S, K, T, sigma, r, q)
        if vega < 1e-8: break
        diff = price - mid_price
        if abs(diff) < 1e-6: break
        sigma -= diff / vega
        sigma = max(1e-4, min(sigma, 5.0))
    return sigma

def build_gamma_field(snapshots, price_grid, contract_mult=100):
    n_y, n_t = len(price_grid), len(snapshots)
    field = np.zeros((n_y, n_t))
    for j, snap in enumerate(snapshots):          # sumbu X: waktu (1 menit)
        for c in snap.contracts:
            T = year_frac(snap.timestamp, c.expiry)
            iv = c.iv or solve_iv(c.mid, snap.spot, c.strike, T,
                                  snap.r(T), snap.q, c.is_call)
            sgn = dealer_sign(c)                  # +1 long / -1 short (Inventory Model)
            qty = c.signed_qty                    # hasil model posisi
            for i, Sy in enumerate(price_grid):   # sumbu Y: harga hipotetis
                g = bs_gamma(Sy, c.strike, T, iv, snap.r(T), snap.q)
                # notional $ gamma per 1% move, ditandai sisi dealer
                field[i, j] += sgn * qty * g * contract_mult * Sy**2 * 0.01
    return field

def render(field, price_grid, time_axis, price_line, strikes_gex):
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm
    vmax = np.percentile(np.abs(field), 99)       # anti-skew outlier
    norm_ = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
    fig, (axL, axM) = plt.subplots(1, 2, sharey=True,
                                   gridspec_kw={"width_ratios":[1,5]})
    # panel kiri: GEX by strike (call oranye / put biru)
    axL.barh(strikes_gex.K, strikes_gex.gex,
             color=np.where(strikes_gex.is_call, "orange", "royalblue"))
    # heatmap
    axM.pcolormesh(time_axis, price_grid, field, cmap="RdBu", norm=norm_)
    # kontur (topografi)
    axM.contour(time_axis, price_grid, field, levels=12,
                colors="k", linewidths=0.4, alpha=0.5)
    # overlay harga
    axM.plot(time_axis, price_line, color="yellow", lw=1.5)
    return fig
```

**[INFERENSI]** Seluruh pseudo-code ini adalah rekonstruksi metodologi publik (BS recompute + diverging heatmap + kontur). Bagian `dealer_sign`/`signed_qty` = titik PROPRIETARY.

## D14. Rekomendasi teknologi render

| Kebutuhan | Rekomendasi | Catatan |
| --- | --- | --- |
| Heatmap besar (ribuan sel × menit), web | **WebGL** via `regl`/`deck.gl` (layer `BitmapLayer`/`HeatmapLayer`) atau `PixiJS` | Hindari SVG per-cell; pakai texture/GPU [INFERENSI] |
| Kontur / isoline | **d3-contour** (marching squares) lalu render path; atau hitung server-side | Untuk garis ridge/valley [INFERENSI] |
| Prototipe / riset | Python `matplotlib pcolormesh + contour`, atau `datashader` untuk data raksasa | Cepat untuk validasi metodologi |
| Interpolasi grid | Bilinear untuk tampilan; tapi **nilai harus dari re-evaluasi BS**, bukan interpolasi murni | Smoothing visual ≠ smoothing data |
| Performa intraday | Hitung field incremental per menit; cache greek per kontrak; vektorisasi `numpy`/GPU | O(n_kontrak × n_price) per kolom |

**[INFERENSI]** Tech stack persis TRACE/OptionsDepth tidak dipublikasikan; OptionsDepth jelas punya mode **3D surface** (kemungkinan WebGL/three.js).[[5]](https://www.optionsdepth.com/resouce/market-makers-gamma-exposure-projection) **[FAKTA: ada 3D surface]**

## D15. Perbedaan TRACE vs OptionsDepth vs GEXBOT vs MenthorQ

| Dimensi | SpotGamma TRACE | OptionsDepth | GEXBOT | MenthorQ |
| --- | --- | --- | --- | --- |
| Model posisi | Options Inventory Model / Synthetic OI (klasifikasi trade, dealer vs customer) [FAKTA] | "Actual positioning" dari klasifikasi flow; full-portfolio [FAKTA] | Orderflow engine: klasifikasi berbasis volatilitas, presisi milidetik; sisi customer [FAKTA] | Net GEX dari OI real-time, agregasi lintas ekspirasi [FAKTA] |
| Visual utama | Heatmap (waktu×harga) 3 lensa + Strike Plot [FAKTA] | Heatmap 2D **dan 3D surface**; peaks(hijau)/troughs(kuning) [FAKTA] | Convexity ladder + profil GEX/options [FAKTA] | Gamma Levels 1–10, key levels, integrasi TradingView [FAKTA] |
| Lensa Greek | Gamma, Delta Pressure, Charm Pressure [FAKTA] | Gamma, Charm (juga vanna disebut) [FAKTA] | GEX/convexity imbalance [FAKTA] | Net GEX, DEX, Gamma/GEX levels [FAKTA] |
| Sisi konvensi | Dealer (MM default); index = long call/short put [FAKTA] | MM exposure [FAKTA] | **Customer** gex (long call/put = long customer) [FAKTA] | Net GEX (call gamma − put gamma) [FAKTA] |
| Update / forward | 1 menit + forward 5 hari [FAKTA] | Intraday & daily model [FAKTA] | Milidetik / intraday [FAKTA] | ~10 menit (mitra), level harian/intraday [FAKTA] |
| Field projection | Re-eval gamma lintas harga & waktu [FAKTA/INFERENSI] | Re-eval seluruh portfolio → surface [FAKTA] | Lebih ke ladder/flow daripada surface harga×waktu [INFERENSI] | Berbasis level, bukan surface penuh [INFERENSI] |
| Fokus | SPX intraday struktur [FAKTA] | SPX 0DTE positioning [FAKTA] | Multi-ticker, futures levels [FAKTA] | Stocks/indeks/futures, levels untuk charting [FAKTA] |

> Sumber: TRACE/Synthetic OI support; OptionsDepth projection & site; GEXBOT site & docs; MenthorQ guides (Net GEX, GEX Levels, Intraday Gamma Models).
> 

---

# YANG MASIH PROPRIETARY / ASUMSI + opsi reverse-engineering

<aside>
🔒

Bagian di bawah **tidak dipublikasikan** vendor. Untuk replikasi 1:1, ini titik yang harus kamu estimasi sendiri.

</aside>

**1. Options Inventory Model / Synthetic OI (paling krusial).**

- Status: [PROPRIETARY]. SpotGamma menyebut "proprietary algorithms + multiple new data feeds", "eliminating assumptions", update sebelum market open (Synthetic OI equity) & 1-min (TRACE).[[14]](https://support.spotgamma.com/hc/en-us/articles/39946919887891-What-is-the-Equity-Hub-Synthetic-OI-Open-Interest-Model)[[1]](https://support.spotgamma.com/hc/en-us/articles/33607907909011-What-is-SpotGamma-TRACE)
- Reverse-engineering:
    - **Trade-side classification** dari tick/quote: bandingkan harga eksekusi vs bid/ask (algoritma **Lee-Ready** / tick rule) untuk infer buy vs sell-initiated. **[INFERENSI]**
    - Akumulasi **net signed volume** per kontrak → estimasi ΔOI intraday, tambahkan ke OI overnight.
    - Mulai dari asumsi struktural index (dealer long call / short put) sebagai prior, lalu koreksi dengan flow.[[4]](https://support.spotgamma.com/hc/en-us/articles/15246735925395-DDOI-Dealer-Directional-Positioning)
    - Data: butuh feed OPRA full (kamu sudah pakai **Databento OPRA** — cocok untuk merekonstruksi signed flow).

**2. IV surface & sumber IV.** [TIDAK TERDOKUMENTASI]. Reverse: solve IV per strike dari mid (NR), bangun surface (SVI/sticky-strike), tentukan asumsi pergeseran IV saat re-eval gamma di harga hipotetis (sticky-strike vs sticky-delta). **[INFERENSI]**

**3. Rate & dividend.** [TIDAK TERDOKUMENTASI]. Reverse: pakai SOFR/OIS per tenor + dividend yield SPX implied dari put-call parity. **[INFERENSI]**

**4. Normalisasi colormap & parameter kontur.** [TIDAK TERDOKUMENTASI]. Reverse: cocokkan dengan screenshot — uji `TwoSlopeNorm(0)` + clip persentil 98–99; jumlah level kontur (≈8–15) dengan eye-matching. **[INFERENSI]**

**5. Volatility Trigger™ & Risk Pivot.** [PROPRIETARY] — "from the actual distribution of dealer gamma across strikes, not a simple OI crossover".[[3]](https://spotgamma.com/gamma-exposure-gex/) Reverse: kandidat = level di bawah spot di mana gamma support positif terakhir terkonsentrasi (mis. weighted gamma centroid / level di mana cumulative positive gamma jatuh di bawah threshold). **[INFERENSI]**

**6. Charm Pressure (transformasi persis).** [PROPRIETARY]. Terdokumentasi hanya konsep: perubahan hedging MM terhadap waktu, kuat dipengaruhi 0DTE, elemen pinning dekat node gamma positif.[[24]](https://support.spotgamma.com/hc/en-us/articles/33608198289043-What-is-the-Charm-Pressure-Heatmap) Reverse: `Charm = ∂Δ/∂t` (BS analytic), lalu dipetakan ke field seperti gamma/delta. **[INFERENSI]**

**7. Resolusi grid harga & forward-decay tepat.** [TIDAK TERDOKUMENTASI]. Reverse: pilih langkah grid 1–5 poin SPX; untuk forward 5-hari, kurangi T per hari & re-eval. **[INFERENSI]**

---

# Daftar sumber utama

**SpotGamma (primer):**

- What is SpotGamma TRACE — support center.[[1]](https://support.spotgamma.com/hc/en-us/articles/33607907909011-What-is-SpotGamma-TRACE)
- What is the Gamma Heatmap — support center.[[7]](https://support.spotgamma.com/hc/en-us/articles/33608037264787-What-is-the-Gamma-Heatmap)
- What is the Strike Plot in TRACE.[[22]](https://support.spotgamma.com/hc/en-us/articles/33608227551379-What-is-the-Strike-Plot-in-TRACE)
- What is the Charm Pressure Heatmap.[[24]](https://support.spotgamma.com/hc/en-us/articles/33608198289043-What-is-the-Charm-Pressure-Heatmap)
- Gamma Exposure (GEX) — halaman metodologi & rumus.[[3]](https://spotgamma.com/gamma-exposure-gex/)
- GEX Explained / How SpotGamma Uses It.[[10]](https://support.spotgamma.com/hc/en-us/articles/15214161607827-GEX-Gamma-Exposure-Explained-What-It-Is-and-How-SpotGamma-Uses-It)
- DDOI (Dealer-Directional Positioning).[[4]](https://support.spotgamma.com/hc/en-us/articles/15246735925395-DDOI-Dealer-Directional-Positioning)
- Synthetic OI (Open Interest) Model.[[14]](https://support.spotgamma.com/hc/en-us/articles/39946919887891-What-is-the-Equity-Hub-Synthetic-OI-Open-Interest-Model)
- Synthetic OI Live Price & SG Levels Chart.[[19]](https://support.spotgamma.com/hc/en-us/articles/39946617292691-What-is-the-Synthetic-OI-Live-Price-SG-Levels-Chart)
- Delta Model & Options Delta Pressure Explained.[[16]](https://support.spotgamma.com/hc/en-us/articles/15350839753875-What-is-the-SpotGamma-Delta-Model)[[8]](https://spotgamma.com/options-delta-pressure-explained/)
- Real Time Updates index chart.[[21]](https://support.spotgamma.com/hc/en-us/articles/15350634159123-What-is-the-Real-Time-Updates-index-chart)
- TRACE product (nexusfi description).[[2]](https://spotgamma.com/nexusfi/)

**Pembanding:**

- OptionsDepth — Market Makers' Gamma Exposure Projection.[[5]](https://www.optionsdepth.com/resouce/market-makers-gamma-exposure-projection)
- OptionsDepth — Charm Exposure Projection.[[25]](https://www.optionsdepth.com/resouce/market-makers-charm-exposure-projection)
- OptionsDepth — 1-Minute Tutorial (proyeksi waktu×harga).[[6]](https://www.youtube.com/watch?v=RyQ6dJWyhrw)
- GEXBOT — site & docs (convexity ladder, orderflow).[[26]](https://www.gexbot.com/)
- MenthorQ — Key Levels/Terms, GEX Levels, Intraday Gamma, DEX.[[27]](https://menthorq.com/guide/key-levels-and-key-terms/)[[28]](https://menthorq.com/guide/intraday-gamma-models/)[[29]](https://menthorq.com/guide/what-is-delta-exposure-dex/)

**Metodologi / kuantitatif:**

- Perfiliev — How to Calculate GEX & Zero Gamma.[[13]](https://perfiliev.com/blog/how-to-calculate-gamma-exposure-and-zero-gamma-level/)
- SqueezeMetrics thread (formula GEX).[[11]](https://www.reddit.com/r/algotrading/comments/g4poro/how_does_squeezemetrics_calculate_gex_dealer/)
- Moomoo — aggregated GEX recompute per price.[[20]](https://www.moomoo.com/us/learn/detail-gamma-exposure-gex-understanding-dealer-hedging-flows-and-key-levels-107906-260473079)
- FlashAlpha — DEX & gamma flip.[[15]](https://flashalpha.com/concepts/dex)[[23]](https://flashalpha.com/tools/gamma-exposure)
- Unusual Whales — GEX per 1% move.[[12]](https://unusualwhales.com/information/what-is-gamma-exposure-gex)
- IBKR — Black-Scholes inputs.[[17]](https://www.interactivebrokers.com/campus/ibkr-quant-news/black-scholes-option-pricing-formula-the-backbone-of-modern-option-pricing/)
- arXiv — Time Evolution of SPX Option Prices (rate+dividend dataset).[[18]](https://arxiv.org/html/2506.17511v1)

<aside>
⚠️

**Disclaimer akurasi:** rumus GEX, konvensi tanda, lensa, update 1-menit, forward 5-hari, warna, kontur OptionsDepth, dan key levels = **terdokumentasi**. Model posisi/inventory, IV solver, rate, parameter normalisasi/kontur, Volatility Trigger = **proprietary/inferensi**. Untuk replikasi 1:1 yang valid, validasi numerik field kamu terhadap screenshot TRACE pada beberapa sesi (eye-matching + uji root gamma flip).

</aside>