# FlowDesk — WebSocket `/ws` (live snapshot stream)

Rilis **1.3** (patch). WebSocket endpoint `services/api` per PRD #8 §7, streaming
snapshot terbaru saat connect dan setiap menit baru lewat Redis pub/sub.

> Patch timpa. Root zip = `flowdesk/` → `unzip -o flowdesk-1.3-websocket.zip`.

## File dalam patch ini

```
flowdesk/services/api/
├─ src/api/
│  ├─ ws.py            # BARU: endpoint /ws + ConnectionManager (fan-out pub/sub)
│  ├─ main.py          # DIUBAH: register_ws_routes(app) di create_app()
│  └─ WS_README.md     # dokumen ini
└─ tests/
   └─ test_ws.py        # BARU: TestClient WS (mocked pub/sub)
```

*(pyproject tidak berubah: `uvicorn[standard]==0.30.6` sudah membawa `websockets`.)*

## Endpoint

`GET /ws?instrument=ES|NQ` (WebSocket upgrade). DESK-gated.

## Protokol (server → client) — semua frame JSON text

| Frame | Kapan |
| --- | --- |
| `{"type":"snapshot","data":<Snapshot>}` | sekali tepat setelah connect (current state dari Redis, jika ada) |
| `{"type":"snapshot","data":<Snapshot>}` | setiap engine update di channel `flowdesk:updates:{instrument}` |
| `{"type":"ping"}` | tiap **15s** (heartbeat) |

## Protokol (client → server)

| Frame | Arti |
| --- | --- |
| `{"type":"pong"}` | balasan ping. Semua frame client diterima & diabaikan; loop receive ada untuk mengamati pong & mendeteksi disconnect. |

`<Snapshot>` = kontrak kanonik `engine/schema.py` (`schema_version:1`), sama persis
dengan yang dikembalikan REST `/api/snapshot`.

## Kontrak feed-gap / STALE (WAJIB untuk FE)

Saat feed upstream macet, engine TETAP mengirim snapshot tapi dengan
`state == "STALE"` dan `stale == true`. Layer WS **meneruskan apa adanya**
(tidak ada frame sintetis, tidak ada penyaringan).

- FE **menahan / menggambar ulang frame baik terakhir** dan menampilkan badge STALE
  sampai datang frame dengan `stale == false`.
- Tidak ada perubahan struktur frame: tetap `{"type":"snapshot", ...}`.

## Close codes

| Code | Arti |
| --- | --- |
| `4401` | tidak ada sesi (unauthenticated) |
| `4403` | ada sesi tapi tanpa role DESK (T-09) |
| `4400` | instrument salah/kosong (ekstensi terdokumentasi; di luar TASK) |
| `1011` | live state store belum terkonfigurasi (service unavailable) |

Gating dicek **sebelum** `accept()`, jadi koneksi non-DESK ditolak saat handshake.

## Connection manager

`ConnectionManager` memegang **tepat satu** `store.subscribe(instrument)` per
instrument dan mem-fan-out tiap snapshot ke semua antrian klien — N tab browser
berbagi satu subscription `flowdesk:updates:{instrument}`. Hub berhenti otomatis
saat klien terakhir untuk instrument itu putus. Manager hanya bergantung pada
`asyncio` + API `subscribe()` store, sehingga bisa diuji tanpa web stack.

## Gating seam (sama dengan REST)

Memakai `api.security` yang sama (`parse_session_cookie`). Fase 3 mengganti
decoder cookie dengan signed-cookie + verifikasi role Discord; `ws.py` tak perlu
disentuh. (PRD #8 §7 versi awal pakai `?token=` + pesan subscribe/unsubscribe —
lihat Divergensi.)

## Divergensi yang di-flag (bukan locked contract)

1. **Auth transport.** PRD #8 §7 menyebut `wss://api.flowdesk/ws?token=`; TASK +
   layer REST memakai **cookie sesi** (`flowdesk_session`). → ikut cookie (konsisten
   dengan gating REST 1.2). Dukungan `?token=` bisa ditambah di Fase 3 bila perlu.
2. **Subscribe model.** PRD §7 punya pesan client `subscribe`/`unsubscribe` multi-
   instrument; TASK = satu instrument via `?instrument=`. → ikut TASK (auto-subscribe
   ke instrument query). Multiplex bisa ditambah belakangan.
3. **Heartbeat.** PRD §7 `{type:"heartbeat"}` tiap 30s; TASK `{type:"ping"}` tiap 15s
   + `{type:"pong"}` dari client. → ikut TASK.
4. **Frame types.** PRD §7 punya `status`/`error` juga; TASK hanya `snapshot` + `ping`.
   → ikut TASK; `status`/`error`/reconnect-backoff ditambah saat dibutuhkan.

## Setup & run

```bash
cd services/api
pip install -e "../engine"      # kontrak flowdesk-engine (engine.schema)
pip install -e ".[dev]"         # fastapi, websockets, httpx, pytest, dll
pytest tests/test_ws.py -q
uvicorn api.main:app --reload   # ws://localhost:8000/ws?instrument=ES
```

## Manual verification checklist

- [ ] `pytest tests/test_ws.py -q` → semua PASS.
- [ ] Connect tanpa cookie → close **4401**.
- [ ] Connect sesi non-DESK → close **4403** (T-09).
- [ ] Connect `?instrument=XX` (sesi DESK) → close **4400**.
- [ ] Connect sesi DESK → frame pertama `{type:"snapshot"}` = current state.
- [ ] Publish ke `flowdesk:updates:ES` → frame `{type:"snapshot"}` baru terdorong.
- [ ] Frame dengan `state="STALE"/stale=true` diteruskan apa adanya.
- [ ] `{type:"ping"}` muncul tiap 15s; kirim `{type:"pong"}` tak menutup koneksi.

## Integration Notes (untuk dokumen jahit akhir Fase 6)

- **Dependensi**: `/ws` membaca `app.state.state_store` (Redis `StateStore` dari
  1.1) — sama dengan REST. Engine worker menulis+publish via `StateStore.set_now`.
- **Wiring**: `register_ws_routes(app)` dipanggil di `create_app()`. Manager di-cache
  di `app.state.ws_manager`, dibuat ulang bila store berganti (mis. test override).
- **Auth seam**: Fase 3 mengisi `security.parse_session_cookie`; bila perlu `?token=`,
  tambah cabang baca token sebelum `accept()` tanpa mengubah jalur gating.
- **FE contract**: tipe frame `snapshot`/`ping`/`pong`, close 4401/4403/4400/1011,
  serta perilaku hold-last-frame saat STALE — cermin langsung untuk store WS di FE.
- **Heartbeat** dapat diatur via env `WS_HEARTBEAT_S` (default 15; test pakai 0.05).

## Assumptions

- Auth WS memakai cookie sesi yang sama dengan REST (bukan `?token=`).
- Saat connect tanpa current state (`get_now` → None), tidak ada frame snapshot
  awal dikirim; klien menunggu push pertama (didokumentasikan untuk FE).
- Pesan client (pong/lainnya) diabaikan di v1; tidak ada rate-limit di layer ini.
- `ws.py` mengimpor `fastapi` & `WebSocketDisconnect` dari Starlette via FastAPI.

## TODO-FROM-OWNER

- Konfirmasi transport auth WS final: cookie sesi (sekarang) vs `?token=` (PRD §7).
- Konfirmasi heartbeat 15s (TASK) vs 30s (PRD §7).
- Putuskan apakah perlu multiplex multi-instrument (`subscribe`/`unsubscribe`) di WS.
