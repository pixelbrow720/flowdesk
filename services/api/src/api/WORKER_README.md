# FlowDesk — Worker per-menit & State Machine Sesi (Rilis 1.4)

Patch **murni** (hanya file baru/berubah untuk task ini). Root zip `flowdesk/` →
`unzip -o` menimpa langsung di atas hasil 1.0–1.3.

Mengimplementasikan **PRD #9** (kalender/state sesi) dan **PRD #12 T-07/T-08**
(boundary state machine + satu tick worker yang menyimpan & mem-publish snapshot).

## File pada rilis ini

| File | Status | Isi |
| --- | --- | --- |
| `src/api/session.py` | BARU | `determine_state(...)` murni + enum `SessionState` + `MarketCalendar`/`StaticCMECalendar` |
| `src/api/worker.py` | BARU | `MinuteWorker` (loop asyncio teraligned menit ET, dependency di-inject) |
| `tests/test_session.py` | BARU | T-07: boundary 09:30 / 16:00 / half-day 13:00 / holiday / feed-gap |
| `tests/test_worker.py` | BARU | T-08: satu tick LIVE menyimpan+mem-publish; STALE hold; CLOSED idle; loop bounded |
| `src/api/WORKER_README.md` | BARU | dokumen ini |

`pyproject.toml` **tidak berubah** — hanya pakai stdlib (`asyncio`, `zoneinfo`,
`math`) + `flowdesk-engine` (sudah dependency) + `db.repo`/`api.state` yang sudah
ada. Tidak ada dependency baru.

## State machine (PRD #9)

`determine_state(now, calendar, *, last_snapshot_ts=None, feed_gap_tolerance_s=120)`
adalah fungsi **murni** (tanpa I/O, tanpa baca clock). `now` wajib
*timezone-aware*; dikonversi ke **America/New_York** untuk boundary jam dan ke
UTC untuk delta feed-gap (jadi caller boleh kirim UTC maupun ET).

| Kondisi | State |
| --- | --- |
| Akhir pekan atau hari libur CME | `HOLIDAY` |
| Sebelum 09:30 ET | `PREMARKET` |
| `>=` jam tutup (16:00 ET, atau 13:00 ET di half-day) | `CLOSED` |
| Dalam RTH, gap feed `>` 120 dtk | `STALE` (tahan frame terakhir) |
| Dalam RTH, lainnya | `LIVE` |

Boundary mengikuti pseudocode wajib PRD #9 persis: open inklusif (`>= 09:30` =
buka), close inklusif (`>= close` = tutup). `STALE → LIVE` otomatis begitu
snapshot baru tiba (gap mengecil).

Kalender di-inject lewat protokol `MarketCalendar` (`is_holiday(date)` +
`half_day_close(date)`), jadi tabel CME bisa diganti tanpa menyentuh state
machine. `StaticCMECalendar` (murni, tanpa jaringan) adalah default; baseline
2026 sudah disertakan tapi **belum otoritatif** (lihat TODO-FROM-OWNER).

## Loop worker (PRD #9 langkah 1–4)

Setiap menit (teraligned ke batas menit wall-clock ET), untuk tiap instrument:

1. resolve state via `determine_state` (membaca ts snapshot terakhir dari Redis);
2. **LIVE** → `feed.get_chain` → `to_engine_chain` → `build_snapshot` →
   `repo.save_snapshot` (Timescale) → `state.set_now` (Redis, mem-publish ke WS);
3. **STALE** → re-publish snapshot terakhir dengan `stale=true` (hold; `ts`/
   `minute_index` **tidak** diubah agar gap terus tumbuh & tetap STALE sampai
   feed pulih) — tidak menulis baris baru ke Timescale;
4. **CLOSED / HOLIDAY / PREMARKET** → idle (hanya catat session state).

State sesi selalu ditulis ke Redis tiap tick (`state.set_session`).

### Hold saat feed hiccup

Jika di dalam RTH `feed.get_chain` gagal/melempar (gap 1–2 menit), worker
**menahan** frame terakhir (tidak menulis, tidak blank). Karena `ts` snapshot
tersimpan tidak maju, `determine_state` otomatis berpindah ke `STALE` setelah
gap melewati 120 dtk pada tick berikutnya → badge amber di FE.

### Testability (loop)

Semua collaborator di-inject: `clock` (callable → datetime aware), `feed`,
`repo`, `state_store`, dan `sleeper`. `MinuteWorker.tick(now)` menjalankan tepat
satu siklus — dipakai test untuk verifikasi deterministik. `run(max_ticks=...)`
membatasi loop; `stop()` keluar dengan rapi. Penjadwalan tidur sampai batas
menit berikutnya via `_seconds_to_next_minute`.

## Verifikasi manual (sandbox)

```bash
ENG=services/engine/src        # dari rilis 0.9 (engine + feed + snapshot)
SRC=services/api/src
TST=services/api/tests
export PYTHONPATH="$ENG:$SRC:$TST"
python -m compileall services/api/src/api/session.py services/api/src/api/worker.py
pytest services/api/tests/test_session.py services/api/tests/test_worker.py -q
```

Di sandbox ini (tanpa pytest/jaringan) ke-13 test dijalankan lewat harness
asyncio langsung terhadap **pipeline engine asli** (`build_snapshot` +
`parse_snapshot`): **13/13 PASS** — 9 boundary T-07 + 4 worker T-08 (LIVE
simpan+publish, STALE hold, CLOSED idle, loop bounded/aligned). Test memakai
fake feed/repo/state in-memory; leg di-harga Black-76 supaya IV solver
round-trip persis.

## Integration Notes (untuk agen VSCode / stitching Fase 6)

- **Target paths** (overlay di atas 1.0–1.3):
  `services/api/src/api/session.py`, `services/api/src/api/worker.py`,
  `services/api/tests/test_session.py`, `services/api/tests/test_worker.py`.
- **Antarmuka yang dikonsumsi (jangan ubah):**
  - `engine.feed.make_adapter(feed_mode, *, data_dir, api_key)` → `FeedAdapter`
    dengan `get_chain(instrument, ts) → OptionChainMinute` (punya `.forward`,
    `.strikes()`).
  - `engine.feed.to_engine_chain(chain, *, t_expiry) → list[ChainQuote]`.
  - `engine.snapshot.build_snapshot(instrument, ts_utc, chain, forward, rate,
    session_state, axis, *, t_expiry, stale, expired) → Snapshot`.
  - `db.repo.SnapshotRepository.save_snapshot(snapshot)` (menerima model/dict).
  - `api.state.StateStore.get_now/set_now/set_session(instrument, ...)`.
- **Entrypoint produksi:** `api.worker.build_worker_from_env()` membaca 12 key
  env (`FEED_MODE`, `DATA_DIR`, `DATABENTO_API_KEY`, `TIMESCALE_DSN`,
  `REDIS_URL`, `SOFR_RATE`). Jalankan service via `python -m api.worker`.
- **Sumbu strike (axis)** diturunkan dari chain: `strike_min/max` dari strike
  yang ada, `step` LOCKED per instrument (/ES = 5, /NQ = 10).
- **Rate** = `ln(1 + SOFR)` (kontrak terkunci), SOFR dari env.
- Worker tidak menghitung kalender di engine — `build_snapshot` menerima
  `session_state` yang sudah di-resolve (sesuai desain engine 0.8/0.9).

## Divergensi dari PRD (untuk ditinjau owner)

1. **Tabel kalender CME** di-hardcode (baseline 2026) karena sandbox tanpa
   jaringan/paket exchange-calendar. Boundary & half-day benar; *daftar tanggal*
   perlu dikonfirmasi/di-extend owner (lihat TODO).
2. **`DEFAULT_T_EXPIRY`** memakai placeholder kecil (~setengah hari / 365). Timing
   expiry 0DTE intraday yang presisi harus diisi oleh feed per-quote begitu
   sumber data definisi expiry tersambung.
3. **Feed-gap = hold tanpa tulis**: frame STALE hanya di-publish ulang ke Redis,
   tidak ditulis ke Timescale (replay hanya menyimpan menit yang benar-benar
   diproduksi). Bila owner ingin menyimpan jejak STALE, beri tahu.

## Assumptions (pilihan paling sederhana, belum dispesifikasi)

- Akhir pekan diperlakukan sebagai `HOLIDAY` (non-trading) — PRD #9 menyatukan
  hari non-trading di banner closed/holiday; FE tetap menyediakan replay (AC-S5).
- Boundary inklusif: `09:30:00` = `LIVE`, `16:00:00`/`13:00:00` = `CLOSED`.
- Toleransi feed-gap = **120 dtk** (“>2 menit”) dengan perbandingan *strict*.
- Instrument default `("ES", "NQ")`.
- `zoneinfo` memakai tz database sistem OS (`America/New_York`) — tidak butuh
  paket `tzdata` di runtime ini.

## TODO-FROM-OWNER

- [ ] **Kalender CME otoritatif**: konfirmasi daftar holiday + half-day (mis.
  langganan paket/feed kalender resmi). Saat ini baseline 2026 hardcoded.
- [ ] **Final SOFR** untuk `SOFR_RATE` (mempengaruhi `r = ln(1 + SOFR)`).
- [ ] **Databento GLBX.MDP3** langganan + API key untuk `FEED_MODE=live`.
- [ ] Konfirmasi apakah frame STALE perlu disimpan ke Timescale (default: tidak).
