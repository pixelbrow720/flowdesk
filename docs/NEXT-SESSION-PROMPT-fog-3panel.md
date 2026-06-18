# Prompt untuk Sesi Baru — FlowDesk Fog 3-Panel Strike Terminal

Salin teks di bawah sebagai pesan pertama di sesi ZCode baru.

---

Kerja di repo FlowDesk: `C:\Users\ollama\Downloads\flowdesk\flowdesk` (Windows,
cmd.exe, git branch `main`).

Baca dulu, berurutan:
1. `AGENTS.md` (kontrak agen — patuhi).
2. `docs/superpowers/specs/2026-06-17-fog-three-panel-design.md` (SPEC desain —
   sudah disetujui user, ini yang dikerjakan).
3. `HANDOFF.md` (§"NEXT TASK: Fog 3-panel" — status terkini + sisa kerja).

Tugas: ganti panel Fog (`/fog`) dari heatmap TRACE jadi **tiga panel profil
strike** yang berbagi satu sumbu-Y (harga strike). Heatmap dipensiunkan (file
`GexHeatmap.tsx`/`glHeatmap.ts` TETAP di repo, cukup jangan di-import lagi).

Keputusan user yang SUDAH FINAL (jangan dibuka lagi):
- 3 panel: gutter harga | KIRI struktur GEX (+IV smile) | TENGAH dinamika |
  KANAN DEX. Semua sejajar di sumbu strike, scroll bareng.
- KIRI = bar `net_gex` dua arah + marker call/put wall + garis gamma_flip
  (`levels.*`), plus overlay IV-smile (SVI dari `surface`) **default ON**.
  Range hairline grey DIPINDAH dari kiri ke tengah (hilangkan dari kiri).
- TENGAH = ide user: **range band** min↔max `net_gex` (fill ikut tanda,
  turquoise/crimson, opacity rendah) + **garis current** `bone.0` + **flow**
  partikel dari `diff5m` (naik→mengalir keluar dari nol; turun→balik ke nol).
- KANAN = bar `net_dex` dua arah, sebahasa dgn kiri, tanpa flow/band.
- Toggle: "IV smile" (default ON) + "Flow" (default ON, auto-OFF saat
  `prefers-reduced-motion`). Gaya kontrol = ikut selector GEX top-left yang ada.
- Estetika WAJIB terasa dibuat-tangan, BUKAN AI-generated. Acuan rasa =
  `StrikePanel`/`GexCell` di `page.tsx` sekarang (type mono kecil, hairline
  `rule`, tanpa border tebal). Warna: token tailwind sudah ada
  (`turquoise.deep`, `crimson.deep`, `bone.0/3`, `amber.current`, `rule`,
  `tide.blue/red`).

SUDAH SELESAI sesi lalu (JANGAN diulang):
- Spec ditulis + di-commit (`e2ee4a0`).
- `apps/dashboard/src/components/fog/flowField.ts` SUDAH dibuat (animator
  partikel Canvas2D, `createFlowField(canvas) → {update, stop, destroy}`).
  BELUM di-commit, BELUM dipakai. Cek isinya dulu sebelum nulis ulang.

SISA KERJA (urut):
1. Perluas memo `strikes` di `page.tsx`: hitung `net_gex` DAN `net_dex` sekaligus
   per strike (sekarang cuma satu metrik via selector). Tambah session min/max +
   `diff5m` ternormalisasi untuk dipakai TENGAH. Satu sumber data, tiga panel.
2. Ganti blok render: drop import `GexHeatmap`/`PriceChart`/`heatmapFrames`,
   bikin grid 3-panel (gutter | GexStructure | Dynamics | Dex).
3. TENGAH: band + current line pakai DOM/CSS; flow pakai `flowField.ts` di SATU
   canvas overlay kolom tengah (rAF, hormati reduced-motion).
4. KIRI: pindahkan marker wall + gamma_flip dari `levels`, tambah IV-smile
   overlay (kurva tipis dari `surface.svi_*` / atm_vol vs strike) + toggle.
5. KANAN: bar `net_dex`.

PENTING soal tooling (kendala nyata sesi lalu — patuhi):
- **JANGAN pakai tool Write untuk file besar** (`page.tsx` ~725 baris). Write
  raksasa berkali-kali GAGAL ("input failed validation" / kepotong) dan bikin
  stuck. Caranya: **Edit potongan kecil** satu per satu. Kalau benar-benar perlu
  file baru besar, tulis kerangka kecil dulu lalu Edit menambah per bagian.
- Sebelum Edit, file HARUS sudah di-Read di sesi ini (harness mewajibkan).
- ESLint belum dikonfigurasi → `npm run lint` JANGAN dipakai (prompt
  interaktif). Gate sebenarnya: `cd apps\dashboard && npm run typecheck` lalu
  `npm run build`.
- Dev server: `cd apps\dashboard && node node_modules\next\dist\bin\next dev -p 4325`
  → `http://localhost:4325/fog`.
- pnpm tidak di PATH; pakai `corepack pnpm ...` kalau perlu install (regl sudah
  ada dari kerja heatmap, nggak wajib dipakai — flowField pakai Canvas2D).
- Verifikasi VISUAL pakai Playwright: playwright-core di
  `C:/Users/ollama/AppData/Roaming/npm/node_modules/playwright-core`, Chrome di
  `C:\Program Files\Google\Chrome\Application\chrome.exe`. Launch chromium
  (executablePath itu) dengan flags `--use-gl=angle --use-angle=swiftshader
  --enable-unsafe-swiftshader --ignore-gpu-blocklist` → `goto('.../fog')` →
  screenshot PNG temp → Read PNG. Bersihkan file temp setelahnya.

Patuhi AGENTS.md: jangan ubah engine/kontrak/locked value; tambah test untuk
helper murni (band range + percentile + normalisasi diff5m); jalankan verifikasi
sebelum klaim selesai. Setelah jadi & terverifikasi visual, tanya user apakah
mau di-commit (konvensi: commit langsung ke `main`).
