# Prompt untuk Sesi Baru — FlowDesk Fog WebGL Heatmap

Salin teks di bawah ini sebagai pesan pertama di sesi ZCode baru.

---

Kerja di repo FlowDesk: `C:\Users\ollama\Downloads\flowdesk\flowdesk` (Windows, cmd.exe, git branch `main`).

Baca dulu, berurutan:
1. `AGENTS.md` (kontrak agen — patuhi).
2. `HANDOFF.md` (status terkini Fog page + tugas berikutnya — INI yang paling penting).
3. `docs/reference/reverse-engineering-trace-gamma-heatmap.md` (resep render TRACE).

Tugas: lanjutkan rebuild panel kanan Fog page (`/fog`) agar heatmap GEX/DEX-nya
match SpotGamma TRACE — mulus, seperti asap, tanpa banding/streak vertikal.
Keputusan yang SUDAH diambil user (jangan dibuka lagi):
- Render engine: **WebGL** pakai `regl` (sudah ke-install di `apps/dashboard`, versi 2.1.1).
- Rentang sumbu harga: **clamp dinamis ±180pt sekitar forward** (bukan union range),
  plus edge-extrapolation (hold nilai tepi terdekat, bukan NaN keras) untuk
  menghilangkan banding. Akar banding sudah diverifikasi di HANDOFF — jangan
  investigasi ulang.

Yang sudah selesai sesi lalu dan JANGAN dirombak tanpa alasan (semua lolos
typecheck+build, belum di-commit):
- Warna locked sudah jadi DEEP: turquoise `#0FB5A8`, crimson `#B5002E`.
- Price line sudah jadi candlestick 5-menit (naik body `#FAFAF7`, turun `#000000`,
  wick/border `#FAFAF7`).
- Bug orientasi sumbu-Y sudah dibetulkan (high price di atas).
- Label harga sudah di sisi KANAN.
- Crosshair sudah ada (overlay canvas terpisah).

Rencana implementasi WebGL (detail lengkap + params di HANDOFF §"NEXT TASK"):
1. Field grid axis = medianForward ±180pt; di luar coverage frame → hold edge value.
2. Upload field sebagai float texture → fragment shader: bilinear GPU + diverging
   colormap (deep turquoise / center hitam / deep crimson, power curve ~0.7).
3. GPU bloom: bright-pass → separable gaussian blur → additive composite.
4. Contour (marching squares), candle, crosshair, axis tetap di Canvas2D overlay
   DI ATAS canvas WebGL (stack: gl → overlay 2d → crosshair). Reuse fungsi yang
   sudah ada di `GexHeatmap.tsx`.

PENTING soal tooling sesi lalu (ada kendala):
- Tool Write sempat gagal saat menulis file besar sekaligus (timeout 524). Untuk
  file besar seperti `GexHeatmap.tsx`, tulis BERTAHAP: buat kerangka dulu lalu
  Edit per bagian, atau pecah jadi beberapa Edit kecil. Jangan satu Write raksasa.
- ESLint belum dikonfigurasi → `npm run lint` masuk prompt interaktif, JANGAN
  dipakai. Gate sebenarnya: `cd apps\dashboard && npm run typecheck` lalu
  `npm run build`.
- pnpm tidak di PATH; pakai `corepack pnpm ...` kalau perlu install.
- Verifikasi VISUAL pakai Playwright (tersedia): playwright-core di
  `C:/Users/ollama/AppData/Roaming/npm/node_modules/playwright-core`, Chrome di
  `C:\Program Files\Google\Chrome\Application\chrome.exe`. Tulis script Node kecil
  → launch chromium (executablePath itu) → `goto('http://localhost:4325/fog')` →
  `page.mouse.move(...)` (untuk crosshair) → screenshot ke PNG temp → Read PNG itu
  untuk inspeksi. Start dev server dulu:
  `cd apps\dashboard && node node_modules\next\dist\bin\next dev -p 4325`.

Patuhi AGENTS.md: jangan ubah engine/kontrak/locked value lain tanpa izin; tambahkan
test untuk perubahan perilaku; jalankan verifikasi sebelum klaim selesai. Setelah
heatmap WebGL jadi dan terverifikasi visual, tanya user apakah mau di-commit
(konvensi sejauh ini: commit langsung ke `main`).
