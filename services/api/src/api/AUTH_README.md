# FlowDesk API — Discord OAuth2 + Session (Release 1.5, Fase 3)

Dokumen ini menjelaskan implementasi autentikasi Discord OAuth2 dan gerbang akses
DESK (`require_desk()`) untuk `services/api`, sesuai **PRD #6** dan acceptance
**PRD #12 / T-09**. Semua kode & identifier dalam bahasa Inggris; penjelasan
dalam bahasa Indonesia.

> **Ringkas kontrak:** turquoise/crimson/#000 LOCKED, 12 env keys LOCKED (tidak
> ditambah), Black-76, /ES ×50 /NQ ×20, RTH ET. Task ini murni server-side auth
> dan tidak menyentuh kontrak visual/pricing.

---

## 1. File dalam patch ini (patch murni, root `flowdesk/`)

```
flowdesk/services/api/
├─ pyproject.toml                      # httpx 0.27.0 dipromosikan dev -> runtime
├─ src/api/
│  ├─ auth_session.py                  # BARU: crypto cookie + algoritma check_access (tanpa FastAPI)
│  ├─ discord_client.py                # BARU: interface DiscordClient + HttpxDiscordClient + FakeDiscordClient
│  ├─ auth.py                          # BARU: route login/callback/logout (FastAPI)
│  ├─ security.py                      # DIUBAH: require_desk() terisi penuh (grace-aware)
│  ├─ models.py                        # DIUBAH: MeResponse + is_member + grace_until
│  ├─ main.py                          # DIUBAH: wire auth router + /api/me + /api/me/recheck
│  └─ AUTH_README.md                   # dokumen ini
└─ tests/test_auth.py                  # BARU: core + HTTP tests, semua pakai FakeDiscordClient
```

---

## 2. Alur OAuth2 (persis seperti PRD #6 §3)

### `GET /api/auth/discord/login` (alias `GET /api/auth/login`)
1. Buat **state** acak (CSRF), tandatangani (HMAC-SHA256 + `SESSION_SECRET`) lalu
   simpan sebagai cookie `flowdesk_oauth_state` (HttpOnly, Secure, SameSite=Lax,
   `Max-Age=600`).
2. Redirect **307** ke Discord authorize:
   `https://discord.com/oauth2/authorize?response_type=code&client_id=...&scope=identify%20guilds.members.read&state=...&redirect_uri=...`.
   Scope **persis**: `identify guilds.members.read`.

### `GET /api/auth/discord/callback` (alias `GET /api/auth/callback`)
1. Verifikasi `state` query == cookie `flowdesk_oauth_state` **dan** tanda tangannya
   valid & belum kedaluwarsa → jika tidak: `400 BAD_REQUEST`.
2. `exchange_code(code)` → OAuth `access_token`.
3. `fetch_user(access_token)` → `discord_id`.
4. `fetch_member(access_token, DISCORD_GUILD_ID)` → objek member guild.
   - `is_member = (member call ≠ 404)`.
   - `has_desk = DISCORD_DESK_ROLE_ID in member.roles`.
5. Mint **Session** (lihat §4), serialisasi + tandatangani → set cookie
   `flowdesk_session`. Hapus cookie state. Redirect **307** ke origin frontend
   (CORS origin pertama) atau `/`.
6. Error: `DiscordAuthError` (4xx) → 401; `DiscordUnavailable` (network/5xx) →
   500 `INTERNAL` (“Discord temporarily unavailable”).

### `POST /api/auth/logout`
Hapus cookie `flowdesk_session` (set value kosong + `Max-Age=0`). **204**.

---

## 3. Gerbang `require_desk()` (T-09)

`require_desk(session)` di `security.py`:
- **tanpa session** → `401 UNAUTHENTICATED`.
- **session tanpa DESK dan tanpa grace aktif** → `403 FORBIDDEN`.
- **has_desk == True** → ALLOW.
- **grace aktif** (`grace_until` ada & `now < grace_until`) → ALLOW.

Semua endpoint data — `GET /api/snapshot`, `/api/snapshot/latest`,
`/api/replay/sessions`, `/api/replay`, dan `WS /ws` — memakai dependency
`require_desk_dep`, sehingga **non-DESK diblokir di semua endpoint data**.
`/api/me` & `/api/me/recheck` hanya butuh session (bukan DESK).

---

## 4. Model Session & `check_access`

`Session` (disimpan di dalam cookie tertandatangani):

| field          | tipe            | catatan                                                       |
|----------------|-----------------|---------------------------------------------------------------|
| `discord_id`   | str             | dari `/users/@me`                                             |
| `has_desk`     | bool            | role DESK ada saat pengecekan terakhir                        |
| `is_member`    | bool            | masih anggota guild (member call ≠ 404)                       |
| `last_checked` | str ISO `...Z`  | timestamp pengecekan Discord terakhir                         |
| `grace_until`  | str ISO `...Z`  | akhir grace (EOD ET) saat role dicabut; `None` jika tak ada   |
| `access_token` | str             | OAuth token Discord, **internal** (lihat §6), tak diekspos    |

`check_access(session, *, now, member, desk_role_id, recheck_interval_s=86400, force=False)`
mengembalikan `AccessResult{session, decision, changed}`.

**Aturan re-check (PRD #6 §5/§6):** dilakukan saat **login**, dan **harian (>24h)**
sejak `last_checked`, atau dipaksa via `/api/me/recheck`. Jika belum jatuh tempo
(dan tidak `force`), cache dipertahankan tanpa memanggil Discord.

**Decision enum:** `ALLOW`, `ALLOW_GRACE`, `DENY_NOT_MEMBER`, `DENY_NO_DESK`.

---

## 5. Komputasi grace dalam ET (didokumentasikan eksplisit)

Ketika re-check menemukan role DESK **dicabut** (sebelumnya `has_desk=True`,
sekarang member ada tapi role hilang), akses tidak langsung dicabut. Sebagai
gantinya:

```
grace_until = end_of_day_et(now)
```

`end_of_day_et(now)` dihitung sebagai **tengah malam ET (America/New_York)
berikutnya**, dikembalikan sebagai instan UTC yang aware:

1. Konversi `now` (UTC) ke zona `America/New_York` (otomatis EST/EDT via `zoneinfo`).
2. Ambil tanggal ET hari itu, tambah 1 hari, set jam ke `00:00:00` ET.
3. Konversi balik ke UTC → itulah `grace_until`.

Contoh: `now = 2026-06-10 18:00 UTC` = `14:00 ET (EDT)` →
`grace_until = 2026-06-11 00:00 ET = 2026-06-11 04:00 UTC`.

Selama `now < grace_until`, `require_desk` mengizinkan akses (`ALLOW_GRACE`,
frontend menampilkan banner). Setelah lewat → `403`.

> **Divergensi vs pseudocode PRD #6 §5:** pseudocode literal akan memberi grace
> ke siapa pun tanpa DESK setelah 24 jam. Kami **hanya memulai grace pada
> pencabutan asli** (transisi `was_desk=True → has_desk=False`), sesuai tabel
> error §7 (user yang memang tak pernah DESK → `403 NO_DESK` langsung, tanpa
> grace). Lihat `test_check_access_no_desk_denied` vs
> `test_revocation_starts_grace_then_expires`.

---

## 6. Cookie & keamanan

- **`flowdesk_session`**: HttpOnly, Secure, SameSite=Lax, `Path=/`,
  `Max-Age=604800` (7 hari), ditandatangani HMAC-SHA256 dengan `SESSION_SECRET`.
- **`flowdesk_oauth_state`**: flag sama, `Max-Age=600`.
- Format token: `base64url(json_payload) + "." + base64url(hmac_sha256)`; field
  `exp` (epoch) divalidasi; verifikasi tanda tangan **constant-time**.
- Tanda tangan rusak / secret salah / kedaluwarsa → `deserialize_session` →
  `None` (dianggap tidak login).
- **Secrets hanya dari env** (`SESSION_SECRET`, `DISCORD_*`). Tidak ada nilai
  rahasia yang di-hardcode.

---

## 7. `/api/me` & `/api/me/recheck`

- `GET /api/me` → `401` jika tak ada session; jika ada, jalankan re-check **harian
  (non-forced)**: bila jatuh tempo, panggil `fetch_member` lalu `check_access`.
  Jika session berubah, cookie baru ditandatangani & di-set. Body:
  `{discord_id, has_desk, is_member, last_checked, grace_until}`.
- `POST /api/me/recheck` → sama, tapi **memaksa** pemanggilan Discord segera
  (`force=True`).
- Bila Discord tidak tersedia saat re-check (`DiscordUnavailable`/token invalid
  `DiscordAuthError`), cache **dipertahankan** (tidak mengunci tiba-tiba), sesuai
  PRD #6 §5 (frontend menampilkan banner “verification pending”).

---

## 8. Verifikasi manual (sandbox / lokal)

Sandbox tidak punya internet/instalasi, jadi tidak ada panggilan jaringan dan
FastAPI/pytest mungkin belum terpasang. Lapisan **core** (`auth_session`,
`discord_client`, `security`) bisa diimpor & diuji tanpa FastAPI.

Langkah lokal (env lengkap):

```bash
cd services/api
python -m pip install -e .[dev]        # menarik fastapi, httpx, pytest, dst.
export SESSION_SECRET=dev-secret
export DISCORD_CLIENT_ID=... DISCORD_CLIENT_SECRET=...
export DISCORD_GUILD_ID=... DISCORD_DESK_ROLE_ID=...
export CORS_ORIGINS=http://localhost:3000
pytest tests/test_auth.py -q
```

Checklist verifikasi:
- [ ] `test_signed_cookie_roundtrip_and_tamper` — round-trip + tamper/secret/exp.
- [ ] `test_cookie_flags_exact` — HttpOnly/Secure/SameSite=lax/Max-Age=604800/Path=/.
- [ ] `test_end_of_day_et_is_next_et_midnight` — grace tepat di tengah malam ET.
- [ ] `test_check_access_happy_desk` / `_no_desk_denied` / `_not_member_denied`.
- [ ] `test_revocation_starts_grace_then_expires` — grace mulai saat dicabut, habis EOD ET.
- [ ] `test_recheck_not_due_keeps_cache` / `test_discord_unavailable_keeps_cache`.
- [ ] `test_http_callback_happy_desk` — callback DESK → session + /api/me 200.
- [ ] `test_http_callback_no_desk_blocked_at_data_endpoints` — 403 di /snapshot & /replay.
- [ ] `test_http_unauthenticated_is_401` — 401 tanpa session.
- [ ] `test_http_recheck_forces_discord_call` — recheck memaksa fetch_member + grace.
- [ ] `test_http_logout_clears_cookie`.
- [ ] `test_http_cookie_flags_secure_when_not_insecure`.

---

## 9. Integration Notes (untuk agent VSCode / Fase stitching)

- **Overlay**: `unzip -o flowdesk-1.5-auth.zip` dari root repo. Root arsip
  `flowdesk/`, jadi file jatuh tepat ke `services/api/...`.
- **Mengganti** versi 1.2–1.4 dari: `security.py`, `models.py`, `main.py`,
  `pyproject.toml`. File worker/session/ws/repo/state **tidak** disentuh.
- **`require_desk()` seam** dari Fase 2 kini terisi. Endpoint data yang sudah ada
  (snapshot/replay/ws) otomatis ter-gate tanpa perubahan signature.
- **`app.state.discord_client`**: default = client nyata (`client_from_env()`,
  butuh `httpx` + `DISCORD_CLIENT_ID/SECRET`). Test meng-override dengan
  `FakeDiscordClient`. Frontend memakai cookie (`credentials: 'include'`); CORS
  sudah `allow_credentials=True`.
- **WS auth (PRD #6 §4)** via `?token=` **belum** diimplementasikan di rilis ini
  (ditunda; `/ws` saat ini memakai gate cookie `require_desk_dep`). Akan disusul.
- **Onboarding tour (PRD #6 §8)** ditunda (frontend).

---

## 10. Assumptions (pilihan paling sederhana, dicatat)

1. **`session.py` vs `auth_session.py`**: TASK meminta `session.py`, tetapi
   `src/api/session.py` **sudah dipakai** sebagai state machine sesi worker (PRD
   #9, rilis 1.4). Untuk menghindari menimpa file itu, modul cookie diberi nama
   **`auth_session.py`**. (Divergensi nama, fungsional identik.)
2. **Tanpa `itsdangerous`** (tidak terpasang & tanpa jaringan) → cookie
   ditandatangani dengan **stdlib `hmac`/`hashlib`/`base64`** (HMAC-SHA256). Tidak
   menambah dependency.
3. **12 env keys LOCKED** → tidak menambah `DISCORD_BOT_TOKEN`. Re-check harian
   memerlukan token user, jadi **OAuth `access_token` disimpan di dalam cookie
   session yang ditandatangani** (HttpOnly, tidak diekspos via `/api/me`). Masa
   token Discord (~7 hari) ≈ umur cookie; jika token kedaluwarsa saat re-check →
   diperlakukan sebagai “Discord unavailable” (cache dipertahankan, user re-login
   saat cookie habis).
4. **Kedua path didaftarkan**: nama kanonik PRD `#6 §3`
   (`/api/auth/discord/login`, `/api/auth/discord/callback`) **dan** alias TASK
   (`/api/auth/login`, `/api/auth/callback`).
5. **Dev toggles non-LOCKED** (opsional, bukan env key wajib baru):
   `PUBLIC_BASE_URL` (override redirect_uri di belakang proxy) dan
   `COOKIE_INSECURE` (matikan flag Secure untuk dev http lokal/test). Keduanya
   opsional; produksi memakai default aman.
6. **Redirect pasca-login** → CORS origin pertama, atau `/` bila kosong.

---

## 11. TODO-FROM-OWNER

- [ ] **Production domain / `PUBLIC_BASE_URL`** untuk `redirect_uri` Discord
      (mis. `https://app.flowdesk.xyz`) + daftarkan **Redirect URI** yang sama di
      Discord Developer Portal.
- [ ] **`DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_GUILD_ID`,
      `DISCORD_DESK_ROLE_ID`** asli (saat ini placeholder di `.env.example`).
- [ ] **`SESSION_SECRET`** acak kuat (≥32 byte) untuk produksi.
- [ ] Konfirmasi kebijakan grace (akhir hari ET) sesuai harapan bisnis DESK.
