# Integrasi FlowDesk ke FlowJob — Rencana Implementasi

> Dokumen perencanaan untuk menyatukan terminal FlowDesk (`/ES` & `/NQ` 0DTE GEX/DEX) ke dalam website utama FlowJob di `flowjob.id/dashboard/app`.
>
> **Status:** Rencana (belum dieksekusi).
> **Scope:** Frontend FlowDesk dimasukkan ke dalam `flowjob-master` sebagai route `/dashboard/app` yang di-gate oleh tier DESK. Backend FlowDesk di-host terpisah di VPS.
> **Catatan:** File ini hanya dokumentasi. Tidak ada kode di project FlowDesk atau FlowJob yang disentuh saat pembuatan file ini.

---

## Daftar Isi

1. [Tujuan & Konteks](#1-tujuan--konteks)
2. [Pemilihan Arsitektur](#2-pemilihan-arsitektur)
3. [Lokasi Integrasi Frontend](#3-lokasi-integrasi-frontend)
4. [Struktur File Target di FlowJob](#4-struktur-file-target-di-flowjob)
5. [Fase Implementasi (9 Fase)](#5-fase-implementasi-9-fase)
6. [Rekomendasi VPS & Hosting Backend](#6-rekomendasi-vps--hosting-backend)
7. [Dependency & Kompatibilitas](#7-dependency--kompatibilitas)
8. [Auth & Gate DESK](#8-auth--gate-desk)
9. [Routing & Landing Page Jadi Docs](#9-routing--landing-page-jadi-docs)
10. [Environment Variables](#10-environment-variables)
11. [Risiko & Mitigasi](#11-risiko--mitigasi)
12. [Checklist Pre-Deploy](#12-checklist-pre-deploy)

---

## 1. Tujuan & Konteks

### Apa yang ingin dicapai

- Memberikan pengguna DESK akses ke terminal FlowDesk langsung dari dalam website FlowJob utama (`flowjob.id/dashboard/app`).
- Menjaga kenyamanan pengguna: login, pembayaran, dan entitlement sudah ada di FlowJob; terminal tinggal "nyala" di belakang gate DESK.
- Mengubah landing page `apps/landing` FlowDesk menjadi dokumentasi publik (`/docs/terminal`) di FlowJob, karena fungsi marketing sudah diambil alih oleh `flowjob.id`.

### Dua repo yang terlibat

| Repo | Path Lokal | Peran | Stack |
|---|---|---|---|
| `flowjob-master` | `...\flowdesk\flowjob-master` | Website utama + auth + pembayaran + kurikulum | Next.js 15.5 App Router, React 18.3, Tailwind 3.4, Supabase, Midtrans, Discord OAuth |
| `flowdesk` | `...\flowdesk\flowdesk` | Terminal + Python compute + API | Next.js 15.1 (dashboard), React 19, FastAPI, Python engine, Redis, TimescaleDB |

---

## 2. Pemilihan Arsitektur

### Alasan memilih Opsi 1: Port komponen ke dalam FlowJob

Ada 3 strategi integrasi yang mungkin:

| Opsi | Keuntungan | Kerugian | Rekomendasi |
|---|---|---|---|
| **A. Port komponen ke `flowjob-master`** (dipilih) | UX nyatu, satu deploy, auth/gate native, SEO & analytics terpusat | Perlu kerja menyesuaikan versi & dependency | **Rekomendasi** — user DESK sudah berada di FlowJob |
| B. Embed via iframe | Cepat, isolasi penuh | Auth harus dijembatani, UX patah-patah, styling terpisah | Tidak direkomendasikan untuk produk utama |
| C. Subdomain terpisah | Gampang, minim konflik | Terasa seperti dua aplikasi berbeda | Bisa jadi fallback, tapi kurang mulus |

Dengan Opsi 1, halaman `/dashboard/app` yang saat ini masih berisi placeholder `AppComingSoonClient` akan diganti dengan terminal FlowDesk yang asli. Gate tier DESK sudah ada dan tinggal di-reuse.

---

## 3. Lokasi Integrasi Frontend

### Titik masuk: `app/dashboard/app/` di `flowjob-master`

Struktur saat ini:

```
app/dashboard/app/
├── page.tsx                 ← server component, cek DESK entitlement
├── AppComingSoonClient.tsx  ← placeholder "terminal sedang dibangun"
└── AppLockedClient.tsx      ← CTA untuk user yang belum DESK
```

`page.tsx` saat ini:

- Jika user belum punya DESK → render `AppLockedClient`.
- Jika user punya DESK → render `AppComingSoonClient` (placeholder).

**Yang harus diubah:**

- Jika user punya DESK → render komponen terminal asli (mis. `TerminalClient`).
- `AppLockedClient` tetap dipertahankan untuk non-DESK.
- Route legacy `/app` sudah redirect permanen (HTTP 308) ke `/dashboard/app` — tidak perlu diubah.

### Layout khusus untuk terminal

Halaman terminal sebaiknya memakai layout full-width tanpa sidebar `UserShell` yang biasa di dashboard FlowJob. Terminal butuh layar penuh.

```
app/dashboard/
├── layout.tsx            ← layout biasa FlowJob (UserShell, sidebar)
└── app/
    ├── layout.tsx        ← layout khusus: full-width, dark, no sidebar
    ├── page.tsx          ← server gate + render TerminalClient
    └── _components/
        ├── TerminalClient.tsx   ← client wrapper utama
        ├── TerminalShell.tsx    ← chrome / shell
        └── ...                  ← komponen fog / flux / arc
```

---

## 4. Struktur File Target di FlowJob

Berikut struktur rekomendasi setelah integrasi. Semua path di bawah ini berada di `flowjob-master/`.

```
flowjob-master/
├── app/
│   ├── dashboard/
│   │   ├── layout.tsx                    ← layout FlowJob biasa
│   │   └── app/
│   │       ├── layout.tsx                ← full-width terminal layout
│   │       ├── page.tsx                  ← gate + TerminalClient
│   │       ├── docs/                     ← (opsional) docs terminal
│   │       │   ├── layout.tsx
│   │       │   └── page.tsx
│   │       └── _components/
│   │           ├── TerminalClient.tsx
│   │           └── TerminalSettings.tsx
│   ├── (marketing)/                      ← tidak disentuh
│   └── api/                              ← tidak disentuh
├── components/
│   ├── terminal/                         ← dipindah dari FlowDesk
│   │   ├── TerminalShell.tsx
│   │   ├── chrome.tsx
│   │   └── Navbar.tsx                    ← atau reuse FlowJob navbar
│   ├── fog/                              ← dipindah dari FlowDesk
│   │   ├── GexHeatmap.tsx
│   │   ├── LevelsChartPanel.tsx
│   │   ├── PriceChart.tsx
│   │   ├── panels.tsx
│   │   ├── strikeMath.ts
│   │   ├── levelsChart.ts
│   │   └── glHeatmap.ts
│   ├── flux/                             ← dipindah dari FlowDesk
│   │   ├── fluxSeries.ts
│   │   └── FluxPanel.tsx
│   └── arc/                              ← dipindah dari FlowDesk (jika dipakai)
│       ├── ArcPanel.tsx
│       ├── arcSurface.ts
│       └── arcSurface.test.ts
├── lib/
│   └── terminal/                         ← dipindah dari FlowDesk
│       ├── api.ts
│       ├── useLiveSnapshots.ts
│       ├── useReplaySnapshots.ts
│       ├── useTerminalFeed.ts
│       └── playback.ts
└── public/
    └── data/                             ← fallback static session snapshots
        ├── ES_2026-06-09.json
        └── NQ_2026-06-09.json
```

### Catatan komponen `arc/`

Komponen Arc pakai `three.js` + `regl`. Ini paling berat. Jika di awal ingin mengurangi risiko, bisa sementara di-skip atau ditandai `EXPERIMENTAL`. Fog dan Flux lebih stabil dan lebih penting untuk user DESK.

---

## 5. Fase Implementasi (9 Fase)

### Fase 0 — Keputusan & Inventarisasi

1. Tentukan URL backend production (contoh: `https://api.flowdesk.flowjob.id`).
2. Buat branch baru di `flowjob-master`: `feat/integrate-flowdesk-terminal`.
3. Daftarkan semua file yang akan dipindah dari `flowdesk/apps/dashboard/src/`.
4. Cek perbedaan versi React & Next.js; putuskan strategi kompatibilitas (lihat bagian 7).

### Fase 1 — Hosting Backend FlowDesk

Backend **tidak boleh di-host di Vercel** karena:

- Python engine butuh runtime terus-menerus, bukan serverless.
- WebSocket dari FastAPI perlu koneksi persistent.
- Worker hitung per menit memerlukan proses yang hidup terus.

Langkah:

1. Pilih VPS (rekomendasi di bagian 6).
2. Clone repo FlowDesk ke VPS.
3. Install Python 3.11+ dan dependencies:
   ```bash
   pip install -e services/engine
   pip install -e services/api
   ```
4. Setup Postgres/TimescaleDB (bisa di VPS yang sama).
5. Setup Redis (bisa di VPS yang sama).
6. Jalankan API + worker via `systemd` atau `docker-compose`.
7. Pasang domain + SSL (Cloudflare atau Certbot/Caddy).
8. Simpan URL backend untuk environment variable (lihat bagian 10).

### Fase 2 — Siapkan Branch & Dependency di FlowJob

1. Checkout branch:
   ```bash
   git checkout -b feat/integrate-flowdesk-terminal
   ```
2. Install dependency terminal:
   ```bash
   npm install lightweight-charts
   npm install three regl
   npm install -D @types/three
   ```
3. Verifikasi `package.json` tetap bersih dan tidak ada konflik versi.

### Fase 3 — Pindahkan Komponen FlowDesk

1. **Salin** (bukan pindah — supaya sumber asli tetap ada) dari `flowdesk/apps/dashboard/src/components/*` ke `flowjob-master/components/terminal/`, `components/fog/`, `components/flux/`, `components/arc/`.
2. Salin `lib/*` dari FlowDesk ke `lib/terminal/`.
3. Sesuaikan import path. Contoh:
   - `@/lib/api` → `@/lib/terminal/api`
   - `@/components/terminal/TerminalShell` tetap (path sudah cocok dengan alias `@/`)
4. Pastikan tidak ada import yang merujuk ke struktur `apps/dashboard` lama.

### Fase 4 — Ganti Halaman `/dashboard/app`

1. Edit `app/dashboard/app/page.tsx`.
2. Tambahkan import:
   ```tsx
   import { TerminalClient } from './_components/TerminalClient';
   ```
3. Ubah return untuk user DESK:
   ```tsx
   if (!hasDesk) {
     return <AppLockedClient userTier={user.tier} />;
   }
   return <TerminalClient />;
   ```
4. Tambahkan `app/dashboard/app/layout.tsx` khusus yang:
   - Tanpa sidebar `UserShell`.
   - Full-width, dark background, font mono.
   - Tetap membaca session user (untuk gate).

### Fase 5 — Sesuaikan Styling & Layout

1. Pendekatan campuran: chart/canvas tetap dark functional; shell/frame menyatu dengan design token FlowJob (`fey-*`).
2. Tambahkan utility class atau CSS variable jika perlu di `globals.css` flowjob, tapi **batasi scope** ke route `/dashboard/app` (hindari override global).
3. Pastikan `prefers-reduced-motion` tetap dihormati.

### Fase 6 — Ubah Landing Page FlowDesk Menjadi Docs

Pilih salah satu (detail di bagian 9):

- **Opsi A — Docs publik** di `app/docs/terminal/` (bisa diakses semua orang). **Rekomendasi.**
- **Opsi B — Docs private** di `app/dashboard/app/docs/` (hanya user DESK).

### Fase 7 — Sambungkan API & WebSocket

1. Tambahkan env var di Vercel flowjob:
   ```
   NEXT_PUBLIC_API_BASE_URL=https://api.flowdesk.flowjob.id
   ```
2. Pastikan `lib/terminal/api.ts` membaca env tersebut (default ke `http://localhost:8000` untuk dev).
3. Verifikasi WebSocket URL otomatis jadi `wss://` saat production HTTPS.
4. Uji end-to-end: buka `/dashboard/app` → terminal ambil snapshot → chart muncul.

### Fase 8 — Uji, Verifikasi, & Build

1. Jalankan di lokal:
   ```bash
   npm run typecheck && npm run lint && npm run test && npm run build
   ```
2. Uji manual di `http://localhost:5000/dashboard/app` dengan user DESK.
3. Uji dengan user non-DESK untuk memastikan `AppLockedClient` masih tampil.
4. Uji WebSocket live dan fallback replay/static.

### Fase 9 — Deploy ke Production

1. Buka PR ke `master` (Vercel akan auto-comment preview URL).
2. Review preview, pastikan env var sudah diatur di Vercel.
3. Merge → Vercel auto-deploy ke production.
4. Verifikasi terminal bisa diakses user DESK di `https://www.flowjob.id/dashboard/app`.

---

## 6. Rekomendasi VPS & Hosting Backend

### Kebutuhan resource riil

Backend FlowDesk menjalankan 4 proses:

| Proses | RAM idle | RAM peak | Catatan |
|---|---|---|---|
| FastAPI (uvicorn) | ~80–150 MB | ~200 MB | REST + WS |
| Worker | ~100–200 MB | ~400 MB | Hitung per menit (ES + NQ) |
| Redis | ~50–150 MB | ~256 MB | Snapshot hot |
| Postgres + TimescaleDB | ~400–800 MB | ~1.5 GB | Tergantung history |
| OS overhead | ~300–500 MB | — | Baseline Linux |
| **Total idle** | **~1.5 GB** | **~2.5 GB** | Aman di 4 GB RAM, lega di 8 GB |

Engine stdlib-only di jalur hitung (kecuali `fog.py` pakai numpy+scipy). CPU hanya spike sebentar tiap menit, idle sisanya.

### Rekomendasi VPS di budget $15–25/bulan

| Provider | Plan | Spec | Harga (perkiraan) | Catatan |
|---|---|---|---|---|
| **Hetzner** | CPX21 | 3 vCPU / 4 GB RAM / 80 GB NVMe | ~$8/bln | Sweet spot harga/performa |
| **Hetzner** | CPX31 | 4 vCPU / 8 GB RAM / 160 GB NVMe | ~$15/bln | **Rekomendasi** — lega untuk Postgres |
| DigitalOcean | Basic | 2 vCPU / 4 GB RAM / 80 GB SSD | $24/bln | Ekosistem rapi, pas di atas budget |
| Vultr | High Frequency | 2 vCPU / 4 GB RAM / 128 GB NVMe | ~$24/bln | Disk cepat |
| AWS Lightsail | 4 GB | 2 vCPU / 4 GB RAM / 80 GB SSD | ~$24/bln | Familiar, kurang worth vs Hetzner |

> Harga dapat berubah; verifikasi langsung di situs provider sebelum membeli.

### Rekomendasi akhir

Untuk budget $15–25/bulan, **pilih Hetzner CPX31** (4 vCPU / 8 GB RAM, ~$15/bln). Alasannya:

- RAM 8 GB lega untuk Python engine + Postgres + Redis dalam satu server.
- Masih di dalam budget, sisa bisa untuk domain/backup/monitoring.
- Disk NVMe mempercepat query TimescaleDB history.
- Jika user DESK tumbuh, upgrade tinggal satu klik.

> Hindari tier 1 GB RAM ($5). Postgres + Timescale bisa kehabisan memori di situ. Minimal **4 GB RAM**.

### Database: satu VPS atau terpisah?

| Opsi | Keuntungan | Kerugian | Kapan dipakai |
|---|---|---|---|
| **Semua di satu VPS** | Murah, simpel | Single point of failure | **Fase beta / user DESK masih sedikit** (rekomendasi sekarang) |
| Postgres managed terpisah (Supabase/Neon) | Backup & scaling mudah | Tambah biaya & kompleksitas | Saat user DESK sudah banyak |

**Rekomendasi sekarang:** semua di satu VPS Hetzner. Pindahkan database ke layanan terpisah hanya jika beban sudah terbukti besar.

---

## 7. Dependency & Kompatibilitas

### Perbedaan versi yang harus diselesaikan

| Paket | FlowJob (`flowjob-master`) | FlowDesk (`apps/dashboard`) | Risiko |
|---|---|---|---|
| React | 18.3.1 | **19.0.0** | Tinggi — API berbeda (`use`, ref-as-prop, dll) |
| React DOM | 18.3.1 | **19.0.0** | Tinggi |
| Next.js | 15.5.18 | 15.1.6 | Rendah — keduanya Next 15 App Router |
| Tailwind | 3.4.13 | 3.4.17 | Rendah — minor, kompatibel |
| TypeScript | 5.6.3 | 5.7.3 | Rendah |
| lightweight-charts | (belum ada) | ^5.2.0 | Perlu ditambah ke FlowJob |
| three / regl | (belum ada) | ^0.184 / ^2.1.1 | Perlu ditambah (jika Arc dipakai) |

### Strategi React 18 vs 19

Karena FlowJob (host) pakai React 18 dan komponen FlowDesk dibangun di React 19, **target host adalah React 18**. Komponen FlowDesk harus diturunkan agar kompatibel:

- Hapus penggunaan fitur khusus React 19 (mis. hook `use()`, perubahan `ref` sebagai prop biasa, Actions/`useActionState`).
- Sebagian besar komponen FlowDesk (fog/flux) kemungkinan besar tidak memakai fitur React 19 spesifik — verifikasi dengan `npm run typecheck` setelah porting.
- **Jangan** upgrade FlowJob ke React 19 hanya untuk ini; itu berisiko ke seluruh website produksi (Supabase SSR, framer-motion, dll).

### Hal yang harus dicek per file

- `lib/api.ts` FlowDesk sengaja **tanpa zod** (dependency-light). Pertahankan; tidak perlu menambah zod ke jalur terminal.
- Hooks `useLiveSnapshots` / `useReplaySnapshots` / `useTerminalFeed` — pastikan tidak memakai API React 19.
- File `*.test.ts` (mis. `strikeMath.test.ts`) memakai `node:test`. Putuskan apakah ikut dipindah atau dikonversi ke Vitest (FlowJob pakai Vitest).

---

## 8. Auth & Gate DESK

Integrasi melibatkan **dua lapis gate** yang harus konsisten:

### Lapis 1 — Gate di FlowJob (frontend/route)

Sudah ada di `app/dashboard/app/page.tsx`:

- Membaca session via `requireUser('/dashboard/app')`.
- Cek entitlement `kind = 'desk'`, `status = 'active'` di Supabase.
- Staff (`owner`/`admin`) otomatis dianggap punya DESK.
- Tidak DESK → `AppLockedClient`. Punya DESK → terminal.

### Lapis 2 — Gate di Backend FlowDesk (API/WS)

Dari arsitektur FlowDesk: "FastAPI service serves snapshots over REST/WebSocket **behind Discord-role auth**."

Artinya backend FlowDesk punya sistem auth sendiri (Discord OAuth + role). Perlu diputuskan bagaimana dua sistem ini saling percaya:

| Pendekatan | Cara kerja | Catatan |
|---|---|---|
| **A. Discord role sebagai jembatan** | FlowJob sudah sync Discord role DESK. Backend FlowDesk cek role yang sama. | Paling natural — keduanya pakai Discord role yang sama. **Rekomendasi.** |
| B. Shared token/JWT | FlowJob menerbitkan token DESK yang diverifikasi backend FlowDesk | Lebih banyak kerja, lebih ketat |
| C. API key per-request server-side | Frontend tidak akses API langsung; lewat proxy route di FlowJob | Aman tapi menambah hop & beban Vercel |

**Rekomendasi:** Pendekatan A. Karena FlowJob sudah melakukan Discord role sync untuk DESK (`DISCORD_ROLE_DESK`), dan backend FlowDesk sudah berbasis Discord-role auth, keduanya bisa memakai role DESK yang sama sebagai sumber kebenaran.

> **Penting:** verifikasi dulu mekanisme auth aktual di `services/api` FlowDesk (`docs/06-api-and-auth.md`) sebelum memilih final. Jangan asumsikan tanpa membaca.

---

## 9. Routing & Landing Page Jadi Docs

### Ide: landing page FlowDesk → halaman dokumentasi

Karena FlowJob sudah punya landing page produksi, `apps/landing` FlowDesk tidak lagi perlu sebagai marketing. Kontennya bisa diubah menjadi dokumentasi terminal.

### Opsi A — Docs publik (Rekomendasi)

```
app/docs/terminal/
├── layout.tsx
└── page.tsx
```

- URL: `flowjob.id/docs/terminal`
- Bisa diakses semua orang (calon user DESK baca dulu sebelum subscribe).
- Konten dari: copy landing FlowDesk + `docs/04-engine.md` (penjelasan GEX/DEX/FLUX).
- Bagus untuk SEO (gunakan `lib/seo` FlowJob).

### Opsi B — Docs private dalam terminal

```
app/dashboard/app/docs/
├── layout.tsx
└── page.tsx
```

- URL: `flowjob.id/dashboard/app/docs`
- Hanya user DESK yang bisa baca.
- Cocok untuk panduan internal pemakaian terminal.

### Topik dokumentasi yang disarankan

- Apa itu GEX (Gamma Exposure) dan DEX (Delta Exposure).
- Cara membaca strike ladder & per-strike net_gex bars.
- Call/Put walls, gamma flip, largest GEX/DEX.
- IV smile overlay (EXPERIMENTAL).
- FLUX (aggressor flow) dan ARC (jika dipakai).
- Jam sesi: PREMARKET → LIVE → CLOSED, arti `stale`/`expired`.

---

## 10. Environment Variables

### Di FlowJob (Vercel — Settings → Environment Variables)

| Key | Contoh nilai | Keterangan |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `https://api.flowdesk.flowjob.id` | Host backend FlowDesk. Tanpa ini, default `http://localhost:8000` (dev). |

> `NEXT_PUBLIC_*` ter-expose ke browser — itu memang disengaja untuk URL API publik. **Jangan** menaruh secret di sini.

### Di Backend FlowDesk (VPS, bukan Vercel)

Backend punya env keys sendiri (lihat dokumentasi FlowDesk; AGENTS.md menyebut "12 ENV keys" yang LOCKED). Termasuk koneksi:

- Database (Postgres/Timescale)
- Redis
- Discord auth (client id/secret, role DESK, guild id)
- Konfigurasi feed (live feed disarm by default — `LIVE_FEED_ARMED` absen)

> Jangan pernah commit secret. Set langsung di VPS (env file dengan permission ketat atau secret manager).

---

## 11. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Konflik React 18 vs 19 | Build gagal / runtime error | Turunkan komponen FlowDesk ke React 18; verifikasi via `typecheck` + `build` |
| WebSocket terblok di production | Terminal tidak update live | Pastikan backend serve `wss://` valid + SSL; uji koneksi dari browser, bukan dari Vercel function |
| Backend mati / VPS down | Terminal kosong | Fallback ke replay/static JSON di `public/data`; tambahkan health check & auto-restart (systemd) |
| Dua sistem auth tidak sinkron | User DESK tertolak di API | Samakan sumber kebenaran (Discord role DESK); verifikasi mekanisme auth backend dulu |
| Dependency berat (three/regl) memperlambat build FlowJob | Build time naik, bundle besar | Lazy-load Arc; `dynamic(() => import(...), { ssr: false })`; atau skip Arc di fase awal |
| Override CSS global merusak halaman lain FlowJob | UI website utama rusak | Batasi styling terminal ke scope `/dashboard/app` saja |
| Bocornya secret saat porting | Risiko keamanan | Hanya pindah kode FE; jangan pindah file `.env`; cek `git diff` sebelum commit |

---

## 12. Checklist Pre-Deploy

**Backend (VPS):**

- [ ] VPS aktif, Python 3.11+, Redis, Postgres/Timescale terpasang
- [ ] `services/engine` & `services/api` ter-install editable
- [ ] Worker + API jalan via systemd/docker-compose (auto-restart)
- [ ] Domain + SSL aktif (`https://` + `wss://` valid)
- [ ] Env backend di-set di VPS (bukan di repo), live feed disarm
- [ ] Health check endpoint merespons

**Frontend (FlowJob):**

- [ ] Branch `feat/integrate-flowdesk-terminal` dibuat
- [ ] Dependency terminal ter-install (`lightweight-charts`, opsional `three`/`regl`)
- [ ] Komponen fog/flux(/arc) + `lib/terminal` ter-port, import path benar
- [ ] `app/dashboard/app/page.tsx` render terminal untuk DESK, `AppLockedClient` untuk non-DESK
- [ ] Layout full-width terminal dibuat
- [ ] `NEXT_PUBLIC_API_BASE_URL` di-set di Vercel
- [ ] `npm run typecheck && npm run lint && npm run test && npm run build` semua hijau
- [ ] Uji manual: user DESK lihat terminal, non-DESK lihat locked
- [ ] Uji WebSocket live + fallback replay/static
- [ ] (Opsional) Docs terminal dibuat di `/docs/terminal`

**Verifikasi akhir:**

- [ ] Tidak ada secret ter-commit (`git diff` bersih)
- [ ] Preview Vercel OK sebelum merge ke `master`
- [ ] Setelah deploy: `https://www.flowjob.id/dashboard/app` berfungsi untuk user DESK

---

> **Langkah berikutnya yang disarankan:** mulai dari Fase 1 (siapkan VPS + backend) **paralel** dengan Fase 2–3 (port komponen di branch lokal). Backend dan frontend bisa dikerjakan bersamaan karena keduanya hanya terhubung lewat `NEXT_PUBLIC_API_BASE_URL`.
