<aside>
🧭

**Tujuan dokumen:** membongkar metodologi, matematika, klasifikasi trade, dan encoding visual indikator **SpotGamma HIRO** (Hedging Impact of Real-time Options) sampai level yang cukup untuk **replikasi dari nol**, plus pembanding (Unusual Whales, Cheddar Flow, GEXBOT, MenthorQ) dan **bab khusus adaptasi untuk terminal /ES & /NQ (options-on-futures CME, data Databento GLBX.MDP3, model Black-76)**.

Ini dokumen pendamping riset TRACE sebelumnya (SpotGamma TRACE — Riset Mendalam Replikasi Heatmap Gamma (vs OptionsDepth, GEXBOT, MenthorQ)). HIRO = **FLOW** real-time; TRACE/GEX = **STOK** posisi.

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

HIRO mengukur **dampak hedging (delta-notional) dari setiap trade opsi secara real-time**: ia mengklasifikasi tiap transaksi (customer buy/sell, call/put), mengubahnya menjadi **delta-notional bertanda** dari sisi *yang harus di-hedge dealer*, lalu **mengakumulasi** menjadi garis intraday.[[1]](https://support.spotgamma.com/hc/en-us/articles/4420646443539-What-is-the-SpotGamma-HIRO-Indicator)[[2]](https://spotgamma.com/hiro-indicator/) **[FAKTA]**

$$
HIRO_t = \sum_{\text{trades} \le t} \big( \delta_i \times q_i \times \text{mult} \times S \times \text{customerSide}_i \times \text{dealerSign}(\text{C/P}) \big)
$$

Garis **naik = net beli call / jual put** (tekanan hedging ke atas); **turun = jual call / beli put** (tekanan ke bawah).[[3]](https://spotgamma.com/how-to-use-spotgamma-hiro-indicator/)[[4]](https://support.spotgamma.com/hc/en-us/articles/4421122374419-What-does-the-sliding-scale-in-the-HIRO-Signal-column-indicate) **[FAKTA]**

Yang **proprietary**: (a) klasifikasi trade & filter trade "hedged", (b) bobot dampak per trade (contextualizing block trades), (c) normalisasi "HIRO Signal" lintas instrumen, (d) impact-threshold Flow Alert.[[5]](https://spotgamma.com/hiro-updated-algo-logic-new-features/)[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf)

**Untuk /ES /NQ (poin terpenting):** `bbo-1m` **TIDAK cukup** — HIRO butuh data **per-trade dengan sisi agresor**. Di Databento GLBX.MDP3 pakai schema **`trades`** atau **`tbbo`** (punya field `side` = aggressor A/B), bukan snapshot interval `bbo-1m`. Delta pakai **Black-76** (opsi atas futures).[[7]](https://databento.com/docs/schemas-and-data-formats/trades)[[8]](https://databento.com/docs/schemas-and-data-formats/bbo)[[9]](https://databento.com/blog/option-greeks) **[FAKTA]**

---

# A. KONSEP

## A1. Apa yang sebenarnya diukur HIRO? Definisi "hedging impact"; flow vs stok

**Definisi resmi:** HIRO "**measures and aggregates the delta notional value from every option trade, estimating the hedging requirement associated with each transaction**" — menunjukkan bagaimana flow opsi memengaruhi arah & magnitudo gerak harga.[[1]](https://support.spotgamma.com/hc/en-us/articles/4420646443539-What-is-the-SpotGamma-HIRO-Indicator) **[FAKTA]**

**"Hedging impact" persisnya:** ketika customer melakukan trade opsi, dealer/market maker mengambil sisi seberang. Untuk tetap *delta-neutral*, dealer harus membeli/menjual underlying. HIRO mengestimasi **berapa besar (dalam $ delta-notional) dan ke arah mana** dealer dipaksa hedging.[[10]](https://spotgamma.com/trading-stocks-with-spotgamma-and-bookmap-hiro/) **[FAKTA]** Kutipan resmi: "if traders buy calls and sell puts… market makers take the opposite side… selling calls and buying puts. Since market makers want to remain delta neutral, **they buy stock to hedge their delta risk**."[[10]](https://spotgamma.com/trading-stocks-with-spotgamma-and-bookmap-hiro/) **[FAKTA]**

**Beda inti FLOW (HIRO) vs STOK (GEX/TRACE):**

| Aspek | HIRO (FLOW) | GEX / TRACE (STOK) |
| --- | --- | --- |
| Objek ukur | Δ posisi dari **trade live** (turunan waktu) | Posisi terakumulasi (Open Interest) — level |
| Greek inti | Delta-notional per trade | Gamma/Delta dari OI |
| Dimensi | 1-D garis kumulatif vs waktu | Profil per strike / medan (waktu×harga) |
| Pertanyaan dijawab | "Apa yang dealer beli/jual SEKARANG?" | "Di harga mana dealer akan stabil/volatil?" |
| Sifat sinyal | Leading / real-time | Struktural / lagging (OI semalam) |

Kutipan resmi yang menegaskan beda ini: "Options flow tools show you what trades are being placed. **HIRO takes the next step — it estimates the hedging impact** of those trades… It's not 'what was bought/sold,' it's '**what will market makers be forced to do** because of it.'"[[2]](https://spotgamma.com/hiro-indicator/) **[FAKTA]**

> Sumber: SpotGamma HIRO support, HIRO indicator page, Bookmap HIRO article.
> 

## A2. Kenapa HIRO leading/real-time? Apa yang dilihat trader?

**Leading karena:** ia menangkap **flow yang akan MEMICU hedging**, bukan hasil hedging yang sudah terjadi. SpotGamma: HIRO monitors "**every single options trade**… in real-time" dan menerjemahkan jutaan trade jadi sinyal dampak.[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf)[[11]](https://support.bloomberg.spotgamma.com/hc/en-us/articles/18660578974739-What-is-the-SpotGamma-HIRO-Indicator) **[FAKTA]** Contoh resmi: pada 2/24/25 garis HIRO (ungu) surge bareng S&P; jam 12:30 HIRO berbalik turun, S&P pun stall — "options flow killed the rally".[[2]](https://spotgamma.com/hiro-indicator/) **[FAKTA]**

**Yang dibaca trader (3 pola terdokumentasi):**

1. **Akumulasi/kemiringan garis** — slope naik = tekanan beli kumulatif; slope turun = tekanan jual.[[3]](https://spotgamma.com/how-to-use-spotgamma-hiro-indicator/) **[FAKTA]**
2. **Spike (Flow Alert)** — trade besar yang melewati "impact threshold" → notifikasi.[[12]](https://support.spotgamma.com/hc/en-us/articles/47871269691667-What-are-HIRO-Flow-Alerts) **[FAKTA]**
3. **Divergence HIRO vs harga** — harga naik tapi HIRO turun ⇒ potensi reversal (lihat C10).[[10]](https://spotgamma.com/trading-stocks-with-spotgamma-and-bookmap-hiro/) **[FAKTA]**

Perilaku khas di **Call Wall/Put Wall**: jika garis HIRO **mendatar (flatten)** dekat Call Wall → kemungkinan top; flatten dekat Put Wall → kemungkinan bottom/reversal tajam.[[13]](https://support.spotgamma.com/hc/en-us/articles/15169160339475-How-can-I-use-the-SpotGamma-HIRO-to-help-me-trade) **[FAKTA]**

> Sumber: HIRO FAQ, HIRO indicator page, Flow Alerts support, Bookmap HIRO, how-to-use HIRO support.
> 

---

# B. MATEMATIKA & DATA

## B3. Apa yang dihitung HIRO per trade? Rumus delta-notional

**Konfirmasi: YA — HIRO = delta-notional bertanda per trade yang diklasifikasi, lalu diakumulasi.**[[1]](https://support.spotgamma.com/hc/en-us/articles/4420646443539-What-is-the-SpotGamma-HIRO-Indicator) **[FAKTA: "delta notional value from every option trade… aggregates"]**

### Rumus per trade (rekonstruksi)

$$
hf_i = \delta_i \times q_i \times m \times S \times \sigma^{cust}_i \times d(\text{type}_i)
$$

| Simbol | Arti | Status |
| --- | --- | --- |
| `δ_i` | Delta opsi (BS/Black-76) saat trade | [FAKTA delta-notional] / model [INFERENSI] |
| `q_i` | Jumlah kontrak yang trade | [FAKTA size matters] |
| `m` = 100 | Multiplier kontrak (opsi ekuitas/indeks AS) | [FAKTA standar] |
| `S` | Harga underlying → ubah delta-share jadi $ notional | [INFERENSI: "notional"] |
| `σ_cust` | +1 customer BUY, −1 customer SELL | [FAKTA arah] / klasifikasi [PROPRIETARY] |
| `d(type)` | Tanda dealer-hedge per call/put (lihat B5) | [INFERENSI dari mekanik MM] |

### Akumulasi → garis HIRO

$$
HIRO_t = \sum_{t_i \le t} hf_i \quad (\text{cumulative rolling sum harian})
$$

SpotGamma menyebut versi lama = "**cumulative rolling sum for the whole day**"; versi baru menambahkan **rolling window** (mis. bar 5 menit) supaya flow aktif lebih terlihat.[[5]](https://spotgamma.com/hiro-updated-algo-logic-new-features/) **[FAKTA]**

**Catatan penting tentang tanda:** Output garis **ungu (Total)** didefinisikan dari sisi *dampak hedging ke harga*: **positif (naik) = customer beli call dan/atau jual put**; **negatif (turun) = customer jual call dan/atau beli put**.[[3]](https://spotgamma.com/how-to-use-spotgamma-hiro-indicator/)[[4]](https://support.spotgamma.com/hc/en-us/articles/4421122374419-What-does-the-sliding-scale-in-the-HIRO-Signal-column-indicate) **[FAKTA]** Artinya tanda sudah dipetakan ke **arah tekanan beli/jual underlying oleh dealer**, bukan sekadar delta opsi mentah.

> Catatan: faktor `S` dan apakah dipakai **delta-dollar** (δ×S×m×q) atau **delta-shares** (δ×m×q) tidak dirinci angka oleh vendor → **[INFERENSI]**. "Delta notional" kuat mengarah ke delta-dollar.
> 

> Sumber: HIRO support definisi, FAQ garis, sliding-scale support, algo-logic update.
> 

## B4. Bagaimana tiap trade diklasifikasi (customer buy/sell, call/put)?

**Yang terdokumentasi:** Flow Data HIRO berasal dari **Tape** (order flow tool SpotGamma) dan mencatat **"whether the order was bought or sold"**, strike, expiry, size/premium.[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf) **[FAKTA]** Konviksi diukur dari posisi eksekusi vs spread: "**Options purchased above the ask or sold below the bid**… may indicate more certainty".[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf) **[FAKTA — ini menyiratkan klasifikasi berbasis bid/ask]**

**Metode klasifikasi (reverse-engineering standar industri):**

- **Quote-based (Lee-Ready / kuota rule):** bandingkan harga eksekusi vs **mid**; di atas mid/ask → buy-initiated (customer buy), di bawah mid/bid → sell-initiated.[[14]](https://unusualwhales.com/information/how-to-interpret-types-of-option-transactions) **[INFERENSI — Unusual Whales eksplisit pakai "side along bid-ask spread"]**
- **Tick rule** sebagai fallback bila quote tidak ada. **[INFERENSI]**

**Mana yang proprietary:**

- **Algoritma klasifikasi persis SpotGamma = [PROPRIETARY]** ("proprietary SpotGamma algorithm").[[1]](https://support.spotgamma.com/hc/en-us/articles/4420646443539-What-is-the-SpotGamma-HIRO-Indicator)
- **Filter trade "hedged":** view *All Trades* "**uses SpotGamma proprietary logic to filter out some trades that we consider hedged** and therefore do not drive the underlying".[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf) **[PROPRIETARY]**
- **Deteksi retail:** "some proprietary logic to identify… which trades are likely retail-driven".[[3]](https://spotgamma.com/how-to-use-spotgamma-hiro-indicator/) **[PROPRIETARY]**
- **Kontekstualisasi block trade:** algo baru "better contextualize those big trades" agar tak jadi spike palsu.[[5]](https://spotgamma.com/hiro-updated-algo-logic-new-features/) **[PROPRIETARY]**

> Sumber: HIRO User Guide (Tape, above ask/below bid), HIRO support (proprietary algo), FAQ (retail logic), algo-logic update, Unusual Whales side definition.
> 

## B5. Arah hedging dealer dari sisi customer + konvensi tanda call/put

**Prinsip: dealer = lawan customer, lalu hedge ke delta-neutral.**[[10]](https://spotgamma.com/trading-stocks-with-spotgamma-and-bookmap-hiro/) **[FAKTA]** Tabel tanda (arah hedging underlying oleh dealer):

| Aksi customer | Posisi dealer | Delta dealer | Hedge underlying | Tanda HIRO |
| --- | --- | --- | --- | --- |
| BUY CALL | short call | negatif | **BELI** underlying |   • (naik) |
| SELL CALL | long call | positif | **JUAL** underlying | − (turun) |
| BUY PUT | short put | positif | **JUAL** underlying | − (turun) |
| SELL PUT | long put | negatif | **BELI** underlying |   • (naik) |

Ini konsisten dengan definisi resmi: positif = beli call/jual put; negatif = jual call/beli put.[[3]](https://spotgamma.com/how-to-use-spotgamma-hiro-indicator/)[[4]](https://support.spotgamma.com/hc/en-us/articles/4421122374419-What-does-the-sliding-scale-in-the-HIRO-Signal-column-indicate) **[FAKTA arah; tabel mekanik = INFERENSI standar]**

**Kunci implementasi:** delta call (>0) dan delta put (<0). Hedging dealer = `−(delta_posisi_dealer)`. Karena dealer = −customer, maka **tekanan hedging underlying = `−δ_opsi × σ_cust`** dikali notional. Untuk **buy call**: `−(+δ)×(+1) = −δ`?? — agar tanda akhir benar (BUY CALL = +), gunakan konvensi: **HIRO impact = `−1 × δ_dealer_posisi` di mana δ_dealer_posisi = −σ_cust × δ_opsi`**. Hasil akhir: BUY CALL → +, BUY PUT → −, dst (sesuai tabel). **[INFERENSI — verifikasi tanda saat coding]**

> Sumber: Bookmap HIRO (mekanik MM), HIRO FAQ & sliding-scale (arah tanda resmi).
> 

## B6. Delta saja atau gamma/charm? Model greek, IV, recompute?

- **Greek inti = DELTA** ("delta notional", "delta-hedging impact").[[1]](https://support.spotgamma.com/hc/en-us/articles/4420646443539-What-is-the-SpotGamma-HIRO-Indicator)[[2]](https://spotgamma.com/hiro-indicator/) **[FAKTA]** Tidak ada klaim resmi bobot gamma/charm di HIRO. Bobot gamma/charm = **[TIDAK TERDOKUMENTASI untuk HIRO]** (itu domain TRACE).
- **Model greek:** **[TIDAK TERDOKUMENTASI eksplisit].** Untuk SPX/saham AS, **Black-Scholes-Merton** adalah default natural. **[INFERENSI]**
- **Sumber IV:** **[TIDAK TERDOKUMENTASI].** Standar: solve IV per kontrak dari **mid bid/ask** (Newton-Raphson). Konsistensi dengan klasifikasi above-ask/below-bid menyiratkan SpotGamma punya quote real-time. **[INFERENSI]**
- **Recompute intraday:** karena "real-time" & per-trade, delta dihitung pada kondisi saat trade (S, T, σ saat itu). **[INFERENSI kuat]**

> Sumber: HIRO support & indicator page (delta notional); sisanya inferensi standar quant.
> 

## B7. Resolusi & agregasi: per trade? reset harian?

- **Granularitas dasar = per trade** ("every single options trade").[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf) **[FAKTA]**
- **Agregasi tampilan:** candle HIRO bisa **5 detik s/d 30 menit**; harga & sinyal punya durasi candle yang bisa diatur.[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf) **[FAKTA]**
- **Rolling window** mengubah dari **kumulatif penuh hari** ke jendela pendek (mis. 5 menit) untuk melihat flow aktif.[[5]](https://spotgamma.com/hiro-updated-algo-logic-new-features/)[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf) **[FAKTA]**
- **Reset harian:** "cumulative rolling sum **for the whole day**" ⇒ akumulasi di-reset tiap sesi. [[5]](https://spotgamma.com/hiro-updated-algo-logic-new-features/) **[FAKTA (implisit "whole day")]**

> Sumber: algo-logic update (whole day, 5-min), User Guide (candle 5s–30m, rolling window).
> 

## B8. Breakdown: index, ticker, call vs put, total

Garis-garis resmi di chart HIRO:[[3]](https://spotgamma.com/how-to-use-spotgamma-hiro-indicator/)[[15]](https://support.spotgamma.com/hc/en-us/articles/12284010265363-What-does-the-Put-Call-HIRO-Stock-Chart-indicate) **[FAKTA]**

| Garis | Warna | Arti |
| --- | --- | --- |
| Price | Putih (atau candle merah/hijau) | Harga underlying real-time |
| Total Aggregate HIRO | Ungu | Net hedging (call+put digabung) |
| Puts Only | Biru tua |   • = jual put, − = beli put |
| Calls Only | Oranye |   • = beli call, − = jual call |
| Next Expiry (0DTE) | Hijau | Flow hanya ekspirasi terdekat |
| Retail Only | Merah | Flow non-institusional (logika proprietary) |
- **Per ticker/index:** HIRO meng-cover **400+ ticker AS** + indeks utama (SPX, SPY, QQQ, IWM) & saham aktif (AAPL, NVDA, TSLA…).[[2]](https://spotgamma.com/hiro-indicator/)[[1]](https://support.spotgamma.com/hc/en-us/articles/4420646443539-What-is-the-SpotGamma-HIRO-Indicator) **[FAKTA]**
- **HIRO Signal (gauge):** nilai ter-standardisasi lintas underlying ("proprietary signal similar to delta notional, **standardized across underlyings**") + range 5-hari/30-hari.[[3]](https://spotgamma.com/how-to-use-spotgamma-hiro-indicator/)[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf) **[FAKTA]**

> Sumber: HIRO FAQ (garis & warna), Put/Call HIRO support, HIRO indicator page, User Guide.
> 

---

# C. ENCODING VISUAL

## C9. Bagaimana HIRO digambar?

- **Garis/candle kumulatif** dioverlay pada **chart harga**, dengan **sumbu-Y ganda**: HIRO di **y-axis terluar**, harga di **y-axis terdalam**.[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf) **[FAKTA]**
- Default: HIRO = **candle biru**; harga = candle merah/hijau.[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf) **[FAKTA]** (Versi web lama: garis ungu HIRO + garis putih harga.[[2]](https://spotgamma.com/hiro-indicator/))
- **Warna call/put:** Calls = **oranye**, Puts = **biru tua**.[[15]](https://support.spotgamma.com/hc/en-us/articles/12284010265363-What-does-the-Put-Call-HIRO-Stock-Chart-indicate) **[FAKTA]**
- Skala HIRO sering dalam **$ order flow** (mis. "$5 BILLION" di y-axis kanan).[[2]](https://spotgamma.com/hiro-indicator/) **[FAKTA]**
- Candle duration 5 detik–30 menit; price line bisa candle/line; bisa multi-ticker compare.[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf) **[FAKTA]**

> Replikasi: dual-axis time-series; x=waktu, y_kiri=harga, y_kanan=HIRO $; layer harga di atas, HIRO sebagai line/area. Overlay key levels (Call/Put Wall, Hedge Wall) sebagai garis horizontal.[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf)
> 

> Sumber: HIRO User Guide (sumbu ganda, candle), Put/Call support, HIRO page.
> 

## C10. Membaca divergence HIRO vs harga (contoh terdokumentasi)

Contoh resmi **AMD, 17 Mar 2022:** harga naik ke 114 **tetapi** Total Aggregate HIRO bergerak **turun**; tampak jelas saat dipisah put/call bahwa trader dominan **jual call** saat harga naik. Divergence ini = sinyal **potensi reversal / short setup**.[[10]](https://spotgamma.com/trading-stocks-with-spotgamma-and-bookmap-hiro/) **[FAKTA]**

Contoh **SPX 2/24/25:** HIRO surge bareng harga lalu berbalik jam 12:30 → rally stall (konfirmasi + lalu exhaustion).[[2]](https://spotgamma.com/hiro-indicator/) **[FAKTA]**

**Pola baca terdokumentasi:**

- **Konfirmasi:** HIRO & harga searah → tren didukung flow.[[16]](https://spotgamma.com/trading-stock-using-equity-hub-hiro/) **[FAKTA]**
- **Divergence:** arah berlawanan → reversal.[[10]](https://spotgamma.com/trading-stocks-with-spotgamma-and-bookmap-hiro/) **[FAKTA]**
- **Flatten di wall:** HIRO mendatar dekat Call/Put Wall → top/bottom.[[13]](https://support.spotgamma.com/hc/en-us/articles/15169160339475-How-can-I-use-the-SpotGamma-HIRO-to-help-me-trade) **[FAKTA]**

> Sumber: Bookmap HIRO (AMD divergence), HIRO page (SPX), Equity Hub HIRO, how-to-use HIRO.
> 

---

# D. REPLIKASI

## DATA CONTRACT (input final)

```python
# === INPUT: TRADE TAPE (per-trade, WAJIB ada sisi agresor) ===
OptionTrade = {
    "ts": datetime,            # timestamp eksekusi (ns)
    "underlying": str,         # SPX / SPY / ES / NQ ...
    "expiry": date,
    "strike": float,
    "type": "C" | "P",
    "price": float,            # harga eksekusi opsi
    "size": int,               # jumlah kontrak (q)
    "side": "BUY" | "SELL" | None,  # sisi AGRESOR (dari feed) -> customer buy/sell
    "bid": float, "ask": float,     # quote tepat sebelum trade (untuk klasifikasi/IV)
}

# === MARKET STATE (untuk delta) ===
State = {
    "spot": float,             # S (underlying / future price)
    "r": float,                # risk-free (SOFR/OIS) [INFERENSI]
    "q": float,                # dividend yield (BSM index) / 0 utk Black-76
    "iv": float | None,        # IV kontrak; else solve dari mid
}

# === OUTPUT: SERI HIRO ===
HiroSeries = {
    "t": List[datetime],
    "total": List[float],      # ungu  (cumulative signed delta-notional)
    "calls": List[float],      # oranye
    "puts":  List[float],      # biru
    "next_expiry": List[float],# hijau (0DTE)
    "price": List[float],      # overlay
}
```

## ALGORITMA (langkah + pseudo-code end-to-end)

1. **Stream trade** per kontrak (butuh sisi agresor).
2. **Klasifikasi sisi**: jika feed kasih aggressor (CME) pakai langsung; jika tidak (OPRA) pakai quote-rule (eksekusi vs mid).
3. **Hitung delta** kontrak (BS/Black-76) pada S,T,σ saat trade.
4. **Delta-notional bertanda**: petakan ke arah hedging dealer (tabel B5).
5. **Akumulasi** ke garis kumulatif harian (+ rolling window opsional).
6. **Render** dual-axis: harga + HIRO (total/call/put/0DTE) + key levels.

```python
from scipy.stats import norm
import numpy as np

def bs_delta(S, K, T, sigma, r, q, is_call):
    if T <= 0 or sigma <= 0: return 1.0 if (is_call and S>K) else (-1.0 if (not is_call and S<K) else 0.0)
    d1 = (np.log(S/K) + (r - q + 0.5*sigma**2)*T)/(sigma*np.sqrt(T))
    return np.exp(-q*T)*norm.cdf(d1) if is_call else np.exp(-q*T)*(norm.cdf(d1)-1)

def black76_delta(F, K, T, sigma, r, is_call):   # opsi atas FUTURES (/ES /NQ)
    if T <= 0 or sigma <= 0: return 1.0 if (is_call and F>K) else (-1.0 if (not is_call and F<K) else 0.0)
    d1 = (np.log(F/K) + 0.5*sigma**2*T)/(sigma*np.sqrt(T))
    return np.exp(-r*T)*norm.cdf(d1) if is_call else -np.exp(-r*T)*norm.cdf(-d1)

def classify_side(trade):
    if trade.side in ("BUY","SELL"):      # CME: aggressor langsung
        return +1 if trade.side=="BUY" else -1
    mid = 0.5*(trade.bid + trade.ask)     # OPRA: quote-rule (Lee-Ready)
    if trade.price >= trade.ask: return +1
    if trade.price <= trade.bid: return -1
    return +1 if trade.price > mid else (-1 if trade.price < mid else 0)

def hiro_impact(trade, state, mult):
    cust = classify_side(trade)           # +1 buy, -1 sell (customer)
    if cust == 0: return 0.0
    is_call = (trade.type == "C")
    iv = trade.iv or solve_iv(trade, state)
    # delta (BS utk index/saham, Black-76 utk futures)
    delta = bs_delta(state.spot, trade.strike, T(trade), iv, state.r, state.q, is_call)
    # arah hedging underlying oleh dealer = -(delta posisi dealer); dealer = -customer
    dealer_delta = -(cust) * delta        # posisi delta dealer dari trade ini
    hedge_flow   = -dealer_delta          # underlying yg dibeli(+)/dijual(-) dealer
    return hedge_flow * trade.size * mult * state.spot   # delta-notional $

def run_hiro(stream, state_at, mult=100):
    total=calls=puts=0.0; out=[]
    for tr in stream:                      # urut waktu, reset tiap sesi
        x = hiro_impact(tr, state_at(tr.ts), mult)
        total += x
        if tr.type=="C": calls += x
        else:            puts  += x
        out.append((tr.ts, total, calls, puts))
    return out
```

**[INFERENSI]** Tanda akhir diverifikasi agar: BUY CALL→+, SELL CALL→−, BUY PUT→−, SELL PUT→+ (sesuai definisi resmi B5). `solve_iv` = Newton-Raphson dari mid.

## D12. Rekomendasi teknologi

| Kebutuhan | Rekomendasi | Catatan |
| --- | --- | --- |
| Streaming trade | Databento **Live** client (Python/Rust/C++), schema `trades`/`tbbo` | Same API live & historical [FAKTA] |
| Delta real-time | Vektorisasi `numpy`; cache IV per kontrak; recompute hanya saat quote berubah | Black-76 utk /ES /NQ [INFERENSI] |
| State (akumulasi) | Streaming engine (mis. Pathway/Flink) atau ring-buffer in-memory per ticker | Reset harian; rolling window konfigurable |
| Render web | TradingView Lightweight Charts / uPlot (dual-axis, jutaan titik) | uPlot sangat cepat utk time-series besar [INFERENSI] |
| Prototipe | Python `matplotlib`/`plotly` dual-axis | Validasi metodologi cepat |

## D13. Beda HIRO vs alat flow lain

| Dimensi | SpotGamma HIRO | Unusual Whales | Cheddar Flow | GEXBOT (orderflow) |
| --- | --- | --- | --- | --- |
| Output inti | **Delta-notional hedging** terakumulasi (garis) [FAKTA] | Feed trade + **premium/net premium**, Market Tide [FAKTA] | Feed sweep/blok + dark pool prints [FAKTA] | **GEX/DEX orderflow** (perubahan imbalance) [FAKTA] |
| Fokus | Dampak hedging ke harga (what MM must do) [FAKTA] | Apa yang di-trade (sentimen, size, side) [FAKTA] | Deteksi flow institusional/sweep [FAKTA] | Konveksitas/positioning intraday [FAKTA] |
| Greek? | Ya — delta (notional) [FAKTA] | Sebagian (greeks dashboard) [FAKTA] | Tidak utama (premium-based) [INFERENSI] | Ya — gamma/delta/vanna/charm second-by-second [FAKTA] |
| Klasifikasi | Proprietary (filter hedged, retail) [PROPRIETARY] | Side via bid-ask spread [FAKTA] | Sweep/blok detection [FAKTA] | **Volatility-based**, presisi milidetik [FAKTA] |
| Visual | Garis kumulatif overlay harga [FAKTA] | Tabel feed + Net Premium chart [FAKTA] | Tabel feed + dark pool levels [FAKTA] | Convexity ladder + GEX profile [FAKTA] |

> Sumber: Unusual Whales (side, premium, net premium/Market Tide)[[14]](https://unusualwhales.com/information/how-to-interpret-types-of-option-transactions)[[17]](https://unusualwhales.com/information/premium)[[18]](https://unusualwhales.com/information/how-to-interpret-net-premium); Cheddar Flow (sweep + dark pool)[[19]](https://www.cheddarflow.com/); GEXBOT (orderflow engine, volatility-based, gex orderflow bar up/down)[[20]](https://www.gexbot.com/)[[21]](https://www.gexbot.com/docs); MenthorQ (lihat doc TRACE).
> 

---

# E. ADAPTASI UNTUK PROJEKKU (/ES & /NQ, Databento, Black-76)

<aside>
🎯

**Jawaban langsung atas catatanmu:** Untuk mereplikasi HIRO di /ES /NQ kamu **WAJIB punya data per-trade dengan sisi agresor**. **`bbo-1m` TIDAK cukup** — itu snapshot interval (forward-filled), tanpa info trade individual maupun sisi buy/sell. Pakai schema **`trades`** (atau **`tbbo`**) di GLBX.MDP3.[[7]](https://databento.com/docs/schemas-and-data-formats/trades)[[8]](https://databento.com/docs/schemas-and-data-formats/bbo)

</aside>

## E14a. Schema Databento mana yang dibutuhkan?

| Schema | Isi | Cukup utk HIRO? |
| --- | --- | --- |
| `bbo-1m` | Best bid/offer + last sale tiap 1 menit (interval, forward-fill)[[8]](https://databento.com/docs/schemas-and-data-formats/bbo) | ❌ TIDAK — tak ada trade per-event maupun sisi agresor |
| `trades` | Tiap trade; field **`side`** = **A** (sell aggressor), **B** (buy aggressor), **N**[[7]](https://databento.com/docs/schemas-and-data-formats/trades) | ✅ INTI — sisi agresor langsung dari matching engine |
| `tbbo` | Tiap trade   **• BBO tepat sebelum trade**; juga punya `side`[[22]](https://databento.com/docs/schemas-and-data-formats/tbbo) | ✅ TERBAIK — trade + quote utk IV & cross-check klasifikasi |
| `mbp-1` | Top-of-book update space (L1)[[23]](https://databento.com/docs/schemas-and-data-formats/mbp-1) | △ Pelengkap quote, bukan sumber trade utama |

**Rekomendasi:** ambil **`tbbo`** sebagai sumber utama (trade + bid/ask sebelum trade → langsung bisa hitung mid untuk IV & verifikasi sisi), atau **`trades`** + langganan `mbp-1`/`bbo-1s` untuk quote. **[INFERENSI rekayasa]**

> **Keuntungan CME vs OPRA:** di GLBX.MDP3 field `side` adalah **aggressor dari matching engine** (A=seller, B=buyer) — jadi klasifikasi buy/sell **lebih andal & tak perlu Lee-Ready** seperti di OPRA.[[7]](https://databento.com/docs/schemas-and-data-formats/trades)[[24]](https://databento.com/docs/standards-and-conventions/common-fields-enums-types) **[FAKTA]** Catatan: `side` adalah **aggressor**, bukan otomatis "customer" — di futures sulit memisah dealer vs customer; perlakukan aggressor sebagai proxy customer-initiated. **[INFERENSI]**
> 

## E14b. Black-76 untuk /ES /NQ

- Opsi /ES /NQ adalah **opsi atas futures** ⇒ pakai **Black-76** (varian BS untuk futures), bukan BSM-on-spot. Databento sendiri mendemokan greeks CME via Black-76 (delta, gamma, theta, vega, rho).[[9]](https://databento.com/blog/option-greeks) **[FAKTA]**
- **Delta Black-76:** `δ_call = e^{−rT} N(d1)`, `δ_put = −e^{−rT} N(−d1)`, `d1 = [ln(F/K) + ½σ²T]/(σ√T)`. Underlying = **harga futures F**, bukan spot. **[FAKTA rumus standar]**
- **Multiplier:** /ES = **$50 × indeks**, /NQ = **$20 × indeks** (ganti `mult=100` → `50`/`20`).[[25]](https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.contractSpecs.html) **[FAKTA spesifikasi CME]**
- **Notional:** delta-notional = `δ × q × mult × F`. **[INFERENSI konsisten HIRO]**
- **Rate/dividend:** Black-76 sudah memuat carry lewat F; pakai r=SOFR utk diskon `e^{−rT}`, q tidak dipakai (sudah di F). **[INFERENSI]**

## E14c. Apa yang berubah vs HIRO SPX SpotGamma

| Aspek | HIRO SPX (SpotGamma) | Versi /ES /NQ kamu |
| --- | --- | --- |
| Feed | OPRA (opsi listed AS) | CME GLBX.MDP3 (options on futures) |
| Klasifikasi sisi | Quote-rule + filter proprietary | **Aggressor langsung** (`side` A/B) — lebih bersih |
| Underlying | Spot index (SPX) | Future price (ES/NQ) |
| Model greek | Black-Scholes-Merton | **Black-76** |
| Multiplier | 100 | $50 (/ES), $20 (/NQ) |
| Universe | 400+ ticker | Fokus /ES /NQ (+ mungkin opsi mingguan) |
| Dealer/customer | Asumsi + deteksi retail | Hanya aggressor proxy; tak ada label customer eksplisit |

**Yang perlu kamu reverse-engineer / asumsikan:** (1) memetakan aggressor→customer (proxy), (2) filter trade hedged/spread (mis. abaikan leg yang jelas bagian spread), (3) IV solver dari quote CME, (4) normalisasi sinyal jika ingin gauge ala HIRO Signal. **[INFERENSI/PROPRIETARY]**

---

# YANG MASIH PROPRIETARY / ASUMSI + reverse-engineering

<aside>
🔒

Bagian berikut **tidak dipublikasikan** SpotGamma. Untuk replikasi, ini titik yang harus kamu estimasi.

</aside>

**1. Algoritma klasifikasi trade & filter "hedged".** [PROPRIETARY] — "proprietary logic to filter out some trades that we consider hedged".[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf) Reverse: untuk OPRA pakai Lee-Ready/quote-rule; untuk CME pakai `side` aggressor. Filter spread: deteksi multi-leg simultan (timestamp + size sama) lalu net-kan. **[INFERENSI]**

**2. Bobot/kontekstualisasi block trade.** [PROPRIETARY] — algo baru "better contextualize big trades".[[5]](https://spotgamma.com/hiro-updated-algo-logic-new-features/) Reverse: dampen outlier (winsorize) atau bobot oleh likuiditas. **[INFERENSI]**

**3. Deteksi retail.** [PROPRIETARY].[[3]](https://spotgamma.com/how-to-use-spotgamma-hiro-indicator/) Reverse: heuristik ukuran kecil + venue/ exchange tertentu. **[INFERENSI]**

**4. Normalisasi "HIRO Signal" lintas instrumen + range 5/30-hari.** [PROPRIETARY].[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf) Reverse: z-score / percentile delta-notional harian per ticker. **[INFERENSI]**

**5. Impact threshold Flow Alerts.** [PROPRIETARY] — "specific impact threshold for the given security".[[12]](https://support.spotgamma.com/hc/en-us/articles/47871269691667-What-are-HIRO-Flow-Alerts) Reverse: ambang relatif vs distribusi flow historis ticker. **[INFERENSI]**

**6. Model greek/IV/rate persis.** [TIDAK TERDOKUMENTASI]. Reverse: BS (index) / Black-76 (futures); IV dari mid (NR); r=SOFR. **[INFERENSI]**

**7. Faktor notional persis (delta-shares vs delta-dollar).** [TIDAK TERDOKUMENTASI]. "Delta notional" ⇒ kemungkinan δ×S×m×q. **[INFERENSI]**

---

# Daftar sumber utama

**SpotGamma (primer):**

- What is the SpotGamma HIRO Indicator — support center.[[1]](https://support.spotgamma.com/hc/en-us/articles/4420646443539-What-is-the-SpotGamma-HIRO-Indicator)
- HIRO Indicator (product page) — definisi, contoh 2/24/25, beda vs flow tools.[[2]](https://spotgamma.com/hiro-indicator/)
- How to Use The SpotGamma HIRO Indicator (FAQ) — garis/warna, HIRO Signal.[[3]](https://spotgamma.com/how-to-use-spotgamma-hiro-indicator/)
- Sliding scale HIRO Signal — tanda merah/hijau/kuning.[[4]](https://support.spotgamma.com/hc/en-us/articles/4421122374419-What-does-the-sliding-scale-in-the-HIRO-Signal-column-indicate)
- HIRO Updated Algo Logic & New Features — cumulative rolling sum, 5-min, block trade.[[5]](https://spotgamma.com/hiro-updated-algo-logic-new-features/)
- SpotGamma HIRO User Guide (PDF, Des 2025) — sumbu ganda, Tape, All Trades filter hedged, rolling window.[[6]](https://spotgamma.com/wp-content/uploads/2025/10/SpotGamma-HIRO-User-Guide-2.pdf)
- Trading Stocks With SpotGamma and Bookmap HIRO — mekanik MM, divergence AMD.[[10]](https://spotgamma.com/trading-stocks-with-spotgamma-and-bookmap-hiro/)
- What is the Bloomberg HIRO Indicator — monitors all trades real time.[[11]](https://support.bloomberg.spotgamma.com/hc/en-us/articles/18660578974739-What-is-the-SpotGamma-HIRO-Indicator)
- What are HIRO Flow Alerts — impact threshold.[[12]](https://support.spotgamma.com/hc/en-us/articles/47871269691667-What-are-HIRO-Flow-Alerts)
- How can I use the SpotGamma HIRO to help me trade — Call/Put Wall flatten.[[13]](https://support.spotgamma.com/hc/en-us/articles/15169160339475-How-can-I-use-the-SpotGamma-HIRO-to-help-me-trade)
- Put/Call HIRO chart — calls oranye, puts biru.[[15]](https://support.spotgamma.com/hc/en-us/articles/12284010265363-What-does-the-Put-Call-HIRO-Stock-Chart-indicate)
- Trading Stock Using Equity Hub and HIRO — konfirmasi arah.[[16]](https://spotgamma.com/trading-stock-using-equity-hub-hiro/)

**Databento (untuk /ES /NQ):**

- Trades schema — field `side` aggressor A/B/N.[[7]](https://databento.com/docs/schemas-and-data-formats/trades)
- BBO on interval — interval 1s/1m, forward-fill.[[8]](https://databento.com/docs/schemas-and-data-formats/bbo)
- Computing Option Greeks (Black-76 untuk CME).[[9]](https://databento.com/blog/option-greeks)
- TBBO — trade + BBO sebelum trade.[[22]](https://databento.com/docs/schemas-and-data-formats/tbbo)
- MBP-1 — top of book.[[23]](https://databento.com/docs/schemas-and-data-formats/mbp-1)
- Common fields/enums — A=seller aggressor, B=buyer aggressor.[[24]](https://databento.com/docs/standards-and-conventions/common-fields-enums-types)
- E-mini S&P 500 contract specs (multiplier).[[25]](https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.contractSpecs.html)

**Pembanding flow:**

- Unusual Whales — interpret side (bid-ask).[[14]](https://unusualwhales.com/information/how-to-interpret-types-of-option-transactions) Premium.[[17]](https://unusualwhales.com/information/premium) Net Premium / Market Tide.[[18]](https://unusualwhales.com/information/how-to-interpret-net-premium)
- Cheddar Flow — sweep + dark pool.[[19]](https://www.cheddarflow.com/)
- GEXBOT — orderflow engine, volatility-based.[[20]](https://www.gexbot.com/) Docs (gex orderflow).[[21]](https://www.gexbot.com/docs)

<aside>
⚠️

**Disclaimer akurasi:** definisi HIRO (delta-notional aggregate), arah tanda, garis/warna, sumbu ganda, rolling window, contoh divergence, schema Databento (`trades`/`tbbo`/`bbo`), Black-76 utk CME, dan multiplier = **terdokumentasi**. Algoritma klasifikasi & filter hedged, bobot block, deteksi retail, normalisasi HIRO Signal, impact threshold, IV/rate persis = **proprietary/inferensi**. Validasi numerik dengan membandingkan garis kamu vs screenshot HIRO pada beberapa sesi.

</aside>