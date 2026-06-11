# FlowDesk — FE Auth Contract (`/api/me`) — Release 1.6

Kontrak antara backend `services/api` dan frontend (`@flowdesk/web`, Fase 4–5)
untuk merender pengalaman **denied / preview-blur** dan **onboarding** sesuai
**PRD #6**. Frontend merender SEPENUHNYA dari `GET /api/me` — endpoint ini
**publik** (anonim → `200`, bukan `401`). Gerbang keras `401/403` hanya di
endpoint data.

> Kode & identifier = English. Copy yang ditampilkan ke user = Indonesia.

---

## 1. `GET /api/me` (PUBLIC)

Selalu `200 OK` (anonim sekalipun). Tidak meng-cache (FE boleh polling / panggil
saat mount + setelah login + setelah recheck).

### Bentuk respons (semua state)

```jsonc
{
  "access_state": "ANON" | "NO_DESK" | "DESK",
  "discord_id": string | null,        // null saat ANON
  "has_desk": boolean,                 // role DESK ada saat cek terakhir
  "is_member": boolean,                // masih anggota guild (bedakan copy not-member)
  "last_checked": string | null,       // ISO-8601 ...Z, waktu cek Discord terakhir
  "grace_until": string | null,        // ISO-8601 ...Z akhir grace (EOD ET) | null
  "cta": {
    "join_url": string,                // link join Discord (env DISCORD_JOIN_URL)
    "buy_url": "https://flowjob.id",   // halaman beli DESK (locked)
    "recheck_supported": true          // FE boleh tampilkan tombol "cek ulang"
  }
}
```

### Penentuan `access_state`

| Kondisi session                              | `access_state` |
|----------------------------------------------|----------------|
| tidak ada session                            | `ANON`         |
| `has_desk == true`                           | `DESK`         |
| dalam grace pencabutan (`now < grace_until`) | `DESK` + banner|
| selain itu (termasuk bukan anggota)          | `NO_DESK`      |

---

## 2. Perilaku FE per `access_state`

### `ANON` → tampilkan **login CTA**
- Tampilkan landing + tombol **“Masuk dengan Discord”** → arahkan ke
  `GET /api/auth/login` (browser redirect, bukan fetch).
- Tidak ada data terminal yang ditampilkan.

### `NO_DESK` → **preview blur** + join/buy + tombol cek ulang
- Render shell terminal dengan **blur/teaser** (data tidak dimuat / placeholder).
- Tampilkan kartu CTA:
  - Jika `is_member == false`: utamakan tombol **Join** (`cta.join_url`).
  - Tombol **Beli DESK** (`cta.buy_url` = `https://flowjob.id`).
  - Jika `cta.recheck_supported`: tombol **“Saya sudah punya DESK — cek ulang”**
    → `POST /api/me/recheck` (credentials: include) lalu render ulang dari
    respons.

### `DESK` → **full app**
- Render terminal penuh; muat snapshot/replay/WS.
- Jika `grace_until != null`: tampilkan **banner grace** (lihat §3 state #4).

---

## 3. Enam error/akses-state dari PRD #6 §7 (HTTP + copy ID)

FE mengambil keputusan UX dari `/api/me` (`access_state`, `is_member`,
`grace_until`). Kolom **HTTP (data endpoint)** menunjukkan kode yang dikembalikan
endpoint **data** (snapshot/replay/ws) pada kondisi tsb — berguna untuk
penanganan error fetch.

| # | Kondisi | `/api/me` | HTTP (data endpoint) | `code` | Copy FE (Indonesia) |
|---|---------|-----------|----------------------|--------|---------------------|
| 1 | Belum login | `200` `ANON` | `401` | `UNAUTHENTICATED` | **“Masuk dulu untuk mengakses FlowDesk.”** Tombol: “Masuk dengan Discord”. |
| 2 | Login, **bukan anggota** guild | `200` `NO_DESK` (`is_member=false`) | `403` | `FORBIDDEN`* | **“Kamu belum bergabung di server Discord FlowDesk. Gabung dulu untuk verifikasi akses DESK.”** Tombol: “Join Discord”, “Beli DESK”. |
| 3 | Anggota, **tanpa role DESK** | `200` `NO_DESK` (`is_member=true`) | `403` | `FORBIDDEN`* | **“Akun kamu belum punya akses DESK.”** Tombol: “Beli DESK”, “Saya sudah punya DESK — cek ulang”. |
| 4 | Role dicabut, **masih dalam grace** (hari ini ET) | `200` `DESK` (`grace_until` terisi) | `200` (tetap jalan) | — | Banner: **“Akses DESK kamu dicabut. Kamu masih bisa pakai sampai akhir hari ini (waktu New York). Perpanjang di flowjob.id.”** |
| 5 | Grace **habis** (lewat akhir hari ET) | `200` `NO_DESK` | `403` | `FORBIDDEN`* | **“Masa tenggang akses DESK kamu sudah berakhir. Perpanjang untuk lanjut.”** Tombol: “Beli DESK”, “Cek ulang”. |
| 6 | **Discord sedang down** saat re-check | `200` (state cache, mis. `DESK`) | sesuai cache (mis. `200`) | — | Banner: **“Verifikasi Discord tertunda. Kami pakai status terakhir kamu untuk sementara.”** Tidak mengunci akses. |

\* Catatan implementasi: endpoint data mengembalikan `403` generik dengan
`code = "FORBIDDEN"` untuk state #2/#3/#5. Pembeda **not-member vs no-desk**
disuguhkan lewat `/api/me` (`access_state` + `is_member`), yang memang menjadi
sumber kebenaran UX bagi FE. (Lihat Divergensi di README auth 1.5.)

Bentuk body error data endpoint:

```json
{ "error": "DESK role required", "code": "FORBIDDEN" }
```

---

## 4. `POST /api/me/recheck`

- Memaksa re-check Discord segera, lalu mengembalikan **bentuk `MeResponse`
  yang sama** seperti `/api/me`.
- **Butuh session**: anonim → `401 UNAUTHENTICATED` (tombol cek ulang hanya
  muncul untuk `NO_DESK`/`DESK`, yang pasti punya session).
- Dipakai tombol **“Saya sudah punya DESK — cek ulang”**.
- `credentials: "include"` wajib (cookie session).

---

## 5. Catatan integrasi FE

- Semua request memakai `credentials: "include"` (cookie `flowdesk_session`,
  HttpOnly). CORS backend sudah `allow_credentials=true`; set `CORS_ORIGINS`
  ke origin FE.
- Login & logout adalah **navigasi browser** (`GET /api/auth/login`,
  `POST /api/auth/logout`), bukan XHR (ada redirect Discord).
- `grace_until` & `last_checked` ISO-8601 UTC (`...Z`); render relatif ke zona
  user, tapi teks grace mengacu **akhir hari ET** (lihat AUTH_README §5).
- Mock untuk dev tanpa Discord: lihat `mocks/` (§6).

---

## 6. Mock untuk pengembangan FE (tanpa Discord live)

Rekaman JSON per-state ada di `services/api/mocks/`:

- `me_anon.json`     — `access_state = ANON`
- `me_no_desk.json`  — `access_state = NO_DESK` (member, tanpa DESK)
- `me_desk.json`     — `access_state = DESK`
- `me_grace.json`    — `access_state = DESK` + `grace_until` (state banner #4)

Server mock kecil tanpa dependensi (stdlib `http.server`):

```bash
# Pilih state via env (default DESK). Sajikan GET/POST /api/me(+/recheck).
MOCK_ACCESS_STATE=NO_DESK python services/api/mocks/mock_me_server.py 8787
# FE: NEXT_PUBLIC_API_BASE=http://localhost:8787
```

Server mengirim header CORS (`Access-Control-Allow-Origin` echo + credentials)
sehingga FE di `http://localhost:3000` bisa memanggil dengan cookie. `POST
/api/me/recheck` mengembalikan state yang sama (atau `MOCK_RECHECK_STATE` bila
diset) untuk mensimulasikan hasil cek ulang.

---

## 7. Acceptance (PRD #12 T-09 + kontrak FE 1.6)

- [x] `access_state` mencakup `ANON` / `NO_DESK` / `DESK`.
- [x] `cta{join_url, buy_url:"https://flowjob.id", recheck_supported:true}`.
- [x] 6 error state PRD #6 terdokumentasi + kode HTTP + copy Indonesia.
- [x] Mock fixtures per state untuk FE (recorded JSON + server stdlib).
- [x] `tests/test_me_contract.py` memvalidasi bentuk `/api/me` tiap state.
- [x] Non-DESK diblokir di semua endpoint data (401/403); secrets hanya dari env.
