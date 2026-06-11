<aside>
⚠️

Riset rekayasa-balik untuk membangun ulang metrik vendor (SpotGamma, SqueezeMetrics, MenthorQ/UW/Tradytics) di atas **Databento GLBX.MDP3** untuk opsi-atas-futures **/ES** ($50/pt) & **/NQ** ($20/pt), fokus **0DTE**. Tanggal akses semua sitasi: **11 Jun 2026**. Label bukti: **[FAKTA]** = terdokumentasi vendor/akademik · **[INFERENSI]** = turunan logis dari mekanika yang diakui · **[SPEKULASI]** = dugaan tanpa konfirmasi publik. Parameter yang tak dipublikasikan ditandai "perlu kalibrasi empiris".

</aside>

Dokumen disusun agar tiap bagian (A–I) langsung dapat diterjemahkan ke modul Python. Konvensi data, model harga, dan mesin DDOI dijelaskan sekali di **Bagian 0** lalu dirujuk ulang.

## 0. Fondasi: model harga, schema, konvensi tanda, mesin DDOI

### 0.1 Black-76 (opsi-atas-futures) — [FAKTA]

Databento merekomendasikan Black-76 untuk IV/greeks opsi index-futures seperti /ES.[[1]](https://databento.com/microstructure/volatility)[[2]](https://databento.com/blog/option-greeks) Simbol: $F$=harga futures front-month, $K$=strike, $T$=tahun (day-count 365), $r=\ln(1+\text{SOFR})$, $D=e^{-rT}$, $\phi/\Phi$=PDF/CDF normal standar.

$$
d_1=\frac{\ln(F/K)+\tfrac12\sigma^2 T}{\sigma\sqrt{T}},\quad d_2=d_1-\sigma\sqrt{T}
$$

$$
\Delta_{c}=D\Phi(d_1),\ \Delta_{p}=-D\Phi(-d_1),\ \Gamma=\frac{D\,\phi(d_1)}{F\sigma\sqrt{T}},\ \mathcal V=D F\phi(d_1)\sqrt T
$$

$$
\text{Vanna}=\frac{\partial\Delta}{\partial\sigma}=-D\,\phi(d_1)\frac{d_2}{\sigma},\quad \text{Charm}=\frac{\partial\Delta}{\partial t}
$$

Charm Black-76 bentuk-tertutupnya panjang & rawan salah; **rekomendasi: finite-difference** $[\Delta(T-\tfrac1{365})-\Delta(T)]\cdot 365$ atau autodiff.[[3]](https://carlolepelaars.github.io/blackscholes/4.the_greeks_black76/) $\Gamma,\mathcal V$,Vanna identik call/put pada strike sama; hanya delta & tanda charm beda.

### 0.2 Schema GLBX.MDP3 — [FAKTA]

| Schema | Field kunci | Dipakai untuk |
| --- | --- | --- |
| definition | strike, tipe C/P, ekspirasi, multiplier, underlying_id | Bangun rantai opsi, map ke front future |
| statistics | settlement price, **open interest** resmi CME, volume | ΔOI harian, anchor IV settlement |
| trades | price, size, **side ∈ {A=sell-agрезор, B=buy-agresor, N}** | Sisi agresor NATIVE (tanpa Lee-Ready) |
| tbbo | trade + BBO tepat sebelum trade | Mid untuk IV, klasifikasi tepi pasif |
| mbp-1 | top-of-book per strike (bid/ask) | Mid IV intraday, microprice |

Field `side` pada `trades`/`tbbo` memberi sisi agresor langsung dari matching engine CME — **keunggulan struktural vs OPRA**: tak perlu Lee-Ready, single-venue (tanpa konsolidasi), OI & settlement resmi.[[4]](https://databento.com/docs/schemas-and-data-formats/trades)[[5]](https://databento.com/docs/schemas-and-data-formats/statistics)

### 0.3 Dollar-greek notional & konvensi tanda dealer — [FAKTA + INFERENSI]

SqueezeMetrics: GEX per kontrak (dalam shares) = $\Gamma\cdot OI\cdot 100\cdot k$, $k=+1$ call, $k=-1$ put, lalu didolarkan ×harga; tanda negatif put karena MM **long call / short put**.[[6]](https://squeezemetrics.com/monitor/download/pdf/white_paper.pdf) SpotGamma: dealer **short put & long call** untuk index; **short put & short call** untuk single-stock equity.[[7]](https://support.spotgamma.com/hc/en-us/articles/15246735925395-DDOI-Dealer-Directional-Positioning) Untuk /ES /NQ kita pakai konvensi index. Notional gamma per-1%-move per strike $i$:

$$
\$\Gamma_i = s_i\cdot \Gamma_i\cdot OI_i\cdot M\cdot F^2\cdot 0.01
$$

dengan $M$=multiplier (50 untuk /ES, 20 untuk /NQ), $s_i\in\{+1,-1\}$ tanda posisi dealer (naif: +call/−put; lanjutan: dari DDOI §0.4). Definisi GEX SpotGamma: "$ value yang harus dibeli/dijual MM untuk tetap delta-netral per 1% move".[[8]](https://support.spotgamma.com/hc/en-us/articles/15214161607827-GEX-Gamma-Exposure-Explained-What-It-Is-and-How-SpotGamma-Uses-It) Vanna/Charm exposure mengikuti pola yang sama (ganti $\Gamma$ dengan Vanna/Charm, sesuaikan faktor normalisasi).[[9]](https://medium.com/option-screener/so-youve-heard-about-gamma-exposure-gex-but-what-about-vanna-and-charm-exposures-47ed9109d26a)

### 0.4 Mesin DDOI (dasar bagi A, B, C, D, E, I) — [FAKTA + INFERENSI]

SqueezeMetrics mendefinisikan DDOI sebagai langkah interim sebelum GEX/VEX: "delve into transaction-level data to assess direction (buy/sell) of every trade, bin it according to how it ought to affect open interest, then **verify** trade direction by tracking the subsequent actual change in OI".[[10]](https://squeezemetrics.com/download/The_Implied_Order_Book.pdf) Pipeline rekonstruksi kita:

1. **Tandai agresor** tiap trade dari `side` (B/A). Trade `N` (mid/implied) → fallback tick-rule.[[11]](https://www.acsu.buffalo.edu/~keechung/MGF743/Readings/Inferring%20trade%20direction%20from%20intraday%20data.pdf)
2. **Klasifikasi open vs close** (tak ada label di GLBX) — heuristik §A.
3. **Akumulasi signed volume** per (strike, tipe, ekspirasi): $SV=\sum (q_{\text{buy}}-q_{\text{sell}})$.
4. **Rekonsiliasi dengan ΔOI resmi** dari `statistics` keesokan paginya: skala/atur tanda agar $\sum \Delta\text{pos}_{\text{dealer}} \approx -\Delta OI_{\text{customer}}$.
5. **Tetapkan** $s_i$ = sisi net dealer per strike. Inilah "Synthetic OI".

---

## A. Synthetic OI / DDOI / Options Inventory Model

**1. Definisi vendor.** SpotGamma DDOI = "hidden positioning of OI antara MM dan customer; hanya bisa diestimasi via modeling & asumsi".[[7]](https://support.spotgamma.com/hc/en-us/articles/15246735925395-DDOI-Dealer-Directional-Positioning) Synthetic OI Model = "lebih presisi melacak hedging flow jangka pendek… mengeliminasi asumsi dengan mengkategorikan transaksi berdasar multiple data feeds + algoritma proprietary", memperkenalkan **High Volatility Point** (gamma paling negatif) & **Low Volatility Point** (gamma paling positif).[[12]](https://support.spotgamma.com/hc/en-us/articles/39946919887891-What-is-the-Equity-Hub-Synthetic-OI-Open-Interest-Model) Model lama "Total OI" mengasumsikan opsi dijual oleh MM.[[13]](https://support.spotgamma.com/hc/en-us/articles/39946988410771-What-is-the-Equity-Hub-Total-OI-Open-Interest-Model)

**2. Mekanika yang diakui.** Update sekali per hari pra-market (jadi DDOI = stok end-of-day yang diakumulasi); MM delta-hedge mekanis tiap hari, customer tidak selalu → asimetri ini yang dimodelkan.[[7]](https://support.spotgamma.com/hc/en-us/articles/15246735925395-DDOI-Dealer-Directional-Positioning) SqueezeMetrics verifikasi arah trade lewat ΔOI aktual.[[10]](https://squeezemetrics.com/download/The_Implied_Order_Book.pdf)

**3. Hipotesis perhitungan (≥2).**

> **H-A1 — Signed-volume + rekonsiliasi ΔOI (paling mungkin).** Untuk tiap kontrak: agregasi signed volume harian $SV_t$ dari `side`. Inferensi open/close: jika OI naik ($\Delta OI_t>0$) maka mayoritas net volume = **opening**; jika turun = **closing**. Alokasikan:
> 

$$
\Delta\text{DealerPos}_t = -\,\text{sign}(SV_t^{\text{cust}})\cdot|\Delta OI_t|\ \ \text{(dealer ambil sisi lawan customer agresor)}
$$

Dealer posisi = kumulatif. Pseudocode:

```python
for k in contracts:
    sv = trades[k].buy_qty - trades[k].sell_qty      # net customer aggression
    dOI = stats[k].oi_today - stats[k].oi_prev
    opened = max(dOI, 0); closed = max(-dOI, 0)
    # customer net long if sv>0 -> dealer net short that contract
    dealer_sign = -np.sign(sv)
    dealer_pos[k] += dealer_sign * opened - dealer_sign * closed*frac_close
```

> **H-A2 — Lipton/QuikStrike-style ITM/OTM + ukuran-trade open/close split.** Probabilitas opening naik untuk trade besar, OTM, dan pagi hari; closing untuk ITM dekat ekspirasi & sore. Bobot logistik $p_{\text{open}}=\sigma(\beta_0+\beta_1\,\text{size}+\beta_2\,\text{OTMness}+\beta_3\,\text{timeofday})$, $\beta$ **perlu kalibrasi empiris** vs ΔOI.
> 

> **H-A3 — BVC (Easley) sebagai pengganti sisi agresor.** Bila ingin smoothing, pakai standardized price change untuk membagi volume tiap bar → buy/sell fraction (lihat §E).[[14]](https://tom.shohfi.com/don/pubs/01-Don-BVC.pdf)
> 

> **H-A4 — Naif (baseline):** dealer long call / short put tanpa flow (model "Total OI").[[15]](https://spotgamma.com/free-tools/spx-gamma-exposure/)
> 

**High/Low Vol Point:** $\text{HVP}=\arg\min_K \$\Gamma(K)$, $\text{LVP}=\arg\max_K \$\Gamma(K)$ memakai $s_i$ dari DDOI.[[12]](https://support.spotgamma.com/hc/en-us/articles/39946919887891-What-is-the-Equity-Hub-Synthetic-OI-Open-Interest-Model)

**4. Peringkat plausibilitas.** H-A1 (70%) — paling dekat deskripsi SqueezeMetrics & paling robust dengan data CME (sisi agresor native + ΔOI resmi). H-A2 (50%) — kemungkinan dipakai sebagai lapisan tambahan SpotGamma ("multiple feeds"). H-A3 (35%) — berguna untuk trade `N`. H-A4 (90% sebagai baseline yang pasti benar tapi kasar).

**5. Adaptasi GLBX.MDP3.** Sisi agresor langsung dari `trades.side` (tak perlu Lee-Ready) — **asumsi terpaksa**: tetap perlu inferensi open/close (tak ada label). ΔOI & settlement dari `statistics`. Front future dari `definition.underlying_id`. Per-strike contract via `definition`.

**6. Validasi.** Golden day rendah-event (mis. pertengahan minggu non-OPEX). Cek: (a) $\sum_k \Delta\text{DealerPos}=0$ identitas pasar; (b) tanda gamma flip kita vs SpotGamma harus match arah; (c) HVP/LVP strike harus match ±1 strike. Toleransi level: flip/VT match ~kira-kira (±0.3%), wall strike match persis.

**7. Jebakan.** (i) Lupa membedakan opening vs closing → DDOI bias. (ii) ΔOI CME T+1 (preliminary vs final Daily Bulletin)[[16]](https://www.cmegroup.com/market-data/volume-open-interest.html) — pakai final. (iii) Trade multi-leg/spread mencemari signed volume; saring via `definition`. (iv) Exercise/assignment menggeser OI tanpa trade.

---

## B. Zero Gamma vs Volatility Trigger vs Risk Pivot

**1. Definisi vendor.** *Zero Gamma*: "price level di mana net dealer gamma menyilang dari + ke − (atau sebaliknya)"; bukan S/R, melainkan penanda rezim.[[17]](https://support.spotgamma.com/hc/en-us/articles/15297958613907-Zero-Gamma)[[18]](https://support.spotgamma.com/hc/en-us/articles/15413261162387-Gamma-Flip) *Volatility Trigger™*: "level di bawahnya feedback loop bearish mulai aktif… umumnya support major terakhir di atas Put Wall… metode proprietary untuk menghitung **last major level of positive gamma support**".[[19]](https://support.spotgamma.com/hc/en-us/articles/15297954935699-Volatility-Trigger)[[20]](https://spotgamma.com/volatility-trigger-zero-gamma-trading/) *Risk Pivot*: batas luar zona support struktural (tidak terdokumentasi penuh).

**2. Mekanika yang diakui.** Zero Gamma = zero-crossing profil $\$\Gamma(S)$ yang dihitung ulang sepanjang grid harga hipotetis.[[21]](https://spotgamma.com/gamma-exposure-gex/) VT ≠ zero crossing — VT adalah **konsentrasi gamma positif**, jadi kuantifikasi berbasis distribusi gamma per strike, bukan titik silang. VT juga dipakai mirip "Hedge Wall" di HIRO.[[22]](https://support.bloomberg.spotgamma.com/hc/en-us/articles/20726435775379-Volatility-Trigger)

**3. Hipotesis.**

> **H-B1 Zero Gamma (titik silang).** Bangun profil $\$\Gamma_{\text{net}}(S)=\sum_i s_i\Gamma_i(S)OI_i M S^2 0.01$ untuk $S$ di grid; ZG = akar (interpolasi linier antar bar tanda berlawanan).
> 

```python
profile = [sum(sign[i]*gamma(i,S)*oi[i]*M*S*S*0.01 for i in chain) for S in grid]
zg = root_by_linear_interp(grid, profile)   # first sign change
```

Keyakinan 85%.

> **H-B2 VT = strike gamma-positif major terendah (paling mungkin).** Di antara strike dengan $\$\Gamma>0$ signifikan (di atas ambang $\tau$ kuantil), VT = strike terendah yang masih "major". $\text{VT}=\min\{K:\$\Gamma(K)>\tau\cdot\max\$\Gamma,\ \$\Gamma(K)>0\}$. $\tau$ **perlu kalibrasi** (mis. 0.3–0.5). Keyakinan 55%.
> 

> **H-B3 VT = strike yang memaksimalkan |hedging flow| sisi bawah** (turunan profil tertajam) — VT sebagai titik di mana $d(\$\Gamma)/dS$ terbesar di bawah spot. Keyakinan 35%.
> 

> **H-B4 Risk Pivot = ZG ± k·(expected move)** atau batas luar klaster gamma (mis. ZG digeser oleh 1σ realized). Keyakinan 30% [SPEKULASI].
> 

**4. Plausibilitas.** Zero Gamma: H-B1 85% (terdokumentasi sebagai crossing). VT: H-B2 55% > H-B3 35% (deskripsi "konsentrasi support" mendukung H-B2). Risk Pivot: spekulatif.

**5. Adaptasi GLBX.** Profil gamma butuh IV per strike (§F) + $s_i$ (§A). Grid $S$: ±5–8% dari spot, langkah 1 strike. Gunakan **semua ekspirasi** untuk ZG "struktural", dan filter **0DTE** untuk versi intraday.

**6. Validasi.** ZG kita vs angka SpotGamma harian SPX (proxy; /ES≈SPX scaled) toleransi ±0.3%. VT harus berada **di atas Put Wall & di bawah/at ZG** secara ordinal — uji urutan level, bukan hanya nilai.[[19]](https://support.spotgamma.com/hc/en-us/articles/15297954935699-Volatility-Trigger)

**7. Jebakan.** (i) Menyamakan VT=ZG (keliru: VT lebih tinggi, berbasis konsentrasi). (ii) Profil gamma tidak menggeser IV saat menggeser S (abaikan vanna → ZG meleset; sticky-strike vs sticky-delta). (iii) Pakai gamma unit alih-alih $-gamma. (iv) /ES vs SPX beda multiplier & jam (ETH 23 jam).

---

## C. Hedge Wall

**1. Definisi vendor.** "Hedge Wall punya dampak untuk saham individual seperti Volatility Trigger untuk index — titik di mana realized vol diperkirakan mulai naik… prediktif terhadap perilaku vol dengan signifikansi statistik".[[23]](https://support.spotgamma.com/hc/en-us/articles/15297582984723-Hedge-Wall) Di HIRO, "kalkulasi serupa dipakai untuk Hedge Wall".[[22]](https://support.bloomberg.spotgamma.com/hc/en-us/articles/20726435775379-Volatility-Trigger)

**2. Mekanika diakui.** Hedge Wall ≈ analog single-name dari VT; "di atasnya cenderung mean-reversion, di bawahnya momentum". Scanner SpotGamma punya "1% margin of Hedge Wall".[[24]](https://support.spotgamma.com/hc/en-us/articles/1500010833862-1-Margin-of-Hedge-Wall-SpotGamma-Scanner)

**3. Hipotesis.**

> **H-C1 (paling mungkin):** Hedge Wall = strike dengan gamma absolut/total terbesar yang berfungsi sebagai batas rezim hedging — secara operasional identik VT tapi tanpa pembobotan flow kompleks; $\text{HW}=\arg\max_K |\$\Gamma(K)|$ dekat spot. Beda dengan Call/Put Wall: HW soal **transisi rezim vol**, Wall soal **batas range**. Keyakinan 55%.
> 

> **H-C2:** HW = level di mana net $\$\Gamma$ kumulatif (dari atas) menyilang nol untuk single-name dengan asumsi dealer short call & short put (equity convention). Keyakinan 40%.
> 

> **H-C3:** HW dipilih untuk memaksimalkan signifikansi statistik prediksi RV (fit historis) — bukan rumus tunggal melainkan level ber-skor tertinggi. [SPEKULASI] 25%.
> 

**4. Plausibilitas.** H-C1 55% > H-C2 40% > H-C3 25%. Untuk /ES /NQ (index convention) HW≈VT, jadi prioritaskan H-C1 dengan konvensi index.

**5. Adaptasi GLBX.** Sama seperti VT (§B) tapi diterapkan pada single underlying; untuk /ES /NQ ini setara VT. Gunakan total gamma per strike dari rantai opsi-atas-futures.

**6. Validasi.** Bandingkan Hedge Wall (single-stock) vs angka Equity Hub; untuk index, uji bahwa HW≈VT. Uji prediktif: RV setelah harga < HW harus > RV di atas HW (uji signifikansi, sesuai klaim vendor).

**7. Jebakan.** (i) Mencampur konvensi tanda equity vs index. (ii) Memakai net gamma (bisa nol di banyak titik) alih-alih |gamma| → HW tak stabil. (iii) Mengabaikan margin 1% (vendor pakai zona, bukan garis).

---

## D. Call Wall / Put Wall / Absolute Gamma

**1. Definisi vendor.** *Call Wall* = "strike dengan **net call gamma** terbesar" (resistance).[[25]](https://support.spotgamma.com/hc/en-us/articles/15297391724179-Call-Wall-What-It-Is-and-How-SpotGamma-Uses-It) *Put Wall* = "strike dengan **net put gamma** terbesar" (support).[[26]](https://support.spotgamma.com/hc/en-us/articles/15297856056979-Put-Wall-What-It-Is-and-How-SpotGamma-Uses-It) *Absolute Gamma* = "strike dengan **total gamma** terbesar", sticky pin, sering dekat ZG.[[27]](https://support.spotgamma.com/hc/en-us/articles/15297255426195-Absolute-Gamma) *Key/Large Gamma Strike* = magnitudo gamma gabungan terbesar.[[28]](https://support.spotgamma.com/hc/en-us/articles/15297780226451-Key-Gamma-Strike)

**2. Mekanika diakui.** Wall = argmax gamma per strike, **bukan** sekadar argmax OI. GEX SpotGamma dalam $-notional berbasis harga kini.[[29]](https://support.spotgamma.com/hc/en-us/articles/33608294279955-What-is-GEX) Call Wall update intraday & bisa jadi magnet bila ditembus.[[30]](https://support.spotgamma.com/hc/en-us/articles/28242176025363-Founder-s-Note-Trading-Example-Basic-Call-Wall-as-Resistance)

**3. Hipotesis.**

> **H-D1 (paling mungkin): argmax gamma-$ dengan IV-weighting.**
> 

$$
\text{CallWall}=\arg\max_{K>S}\ \Gamma_c(K)\,OI_c(K)\,M\,F^2,\quad \text{PutWall}=\arg\max_{K<S}\ \Gamma_p(K)\,OI_p(K)\,M\,F^2
$$

Dinamis karena $\Gamma$ bergantung IV & spot (dynamic vol weighting). Keyakinan 70%.

> **H-D2: argmax net gamma per strike** (call − put gamma di strike itu) — menangkap "net call gamma". Keyakinan 45%.
> 

> **H-D3: argmax OI saja** (static, lensa OI) — model lama / tampilan alternatif. Keyakinan 25%.
> 

> **Absolute Gamma:** $\arg\max_K[\Gamma_c OI_c+\Gamma_p OI_p]\,M F^2$ (tanpa tanda dealer, total). Keyakinan 80%.
> 

**4. Plausibilitas.** H-D1 70% (vendor tekankan gamma & dynamic vol, eksplisit "largest net call gamma"). H-D2 45%. H-D3 25% (hanya lensa OI). Absolute Gamma 80%.

**5. Adaptasi GLBX.** Butuh $\Gamma$ per strike (IV §F) + OI dari `statistics`. Filter ekspirasi: vendor punya selektor (nearest/0DTE/aggregate)[[25]](https://support.spotgamma.com/hc/en-us/articles/15297391724179-Call-Wall-What-It-Is-and-How-SpotGamma-Uses-It) → reproduksi keduanya. Net vs absolute: sediakan toggle.

**6. Validasi.** Statistik publik SpotGamma: Call Wall ditembus hanya ~17% sesi; saat ditembus, 68% close di atasnya.[[31]](https://spotgamma.com/option-wall-stats/) Gunakan ini sebagai **uji distribusi** (bukan hanya level harian). Wall strike harus match persis vs Equity Hub SPX.

**7. Jebakan.** (i) Pakai gamma unit, bukan gamma-$ (besar OI di strike murah mendominasi keliru). (ii) Tak update IV intraday → wall "beku". (iii) Campur semua ekspirasi padahal 0DTE dominan. (iv) Net vs absolute tertukar (Wall=net, Absolute=total).

---

## E. Klasifikasi Customer / Dealer / Retail (untuk HIRO)

**1. Definisi vendor.** HIRO = "Hedging Impact of Real-time Options": "mengukur & mengagregasi **delta notional** dari setiap trade opsi, mengestimasi kebutuhan hedging tiap transaksi".[[32]](https://support.spotgamma.com/hc/en-us/articles/4420646443539-What-is-the-SpotGamma-HIRO-Indicator) Bukan "apa yang dibeli" tapi "apa yang harus dilakukan MM".[[33]](https://spotgamma.com/hiro-indicator/) Garis terpisah: 0DTE / Total / Calls / Puts / Retail.

**2. Mekanika diakui.** Untuk tiap trade, tentukan apakah customer beli/jual (→ MM ambil sisi lawan), kalikan delta notional, agregasi terus-menerus → kurva tekanan hedging real-time.[[34]](https://spotgamma.com/how-to-use-spotgamma-hiro-indicator/)

**3. Hipotesis.**

> **H-E1 Pemetaan agresor → impact (paling mungkin di GLBX).** customer buy-agresor call ⇒ MM short call ⇒ MM beli future (hedge +). Tanda impact:
> 

$$
\text{HIRO}_t=\sum_{\text{trades}} \underbrace{(+1\,\text{buy}/-1\,\text{sell})}_{\text{side}}\cdot \underbrace{(\text{call}+/\text{put}-)}_{\text{type}}\cdot \Delta_{\text{opt}}\cdot q\cdot M\cdot F
$$

```python
def hiro_increment(tr):
    cust = +1 if tr.side=='B' else -1      # customer aggressor direction
    typ  = +1 if tr.is_call else -1
    return cust*typ*opt_delta(tr)*tr.size*M*F   # dealer hedge delta-notional
```

Keyakinan 75%.

> **H-E2 Retail split via ukuran & odd-lot.** retail = trade kecil (≤ N kontrak), round strikes, eksekusi di ask (lifting). Garis Retail = subset signed-impact dengan size ≤ ambang. Ambang **perlu kalibrasi**. Keyakinan 50%.
> 

> **H-E3 BVC untuk trade `N`/mid.** Bila side=N, pakai standardized price change Easley: $V_{\text{buy}}=V\cdot Z\!\big(\tfrac{\Delta P}{\sigma_{\Delta P}}\big)$, $Z$=CDF (normal/Student-t).[[14]](https://tom.shohfi.com/don/pubs/01-Don-BVC.pdf) Keyakinan 45%.
> 

> **H-E4 0DTE line** = filter $T<1$ hari pada agregasi yang sama. Keyakinan 85%.
> 

**4. Plausibilitas.** H-E1 75% (delta-notional × sisi agresor = definisi langsung HIRO). H-E4 85%. H-E2 50% (proxy retail wajar tapi tak terkonfirmasi). H-E3 45%.

**5. Adaptasi GLBX.** `side` native → klasifikasi MM-impact tanpa Lee-Ready (keunggulan besar vs SpotGamma yang harus pakai feed OPRA + heuristik). **Asumsi terpaksa:** label customer/MM tak ada → kita asumsikan agresor = customer, pasif = MM (umumnya benar di opsi). Retail line murni heuristik ukuran (tak ada label retail di CME).

**6. Validasi.** Integral HIRO intraday harus berkorelasi dengan arah /ES. Bandingkan tanda & timing spike vs HIRO SPY publik (kualitatif, karena angka absolut beda). Uji: pada sesi positive-gamma, HIRO mean-revert; negative-gamma, HIRO trending.

**7. Jebakan.** (i) Salah tanda put (buy put customer ⇒ MM long put ⇒ MM jual future). (ii) Pakai delta unit, bukan delta-notional ×F×M. (iii) Trade `N` diabaikan → bias di opsi index yang banyak trade mid. (iv) Multi-leg (spread) dihitung sebagai dua agresif terpisah → double-count; rekonstruksi leg dari `definition`.

---

## F. Sumber & Konstruksi Implied Volatility

**1. Definisi vendor.** Databento sengaja **tidak** menyediakan IV/greeks (sensitif terhadap model/input), hanya tutorial Black-76.[[35]](https://databento.com/options)[[2]](https://databento.com/blog/option-greeks) CBOE VIX: variansi model-free dari strip OTM put+call dua ekspirasi, diinterpolasi ke 30 hari.[[36]](https://cdn.cboe.com/resources/indices/Cboe_Volatility_Index_Mathematics_Methodology.pdf)

**2. Mekanika diakui.** VIX: $\sigma^2=\frac{2}{T}\sum_i \frac{\Delta K_i}{K_i^2}e^{rT}Q(K_i)-\frac1T\big(\frac{F}{K_0}-1\big)^2$, $Q$=mid OTM.[[37]](https://www.cboe.com/micro/vix/vixwhite.pdf) Mid dari bid/ask (mbp-1/tbbo).

**3. Hipotesis.**

> **H-F1 IV per kontrak dari mid mbp-1 + Newton-Raphson (paling mungkin).** Mid = (bid+ask)/2 dari `mbp-1`/`tbbo` tepat sebelum/at waktu. Init NR: **Brenner-Subrahmanyam** $\sigma_0\approx\sqrt{2\pi/T}\cdot(\text{price}/F)$; vega-Newton dengan fallback Brent bila vega→0 (deep OTM/0DTE).
> 

```python
def iv(price,F,K,T,r,cp):
    s=sqrt(2*pi/T)*price/F                  # Brenner-Subrahmanyam seed
    for _ in range(50):
        d=black76_price(F,K,T,r,s,cp)-price
        v=black76_vega(F,K,T,r,s)
        if v<1e-8: return brent_iv(...)     # fallback
        s-=d/v
    return s
```

Keyakinan 80%.

> **H-F2 IV dari trade price** (untuk titik tereksekusi) — lebih bising, dipakai HIRO; gabung dengan H-F1. Keyakinan 50%.
> 

> **H-F3 Surface: SVI raw (Gatheral) per slice, no-arb.** Total varians $w(k)=a+b\{\rho(k-m)+\sqrt{(k-m)^2+\sigma^2}\}$, $k=\ln(K/F)$; kalibrasi arbitrage-free (Gatheral-Jacquier), cek butterfly $g(k)\ge0$ & calendar (w monoton di T).[[38]](https://arxiv.org/abs/1204.0646)[[39]](https://mfe.baruch.cuny.edu/wp-content/uploads/2013/01/OsakaSVI2012.pdf) Keyakinan 70% (SVI lebih lazim daripada SABR untuk index).
> 

> **H-F4 SABR** (β≈1 untuk futures) alternatif. Keyakinan 35%.
> 

> **H-F5 Expected move VIX-style** untuk /ES /NQ: bangun "VIX lokal" dari strip opsi front, expected move = $\sigma_{30d}\sqrt{T}\cdot F$; cek vs straddle ATM (~0.85×straddle).[[40]](https://www.barchart.com/stocks/quotes/%24SPX/gamma-exposure) Keyakinan 75%.
> 

**4. Plausibilitas.** H-F1 80% > H-F3 70% > H-F5 75% (semua kemungkinan dipakai bersama: per-contract IV → fit SVI → expected move). H-F2 50%, H-F4 35%.

**5. Adaptasi GLBX.** Mid dari `mbp-1` (top-of-book per strike) atau `tbbo`. **Asumsi terpaksa:** 0DTE deep-OTM vega→0 membuat IV tak stabil → clip & andalkan SVI smoothing. Forward $F$ langsung = harga future (tak perlu put-call parity sintetis seperti SPX). r dari SOFR.

**6. Validasi.** Re-price settlement (`statistics`) dengan IV settlement CME (jika ada di feed) → harus match. VIX-lokal kita vs VIX CBOE pada hari yang sama (proxy) ±0.5 vol point. SVI: tanpa butterfly/calendar arbitrage (uji $g(k)\ge0$).

**7. Jebakan.** (i) Pakai last-trade bukan mid → IV bias di spread lebar. (ii) NR diverging di deep-OTM (vega kecil) tanpa fallback. (iii) Day-count salah (pakai 365 sesuai brief, tapi 0DTE harus pakai **jam tersisa** bukan hari penuh — kritikal!). (iv) Lupa diskon $D$ di vega saat NR. (v) Forward salah expiry (front vs back month).

---

## G. Normalisasi Colormap Heatmap (TRACE)

**1. Definisi vendor.** TRACE: heatmap + strike plot menampilkan S/R & zona vol intraday.[[41]](https://support.spotgamma.com/hc/en-us/articles/33607907909011-What-is-SpotGamma-TRACE) Gamma Heatmap: **biru** = vol rendah (gamma MM +), **merah** = vol tinggi (gamma −), **putih/hitam** = transisi/netral.[[42]](https://support.spotgamma.com/hc/en-us/articles/33608037264787-What-is-the-Gamma-Heatmap) Ada Delta Pressure & Charm Pressure heatmap.[[43]](https://support.spotgamma.com/hc/en-us/articles/33608084842643-What-is-the-Delta-Pressure-Heatmap)[[44]](https://support.spotgamma.com/hc/en-us/articles/33608198289043-What-is-the-Charm-Pressure-Heatmap)

**2. Mekanika diakui.** Warna **signed & simetris di sekitar 0** (biru + / merah −), intensitas ∝ magnitudo. Sumbu: strike (y) × waktu (x), nilai = gamma/charm per sel.

**3. Hipotesis.**

> **H-G1 Signed-symmetric + percentile clipping (paling mungkin).** Normalisasi diverging di sekitar 0: $c=\text{clip}(x/Q_{p},-1,1)$ dengan $Q_p$=kuantil-p |x| (mis. p=95–99) per sesi/per nama, lalu map ke colormap diverging (RdBu). $p$ **perlu kalibrasi**. Keyakinan 70%.
> 

> **H-G2 Signed-log.** $c=\text{sign}(x)\log(1+|x|/x_0)$ untuk menangani heavy tail gamma. Keyakinan 50%.
> 

> **H-G3 Linear absolute scaling** (min-max simetris global). Keyakinan 30% (kurang robust antar-nama).
> 

```python
def colormap_value(x, ref):
    q = np.quantile(np.abs(ref), 0.97)        # per-session calibration
    return np.clip(x/ (q+1e-9), -1, 1)        # -> diverging RdBu, 0=white/black
```

**4. Plausibilitas.** H-G1 70% (percentile clip + diverging adalah standar de-facto heatmap finansial & cocok dengan "biru/merah/putih"). H-G2 50%. H-G3 30%.

**5. Adaptasi GLBX.** Hitung gamma/charm per (strike, waktu) dari rantai opsi-atas-futures; charm dari §0.1; agregasi tanda dealer §0.4. Sel waktu = bar (mis. 1 menit).

**6. Validasi.** Tak ada angka publik → validasi **kualitatif**: replikasi screenshot golden day (mis. 11 Sep 2024 yang dipakai SpotGamma)[[41]](https://support.spotgamma.com/hc/en-us/articles/33607907909011-What-is-SpotGamma-TRACE) — pola biru/merah & lokasi pita harus serupa. Kalibrasi $p$ sampai distribusi warna match.

**7. Jebakan.** (i) Normalisasi non-simetris → 0 tak di tengah colormap. (ii) Skala global antar-hari → hari tenang tampak "kosong". (iii) Tak clip outlier → satu strike 0DTE mendominasi seluruh peta.

---

## H. SG Acceleration Indicator / Composite View

**1. Definisi vendor.** Composite View: "seberapa cepat gamma berubah, diukur oleh **SG Acceleration Indicator** (y-axis); spike → ekspektasi vol lebih tinggi".[[45]](https://support.spotgamma.com/hc/en-us/articles/39946656110739-What-is-the-Synthetic-OI-Composite-View-Chart) Versi lama "SG Momentum Indicator"; hijau = call mengendalikan, merah = put.[[46]](https://support.spotgamma.com/hc/en-us/articles/14356919886227-What-is-the-Total-OI-Composite-View-chart)

**2. Mekanika diakui.** Mengukur **laju perubahan gamma** (turunan). "Recent Activity" line = seberapa cepat gamma berubah lintas strike, diwarnai by level aktivitas opsi.

**3. Hipotesis.**

> **H-H1 (paling mungkin): turunan waktu dari net gamma.** $\text{Accel}_t=\frac{d^2 \$\Gamma}{dt^2}$ atau lebih tepat laju perubahan profil gamma: $\text{Accel}_t=\lVert \$\Gamma_t(\cdot)-\$\Gamma_{t-1}(\cdot)\rVert$ (norma perubahan distribusi gamma per strike). Velocity/acceleration ala indikator V&A standar.[[47]](https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/V-Z/VelocityAndAcceleration) Keyakinan 60%.
> 

> **H-H2: |d(GEX)/dS| di spot** (seberapa tajam gamma berubah terhadap harga di level saat ini). Keyakinan 45%.
> 

> **H-H3: rate-of-change ter-smoothing (EMA velocity lalu EMA acceleration).** Keyakinan 40%.
> 

Warna hijau/merah: tanda dominasi call vs put gamma flow di sel.

**4. Plausibilitas.** H-H1 60% (vendor eksplisit "how fast gamma is changing"). H-H2 45%. H-H3 40% (smoothing wajar untuk display).

**5. Adaptasi GLBX.** Hitung profil $\$\Gamma$ per bar (§0.3), ambil selisih antar-bar (velocity) lalu selisih kedua (acceleration); warnai dengan rasio call-gamma vs put-gamma flow dari §E.

**6. Validasi.** Tak ada angka publik → validasi kualitatif: spike Acceleration harus mendahului ekspansi RV (klaim vendor). Uji korelasi $\text{Accel}_t$ vs RV$_{t+\delta}$.

**7. Jebakan.** (i) Tukar velocity vs acceleration. (ii) Noise 0DTE membuat turunan kedua meledak → wajib smoothing. (iii) Lupa pisahkan komponen call/put untuk pewarnaan.

---

## I. Charm Pressure & Vanna Pressure Models

**1. Definisi vendor.** SpotGamma: *Vanna* = Δ change per ΔIV; dealer index **long call/short put ⇒ long vanna**, IV turun ⇒ MM beli future.[[48]](https://spotgamma.com/options-vanna/)[[49]](https://spotgamma.com/options-vanna-charm/) *Charm* = Δ change per Δwaktu; OTM decay ⇒ dealer beli kembali future.[[50]](https://support.spotgamma.com/hc/en-us/articles/15246596430483-Charm) Charm Pressure (TRACE) = "bagaimana hedging MM berubah terhadap waktu, dipengaruhi besar oleh volume 0DTE; elemen kunci pinning dekat node gamma +".[[44]](https://support.spotgamma.com/hc/en-us/articles/33608198289043-What-is-the-Charm-Pressure-Heatmap)

**2. Mekanika diakui.** "Pressure" = laju hedging future yang dipaksa oleh charm/vanna per satuan waktu. Vanna Model SpotGamma menggeser IV bersama harga (kurva ungu vs kurva gamma abu) — "complex IV model".[[51]](https://support.spotgamma.com/hc/en-us/articles/15350867797267-What-is-the-SpotGamma-Vanna-Model)

**3. Hipotesis.**

> **H-I1 Exposure-style (paling mungkin).** Per strike, eksposur dealer:
> 

$$
\text{CEX}(K)=s\,\text{Charm}(K)\,OI(K)\,M\,F,\qquad \text{VEX}(K)=s\,\text{Vanna}(K)\,OI(K)\,M\,F\,\cdot(\partial\sigma)
$$

Vanna Pressure per menit = $\Delta\text{hedge}=\text{VEX}\cdot \Delta\sigma_{\text{per min}}$; Charm Pressure per menit = $\text{CEX}\cdot \Delta t_{\text{per min}}$.[[9]](https://medium.com/option-screener/so-youve-heard-about-gamma-exposure-gex-but-what-about-vanna-and-charm-exposures-47ed9109d26a) Keyakinan 75%.

```python
CEX = sign*charm(K)*OI*M*F            # delta drift per unit time
VEX = sign*vanna(K)*OI*M*F            # delta drift per unit IV
charm_pressure_per_min = CEX * (1/ (minutes_to_expiry))   # time decay rate
vanna_pressure_per_min = VEX * d_sigma_per_min            # IV path
```

> **H-I2 Path-dependent (vanna ×skew).** Pakai SpotGamma-style: geser IV sepanjang skew saat harga bergerak (vanna efektif memakai $\partial\sigma/\partial S$ dari surface SVI). Keyakinan 55%.
> 

> **H-I3 Charm pinning kernel.** Bobot charm hanya dekat node gamma + (pinning) — agregasi tertimbang jarak ke gamma positif. Keyakinan 40%.
> 

**4. Plausibilitas.** H-I1 75% (paralel langsung dengan GEX). H-I2 55% (vendor klaim "complex IV model" → menggeser IV sepanjang skew). H-I3 40%.

**5. Adaptasi GLBX.** Charm/vanna unit dari §0.1 (finite-diff aman untuk 0DTE), $s$ dari §0.4, OI dari `statistics`, $\Delta\sigma_{\text{per min}}$ dari path IV intraday (§F). **Asumsi terpaksa:** charm 0DTE meledak mendekati ekspirasi → clip & pakai jam-tersisa, bukan 1/365.

**6. Validasi.** Vanna Pressure harus menjelaskan "vol-reset rally" (IV turun sore ⇒ beli future).[[52]](https://spotgamma.com/vanna-and-charm-explained/) Charm Pressure harus memuncak menuju 15:00–16:00 ET pada 0DTE (pinning). Bandingkan tanda & timing dengan narasi Founder's Note (kualitatif).

**7. Jebakan.** (i) Charm pakai 1/365 alih-alih jam riil 0DTE → magnitudo salah total. (ii) Tanda vanna put keliru. (iii) Vanna tanpa menggeser skew (sticky-strike) meremehkan efek. (iv) Double-count vega vs vanna.

---

## Tabel ringkas: kandidat algoritma × plausibilitas × kebutuhan data GLBX

| Metrik | Kandidat utama | Keyakinan | Data GLBX |
| --- | --- | --- | --- |
| A. Synthetic OI/DDOI | Signed-vol + rekonsiliasi ΔOI (H-A1) | 70% | trades.side, statistics(OI), definition |
| B. Zero Gamma | Zero-crossing profil $Γ(S) (H-B1) | 85% | IV(mbp-1), OI, sign(DDOI) |
| B. Vol Trigger | Strike gamma+ major terendah (H-B2) | 55% |   • ambang τ kalibrasi |
| C. Hedge Wall | argmax|$Γ| dekat spot, index conv (H-C1) | 55% | IV, OI |
| D. Call/Put Wall | argmax gamma-$ IV-weighted (H-D1) | 70% | IV, OI per call/put |
| D. Absolute Gamma | argmax total gamma-$ (H-D) | 80% | IV, OI |
| E. HIRO/klasifikasi | side→delta-notional impact (H-E1) | 75% | trades.side, delta(IV) |
| F. IV | mid mbp-1 + NR + SVI no-arb (H-F1/F3) | 80/70% | mbp-1/tbbo, SOFR |
| G. Heatmap norm | Signed-symmetric + percentile clip (H-G1) | 70% | gamma/charm per bar |
| H. SG Acceleration | Laju perubahan profil gamma (H-H1) | 60% | $Γ per bar |
| I. Charm/Vanna Pressure | CEX/VEX × Δt/Δσ per menit (H-I1) | 75% | charm/vanna, OI, path IV |

---

## Triangulasi 3 vendor (metode yang konvergen)

| Konsep | SpotGamma | SqueezeMetrics | MenthorQ / UW |
| --- | --- | --- | --- |
| GEX dasar | $-notional per 1% (coined GEX) | Γ·OI·100·k, ±put, didolarkan | net GEX per strike, blind spots |
| Posisi dealer | index: short put/long call; equity: short keduanya | long call/short put (call overwriting + protective put) | OI-based, gamma + & − |
| Inferensi arah | Synthetic OI (multi-feed) | DDOI: sisi trade + verifikasi ΔOI | OI positioning (tanpa flow eksplisit) |
| Level kunci | Call/Put Wall, VT, ZG, Abs Gamma, Hedge Wall | GEX profile, zero-cross | Gamma levels, Blind Spots, HVL/LVL |

Konvergensi: ketiganya setuju **(a)** gamma + ⇒ vol ditekan, gamma − ⇒ vol diperbesar; **(b)** wall = argmax gamma per strike; **(c)** arah hedging dari posisi dealer yang diinferensi. Divergensi utama: SpotGamma & SqueezeMetrics melakukan inferensi flow (DDOI), MenthorQ lebih murni OI-positioning.[[53]](https://menthorq.com/guide/key-gamma-levels/)[[6]](https://squeezemetrics.com/monitor/download/pdf/white_paper.pdf)[[8]](https://support.spotgamma.com/hc/en-us/articles/15214161607827-GEX-Gamma-Exposure-Explained-What-It-Is-and-How-SpotGamma-Uses-It)

---

## Peta Kalibrasi (parameter yang harus dikalibrasi empiris dari golden days)

| Parameter | Bagian | Status | Prosedur kalibrasi |
| --- | --- | --- | --- |
| p_open(size, OTM, time-of-day) — bobot open/close | A | tidak diketahui | Regresi logistik signed-vol vs ΔOI aktual T+1; maksimalkan match Σdealer pos |
| frac_close (porsi closing saat ΔOI<0) | A | tidak diketahui | Grid-search agar rekonstruksi OI = OI resmi |
| τ (ambang "major" gamma untuk VT) | B | tidak diketahui | Minimkan error VT kita vs VT SpotGamma di N golden days; cari τ∈[0.3,0.6] |
| Retail size threshold | E | tidak diketahui | Sweep ambang; cocokkan profil garis Retail HIRO publik (kualitatif) |
| BVC σ_ΔP & distribusi (normal/t, df) | A/E | tidak diketahui | MLE pada bar; bandingkan akurasi vs sisi agresor native |
| SVI (a,b,ρ,m,σ) per slice | F | fit harian | Least-squares vega-weighted + constraint no-arb (g(k)≥0, calendar) |
| Percentile clip p (heatmap) | G | tidak diketahui | Sesuaikan p∈[95,99] agar distribusi warna match screenshot golden day |
| Smoothing EMA (velocity/accel) | H | tidak diketahui | Pilih span agar spike mendahului RV; maksimalkan korelasi Accel→RV |
| Δσ_per_min (path IV) | I | data-driven | Estimasi dari mid IV intraday; smoothing Kalman |
| Day-count 0DTE (jam riil vs 1/365) | F/I | kritikal | Pakai jam-ke-settlement aktual (15:00/16:00 ET); kalibrasi vs harga settlement |

**Golden-day protocol:** pilih 5–10 hari (campuran tenang & event: mis. OPEX, CPI, FOMC, hari tenang mid-week). Untuk tiap hari: (1) bangun semua metrik; (2) bandingkan level (wall, VT, ZG, flip) vs angka SpotGamma SPX sebagai proxy (toleransi: wall strike **persis**, VT/ZG **±0.3%**); (3) sesuaikan parameter; (4) bekukan; (5) out-of-sample test pada hari lain. Catatan: /ES≈SPX tetapi beda multiplier, jam ETH, dan basis future—jangan harap match absolut, fokus pada **arah, ordinal level, dan timing**.

---

## Catatan keterbatasan & asumsi terpaksa (ringkasan)

- **Tidak ada label open/close** → semua DDOI bergantung rekonsiliasi ΔOI (T+1, pakai final Daily Bulletin).[[16]](https://www.cmegroup.com/market-data/volume-open-interest.html)
- **Tidak ada label customer/MM** → asumsi agresor=customer, pasif=MM.
- **Tidak ada Cboe Open-Close** → garis Retail murni heuristik ukuran.
- **Keunggulan:** sisi agresor native (`side`), single-venue (tanpa konsolidasi OPRA), OI & settlement resmi CME via `statistics`.[[4]](https://databento.com/docs/schemas-and-data-formats/trades)
- Semua angka parameter proprietary vendor **tidak dipublikasikan** → wajib kalibrasi empiris (tabel di atas).

<aside>
🔧

Langkah implementasi Python yang disarankan: (1) loader `definition`+`statistics`+`trades`/`mbp-1`; (2) modul Black-76 (IV NR + greeks autodiff); (3) mesin DDOI (§0.4); (4) builder profil gamma/vanna/charm; (5) ekstraktor level (ZG/VT/Wall/AbsGamma); (6) HIRO streamer; (7) heatmap renderer; (8) harness kalibrasi golden-day. Tiap modul memetakan 1:1 ke bagian A–I.

</aside>