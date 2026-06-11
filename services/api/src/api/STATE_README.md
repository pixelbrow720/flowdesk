# FlowDesk — Redis current-state layer (Fase 2 / lanjutan)

Rilis **1.1** (patch). Live now-state + WS pub/sub fan-out di
`services/api/src/api/state.py`. Sisi LIVE dari data path (PRD #8 §5, §13);
sisi REPLAY tetap dari TimescaleDB (`db/repo.py`, rilis 1.0).

> Patch timpa. Root zip = `flowdesk/` → `unzip -o flowdesk-1.1-redis-state.zip`.

## File dalam patch ini

```
flowdesk/services/api/
├─ pyproject.toml                 # DIUBAH: + redis==5.0.8, + fakeredis (dev). (asyncpg 1.0 tetap)
├─ src/api/
│  ├─ state.py                    # StateStore + Subscription + key scheme + factory
│  └─ STATE_README.md             # dokumen ini
└─ tests/
   └─ test_state.py               # round-trip set/get/publish via fakeredis
```

## Skema key Redis (didokumentasikan)

| Key / channel | Tipe | Isi |
| --- | --- | --- |
| `flowdesk:now:{instrument}` | STRING | snapshot JSON terbaru |
| `flowdesk:session:{instrument}` | STRING | session state saat ini (mis. `"LIVE"`) |
| `flowdesk:updates:{instrument}` | CHANNEL (pub/sub) | snapshot JSON tiap tick untuk fan-out WS |

Konstanta `NOW_KEY` / `SESSION_KEY` / `UPDATES_CHANNEL` di `state.py` = satu
sumber kebenaran; tukar di satu tempat bila perlu.

> **Divergensi dari PRD #8 §5 (di-flag):** PRD menulis `state:{instrument}:latest`,
> `state:{instrument}:session`, channel `live:{instrument}`. TASK ini eksplisit
> meminta skema ber-namespace `flowdesk:*` dan minta saya "document it" — jadi saya
> ikuti TASK. Nama key Redis BUKAN bagian locked contract. Untuk kembali ke nama
> literal PRD, ubah 3 konstanta tsb.

## API

| Fungsi | Perilaku |
| --- | --- |
| `StateStore.set_now(instrument, snapshot)` | SET `now:{}` **dan** PUBLISH ke `updates:{}`; kembalikan JSON string |
| `StateStore.get_now(instrument)` | GET `now:{}` → `dict \| None` |
| `StateStore.set_session(instrument, state)` / `get_session` | SET/GET `session:{}` (string) |
| `StateStore.subscribe(instrument)` | `Subscription` (async context manager) untuk WS layer |
| `create_client(url)` / `create_state_store(url)` | bangun klien redis-py asyncio dari `REDIS_URL` |

`snapshot` menerima dict / JSON string / objek ber-`model_dump()`. redis-py
di-import **lazy** (cuma di `create_client`) → modul & test import tanpa server Redis.

Contoh pemakaian WS layer:
```python
async with store.subscribe("ES") as sub:
    async for snapshot in sub.messages():
        await websocket.send_json({"type": "snapshot", "data": snapshot})
```

## Setup & run

```bash
cd services/api
pip install -e ".[dev]"      # redis + fakeredis + pytest
pytest tests/test_state.py -q
```

### Smoke test terhadap Redis nyata (lokal, manual)
```bash
docker run -d --name flowdesk-redis -p 6379:6379 redis:7-alpine
export REDIS_URL=redis://localhost:6379/0
```
```python
import asyncio
from api.state import create_state_store
async def main():
    store = create_state_store("redis://localhost:6379/0")
    await store.set_now("ES", {"schema_version": 1, "instrument": "ES", "...": "..."})
    print(await store.get_now("ES"))
asyncio.run(main())
```

## Manual verification checklist

- [ ] `pip install -e ".[dev]"` sukses (redis + fakeredis terpasang).
- [ ] `pytest tests/test_state.py -q` → semua PASS.
- [ ] `set_now` lalu `get_now` mengembalikan payload identik.
- [ ] Subscriber pada `flowdesk:updates:ES` menerima pesan setelah `set_now("ES", ...)`.
- [ ] Subscriber instrument ES TIDAK menerima publish instrument NQ.
- [ ] Terhadap Redis nyata: `redis-cli GET flowdesk:now:ES` mengembalikan JSON.

## Integration Notes (untuk dokumen jahit akhir Fase 6)

- **Penulis**: engine worker (Fase berikutnya) memanggil `set_now` tiap menit
  (PRD #8 §13) — SET + PUBLISH dalam satu langkah.
- **Pembaca**: route `GET /api/snapshot/latest` → `get_now` (Redis, bukan DB);
  WS route → `store.subscribe(instrument)` lalu fan-out `sub.messages()`.
- **Env**: `REDIS_URL` (sudah ada di `.env.example`).
- **Titik wiring**: `create_state_store(REDIS_URL)` saat startup app (lifespan),
  inject `StateStore` ke route via dependency. Live=Redis, Replay=Timescale (`db.repo`).
- **Heartbeat** (`heartbeat:engine`, PRD #8 §5) di luar lingkup TASK ini —
  ditambahkan saat engine worker dibangun.

## Assumptions

- Skema key memakai namespace `flowdesk:*` sesuai TASK (lihat divergensi PRD di atas).
- `flowdesk:session:{}` menyimpan **string** SessionState (sesuai TASK "current
  session state"); meta sesi lebih kaya (date/open_ts/last_minute, PRD #8 §5) bisa
  ditaruh sebagai JSON di key yang sama bila nanti dibutuhkan.
- Klien dibuat dengan `decode_responses=True` → GET & pesan pub/sub berupa `str`.
- **Pin** `redis==5.0.8` & `fakeredis==2.23.5` dipilih kompatibel `python==3.11.*`;
  tidak bisa diverifikasi online di sandbox → lihat TODO-FROM-OWNER.

## TODO-FROM-OWNER

- Konfirmasi pin `redis==5.0.8` & `fakeredis==2.23.5` cocok dengan environment
  deploy kamu (keduanya rilis stabil yang mendukung Python 3.11).
- Isi `REDIS_URL` produksi di `.env` (placeholder ada di `.env.example`).
