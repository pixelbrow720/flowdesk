# FlowDesk — TimescaleDB storage untuk derived snapshots (Fase 2)

Rilis **1.0** (patch). Implementasi storage snapshot turunan di `services/api`:
migration TimescaleDB + repository async (asyncpg, thin query layer, **tanpa ORM**).

> Catatan rilis: ini patch **timpa** (overlay). Root zip = `flowdesk/`, jadi cukup
> `unzip -o flowdesk-1.0-storage.zip` di atas repo — file mendarat tepat di
> `services/api/...`.

---

## File dalam patch ini

```
flowdesk/services/api/
├─ pyproject.toml                  # DIUBAH: + asyncpg==0.29.0, + pytest (dev), pytest pythonpath
├─ db/
│  ├─ __init__.py                  # re-export repo API
│  ├─ repo.py                      # SnapshotRepository + SQL + pool/migration helper
│  ├─ migrations/
│  │  └─ 0001_init.sql             # hypertable `snapshots` + index + retensi 90 hari
│  └─ README.md                    # dokumen ini
└─ tests/
   └─ test_repo.py                 # unit test SQL + binding (pakai test-double)
```

**Prasyarat rilis sebelumnya (tidak disertakan, patch-murni):** kontrak Snapshot
ada di `packages/contracts` (TS) dan `services/engine/src/engine/schema.py` (Py).
Repo ini **tidak meng-import** engine — ia menerima Snapshot berupa dict / JSON
string / objek ber-`model_dump()`.

---

## Skema DB (`0001_init.sql`)

Tabel `snapshots` — **superset PRD #8 §4**:

| Kolom | Tipe | Sumber |
| --- | --- | --- |
| `instrument` | TEXT | extracted |
| `session_date` | DATE | extracted (filter cepat) |
| `ts` | TIMESTAMPTZ | extracted (dimensi waktu hypertable) |
| `minute_index` | INT | extracted (filter cepat) |
| `state` | TEXT | extracted (SessionState) |
| `regime_sign` | SMALLINT | extracted (`regime.sign`, CHECK -1\|0\|1) |
| `forward` | DOUBLE PRECISION | extracted |
| `payload` | JSONB | **Snapshot JSON penuh (PRD #8 §3)** |

- **PK** `(instrument, ts)` → `create_hypertable('snapshots', 'ts')`.
- **Index** `(instrument, session_date, minute_index)` untuk query replay.
- **Retensi**: `add_retention_policy('snapshots', INTERVAL '90 days')` — derived-only,
  akumulatif sejak launch (PRD #10 §4). Raw chain TIDAK pernah disimpan di DB produksi.

## Repository (`repo.py`) — query replay PRD #10

| Method | SQL | Mengembalikan |
| --- | --- | --- |
| `save_snapshot(snapshot)` | INSERT … ON CONFLICT (instrument, ts) DO UPDATE | upsert idempoten |
| `get_snapshot(instrument, session_date, minute_index)` | SELECT payload … LIMIT 1 | `dict \| None` |
| `list_sessions(instrument)` | SELECT session_date, COUNT(*) … GROUP BY … DESC | `[{session_date, minute_count}]` |
| `get_range(instrument, session_date, from_minute, to_minute)` | SELECT payload … BETWEEN … ORDER BY minute_index | `Snapshot[]` |

- `list_sessions` & `get_range` memetakan persis kontrak `GET /api/replay/sessions`
  dan `GET /api/replay` (PRD #10 §2).
- Semua identifier tabel/kolom **double-quoted**; parameter pakai placeholder
  posisional `$1..$N` (binding asyncpg, anti SQL-injection).
- `payload` di-encode/decode eksplisit dengan `json` stdlib + cast `$8::jsonb`
  (thin layer, transparan, mudah ditest). Tidak ada codec asyncpg tersembunyi.

---

## Setup & run

```bash
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # termasuk asyncpg + pytest
```

### Unit test (TANPA database — default)

```bash
cd services/api
pytest tests/test_repo.py -q
```
Memakai test-double yang merekam (SQL, args); memverifikasi string SQL,
kutip identifier, urutan & bentuk parameter, serta decode payload replay.

### Integration test NYATA terhadap TimescaleDB (lokal, manual)

1. Jalankan Timescale (contoh Docker):
   ```bash
   docker run -d --name flowdesk-ts -p 5432:5432 \
     -e POSTGRES_PASSWORD=postgres timescale/timescaledb:2.16.1-pg16
   export TIMESCALE_DSN=postgresql://postgres:postgres@localhost:5432/postgres
   ```
2. Terapkan migration + smoke test:
   ```python
   import asyncio
   from db.repo import create_pool, apply_migrations, SnapshotRepository

   async def main():
       pool = await create_pool("postgresql://postgres:postgres@localhost:5432/postgres")
       async with pool.acquire() as conn:
           await apply_migrations(conn)            # runs 0001_init.sql
       repo = SnapshotRepository(pool)
       # await repo.save_snapshot(my_snapshot_dict)
       print(await repo.list_sessions("ES"))
   asyncio.run(main())
   ```
   `apply_migrations` mengeksekusi seluruh `0001_init.sql` dalam satu panggilan
   (asyncpg mengeksekusi multi-statement saat tanpa argumen).

---

## Manual verification checklist

- [ ] `pip install -e ".[dev]"` sukses (asyncpg & pytest terpasang).
- [ ] `pytest tests/test_repo.py -q` → semua PASS.
- [ ] Terhadap Timescale nyata: `apply_migrations` membuat hypertable
      (`SELECT * FROM timescaledb_information.hypertables;` memuat `snapshots`).
- [ ] Index `snapshots_replay_idx` ada (`\d snapshots`).
- [ ] `add_retention_policy` terdaftar
      (`SELECT * FROM timescaledb_information.jobs WHERE application_name LIKE '%Retention%';`).
- [ ] `save_snapshot` lalu `get_snapshot` mengembalikan payload identik (round-trip).
- [ ] `list_sessions` mengembalikan `{session_date, minute_count}` urut terbaru dulu.

## Integration Notes (untuk dokumen jahit akhir Fase 6)

- **Konsumen tulis**: engine worker (`main_worker.py`, Fase berikutnya) memanggil
  `SnapshotRepository.save_snapshot(snapshot)` tiap menit (PRD #8 §13).
- **Konsumen baca**: route API `replay.py` memanggil `list_sessions` & `get_range`;
  `snapshot.py` (latest) baca Redis, bukan DB.
- **Env**: butuh `TIMESCALE_DSN` (sudah ada di `.env.example`).
- **Titik wiring**: `create_pool(TIMESCALE_DSN)` dibuat saat startup app (lifespan),
  lalu `SnapshotRepository(pool)` disuntik ke route via dependency.
- **Kontrak**: kolom turunan HARUS konsisten dengan `schema.py` (state enum,
  regime.sign ∈ {-1,0,1}); `payload` = Snapshot `schema_version=1` apa adanya.

## Assumptions

- **Nama tabel `snapshots` (plural)** mengikuti TASK ini; PRD #8 §4 menulis
  `snapshot` (singular). Divergensi nama saja — struktur tetap superset PRD #8.
- Ditambah kolom turunan `state` & `regime_sign` (di luar DDL PRD #8) sesuai
  permintaan TASK untuk filter cepat; semuanya tetap redundan terhadap `payload`.
- `payload` disimpan sebagai JSON string + cast `::jsonb` (bukan codec asyncpg),
  agar layer tetap tipis & deterministik untuk testing.
- **Pin `asyncpg==0.29.0`** dipilih kompatibel dengan `requires-python == 3.11.*`.
  Tidak bisa diverifikasi online di sandbox → lihat TODO-FROM-OWNER.
- `create_hypertable`/`add_retention_policy` memakai `if_not_exists => TRUE`
  agar migration idempoten saat dijalankan ulang.

## TODO-FROM-OWNER

- Konfirmasi versi `asyncpg` (0.29.0) cocok dengan environment deploy kamu, dan
  versi image TimescaleDB produksi (mis. `timescaledb:2.16.x-pg16`).
- Isi `TIMESCALE_DSN` produksi di `.env` (placeholder ada di `.env.example`).
