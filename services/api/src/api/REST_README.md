# FlowDesk — REST API (Fase 3 prep)

Rilis **1.2** (patch). REST contract PRD #8 §6 + PRD #10 §2 di `services/api`,
lengkap dengan seam gating DESK (diisi penuh di Fase 3).

> Patch timpa. Root zip = `flowdesk/` → `unzip -o flowdesk-1.2-rest-api.zip`.

## File dalam patch ini

```
flowdesk/services/api/
├─ pyproject.toml              # DIUBAH: + flowdesk-engine (kontrak), + httpx (dev). asyncpg/redis tetap.
├─ src/api/
│  ├─ main.py                  # DIUBAH: app factory + semua route + CORS + handler error
│  ├─ errors.py                # ApiError + {error, code} (pure, tanpa FastAPI)
│  ├─ security.py              # Session + require_session/require_desk (SEAM Fase 3, pure)
│  ├─ models.py                # response models; re-export Snapshot dari engine.schema
│  └─ REST_README.md           # dokumen ini
└─ tests/
   └─ test_rest.py             # TestClient: 200/401/403/404/422 + gating T-09
```

## Endpoint (path persis)

| Method & Path | Gating | Sumber | Catatan |
| --- | --- | --- | --- |
| `GET /api/health` | — | — | `{status, feed_mode, version}` |
| `GET /api/snapshot?instrument=ES\|NQ` | **DESK** | Redis (`state.get_now`) | snapshot terbaru; 404 bila kosong |
| `GET /api/snapshot/latest?instrument=` | **DESK** | Redis | **alias PRD #8 §6** (lihat divergensi) |
| `GET /api/replay/sessions?instrument=` | **DESK** | Timescale (`repo.list_sessions`) | `[{session_date, minute_count}]` |
| `GET /api/replay?instrument&date&from_minute&to_minute` | **DESK** | Timescale (`repo.get_range`) | `{snapshots: Snapshot[]}` |
| `GET /api/me` | sesi | cookie | `{discord_id, has_desk, last_checked}`; 401 bila tak ada sesi |
| `POST /api/me/recheck` | sesi | cookie | stub Fase 3; 401 bila tak ada sesi |

## Gating seam (PRD #8 AC-A5, T-09)

`security.py` = **SEAM auth**. Saat ini hanya membaca + memvalidasi *bentuk* sesi
dari cookie `flowdesk_session` (plain JSON), BELUM verifikasi Discord asli.

- Tanpa sesi → **401** `UNAUTHENTICATED`
- Sesi tanpa DESK → **403** `FORBIDDEN`  *(T-09)*
- Sesi dengan DESK → lolos

Dependency: `require_desk_dep` (data endpoints) & `require_session_dep` (`/api/me*`).
Fungsi murni `require_session()` / `require_desk()` bisa di-unit-test tanpa FastAPI.

> **Fase 3 mengganti** `parse_session_cookie` dengan verifikasi signed-cookie
> (`SESSION_SECRET`/itsdangerous) + OAuth2 Discord + cek membership guild & role
> DESK. Signature `require_session`/`require_desk` dan nama cookie TIDAK berubah,
> jadi route tak perlu disentuh.

## Divergensi yang di-flag (bukan locked contract)

1. **Path snapshot.** TASK menulis `GET /api/snapshot`; PRD #8 §6 = `GET /api/snapshot/latest`.
   → saya daftarkan **keduanya** (primary `/api/snapshot` + alias `/api/snapshot/latest`).
2. **`/api/health`** bentuk TASK `{status, feed_mode, version}`; PRD #8 §6 `{status, engine_heartbeat_age_s}`.
   → ikut TASK; `engine_heartbeat_age_s` ditambah saat engine worker ada.
3. **`/api/me`** bentuk TASK `{discord_id, has_desk, last_checked}`; PRD #8 §6 menambah
   `is_member` & `grace_until`. → ikut TASK; field PRD ditambah di Fase 3.
4. **Kontrak Snapshot** = `engine/schema.py` (objek Python kanonik: `axis.step`,
   `regime.sign` int `-1|0|1`, `levels` berisi list angka) — **bukan** contoh JSON
   PRD #8 §3 (`strike_step`, `sign:"negative"`, levels objek). Engine schema = SOT.

## Error & CORS

- Semua error → `{ "error": <pesan>, "code": <CODE> }`. Kode: `UNAUTHENTICATED` (401),
  `FORBIDDEN` (403), `NOT_FOUND` (404), `VALIDATION` (422), `SERVICE_UNAVAILABLE` (503).
- CORS dari env `CORS_ORIGINS` (comma-separated) via `CORSMiddleware`.
- Instrument selain `ES|NQ` → 422 `VALIDATION` (lewat `Literal` engine).

## Setup & run

```bash
cd services/api
pip install -e "../engine"      # sediakan kontrak flowdesk-engine (engine.schema)
pip install -e ".[dev]"         # fastapi, httpx, pytest, dll
pytest tests/test_rest.py -q
uvicorn api.main:app --reload   # http://localhost:8000/api/health
```

Backend (Redis/Timescale) di-inject lewat dependency `get_state_store`/`get_repo`;
di test di-override dengan fake; di runtime dibuat di app lifespan dari `REDIS_URL`
/ `TIMESCALE_DSN` bila ada. Tanpa env, endpoint data mengembalikan 503
`SERVICE_UNAVAILABLE` (bukan crash).

## Manual verification checklist

- [ ] `pytest tests/test_rest.py -q` → semua PASS.
- [ ] `GET /api/health` → 200 `{status:"ok", feed_mode, version}`.
- [ ] `GET /api/snapshot?instrument=ES` tanpa cookie → 401 `UNAUTHENTICATED`.
- [ ] dengan sesi non-DESK → 403 `FORBIDDEN` (T-09).
- [ ] dengan sesi DESK → 200, body lolos validasi Snapshot.
- [ ] state kosong → 404 `NOT_FOUND`; instrument `XX` → 422 `VALIDATION`.
- [ ] `GET /api/replay/sessions` & `GET /api/replay` ter-gate DESK & balas bentuk PRD #10.
- [ ] `GET /api/me` tanpa sesi → 401; dengan sesi → 200.

## Integration Notes (untuk dokumen jahit akhir Fase 6)

- **Dependensi**: `api` meng-import `engine.schema` (kontrak Snapshot) → install
  `services/engine` lebih dulu. Reads: Redis (live) via `api.state.StateStore`,
  Timescale (replay) via `db.repo.SnapshotRepository`.
- **Wiring**: app lifespan membuat `state_store` (dari `REDIS_URL`) & `repo`
  (dari `TIMESCALE_DSN`); route ambil via `Depends(get_state_store/get_repo)`.
- **Auth seam**: Fase 3 mengisi `security.parse_session_cookie` + route
  `/api/auth/discord/login|callback` (PRD #6) dan melengkapi `/api/me`,
  `/api/me/recheck` (cek role instan).
- **Belum dibuat (sengaja, di luar TASK)**: `GET /api/instruments` (PRD #8 §6) &
  WebSocket `/ws` (PRD #8 §7) — tugas terpisah berikutnya.

## Assumptions

- Skema cookie sesi Fase-1 = JSON `{discord_id, has_desk, is_member?, last_checked?}`
  (placeholder; Fase 3 menandatangani & memverifikasi via Discord).
- `/api/me` boleh diakses sesi non-DESK (hanya butuh login); hanya endpoint data
  yang butuh DESK.
- `flowdesk-engine==0.1.0` di-resolve sebagai editable workspace dep.
- Pin `httpx==0.27.0` (dev, untuk TestClient) kompatibel `python==3.11.*`;
  tak bisa diverifikasi online → TODO-FROM-OWNER.

## TODO-FROM-OWNER

- Konfirmasi path final snapshot: `/api/snapshot` (TASK) vs `/api/snapshot/latest`
  (PRD #8). Saat ini keduanya aktif.
- Konfirmasi pin `httpx==0.27.0`; isi `CORS_ORIGINS` produksi di `.env`.
