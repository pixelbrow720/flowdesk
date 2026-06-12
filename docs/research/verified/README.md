# FlowDesk — Paket Hasil Riset (Source of Truth)

Paket ini berisi **hasil riset terverifikasi** untuk FlowDesk — BUKAN kode aplikasi. Tujuannya: jadi **sumber kebenaran (source of truth)** yang dipakai Opus di VSCode saat mengerjakan layer empiris/repo. Letakkan isi paket ini di repo sebagai `docs/research/` agar Opus bekerja dari spec yang sudah dikunci, bukan dari ingatan.

## Isi paket
| File | Apa isinya |
|---|---|
| `01-Laporan-Riset-Definitif.md` | Laporan riset lengkap Track A–L (mekanika 0DTE, schema Databento, Black-76 greeks, GEX/DEX/DDOI, HIRO, vol surface, harness validasi, arsitektur backend/DB/FE, auth). |
| `02-Audit-RedTeam-Validasi.md` | Audit red-team Fase 1 (verification ledger + koreksi) & Fase 2 (status empiris). |
| `black76_validate.py` | Skrip validasi greeks Black-76 (parity, finite-difference vanna/charm, round-trip IV). Tanpa dependensi scipy. |

## Status pembuktian (ringkas)
- ✅ **TERBUKTI (math layer):** Black-76 harga/delta/gamma/vega, **vanna** (`−e^{−rT}φ(d1)d2/σ`) & **charm** (bentuk eksak), faktor GEX (`Γ·Q·M·F²·0.01`), parity, round-trip IV. Dicocokkan numerik vs finite-difference (~1e-8 s/d 1e-13).
- ✅ **TERVERIFIKASI (sumber):** 4 sitasi akademik nyata + angka cocok; 0 FABRICATED-SOURCE; 1 kontradiksi internal (RTY) diperbaiki.
- ⏳ **BELUM DIUJI (empirical layer):** apakah struktur GEX prediktif untuk harga /ES /NQ — butuh data Databento nyata + repo. Ini bagian yang dikerjakan Opus di VSCode (Track G, Lapis 1–2).
- ❓ **UNVERIFIED (kode vs dokumen):** klaim laporan tentang `exposure.py`, `feed/live.py`, `schema_version=1` belum dibandingkan dgn kode aktual (tanpa akses repo saat riset).

## Pembagian kerja
- **Notion AI (paket ini):** layer dokumen + matematika → **LOCKED**.
- **Opus di VSCode:** layer empiris/repo → jalankan harness Track G (Lapis 1→2) pada data /ES /NQ nyata, tutup gap kode-vs-dokumen, implement live feed.

## LOCKED CONTRACT (jangan diubah tanpa label eksplisit)
- Warna: turquoise `#40E0D0` / crimson `#E0183C` / base `#000000` (interpolasi OKLab).
- Font: Space Grotesk + JetBrains Mono.
- /ES M=$50 step 5; /NQ M=$20 step 10.
- RTH 09:30–16:00 ET, 1-menit, replay 90 hari.
- Black-76; `r=ln(1+SOFR)`; IV mid Newton→bisection tol 1e-6.
- Dealer long-call/short-put: `DEALER_SIGN_CALL=+1`, `DEALER_SIGN_PUT=−1`.
- `GEX = Γ·VOL·M·F²·0.01` (VOL kumulatif sejak RTH); walls = gamma-$ Top-3.
- HIRO optional; Discord OAuth (`identify`, `guilds.members.read`) + `DESK_ROLE_ID`; `SCHEMA_VERSION=1`.

## Cara pakai di repo
1. Salin folder ini ke `docs/research/` di repo FlowDesk.
2. Rujuk `01-Laporan-Riset-Definitif.md` sebagai spec saat membangun harness Track G.
3. Jalankan `python black76_validate.py` untuk membuktikan ulang greeks sebelum menyentuh modul pricing.
4. Saat membangun Lapis 1 (rekonsiliasi ΔOI), verifikasi dulu granularitas ΔOI per-strike harian di `statistics` GLBX (prasyarat — lihat §G.10.1).

*Tanggal akses sumber riset: 12 Juni 2026.*
