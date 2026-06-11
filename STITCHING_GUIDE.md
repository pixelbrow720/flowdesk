# FlowDesk — Stitching Guide untuk AI Agent (VSCode / Opus 4.x)

> Tujuan: menjahit semua patch rilis (0.1–1.6 backend + Fase 4/5/6 berikutnya) menjadi satu monorepo `flowdesk/` yang utuh, jalan, dan lolos acceptance. Bahasa penjelasan Indonesia; kode/identifier Inggris. LOCKED CONTRACT = mutlak (lihat §2).

---

## 0. Prasyarat & prinsip

- Tiap rilis dikirim sebagai **patch murni** (hanya file baru/berubah), root folder **flowdesk/**. Overlay dengan `unzip -o <zip>` dari root repo → file menimpa dengan rapi.
- Urutan overlay = urutan nomor rilis **menaik** (0.1 → 0.9 → 1.0 → ... → 1.6 → 1.7 → ...). Rilis lebih baru menimpa file lama bila ada konflik path.
- **JANGAN ubah** nilai LOCKED CONTRACT saat menjahit. Bila dua patch konflik di file terkunci, menangkan rilis lebih baru dan catat di STITCH_NOTES.
- Setelah semua overlay: jalankan verifikasi §6 sebelum menjalankan stack.

---

## 1. Target struktur repo akhir

```
flowdesk/
  services/
    engine/                 # paket python flowdesk-engine
      src/engine/           # black76, iv, exposure, field, levels, regime, schema, snapshot, feed/
      pyproject.toml
    api/                    # paket python flowdesk-api
      src/api/              # main, models, errors, state, ws, auth, auth_session,
                            #   discord_client, security, entitlement, FE_AUTH_CONTRACT.md
      mocks/                # me_*.json + mock_me_server.py (rilis 1.6)
      tests/                # test_*.py
      pyproject.toml
    web/                    # Next.js app (Fase 4/5) — ditambahkan nanti
  packages/
    contracts/              # @flowdesk/contracts (mirror snapshot + /api/me schema -> TS)
    tokens/                 # @flowdesk/tokens (design tokens §2 PRD)
  infra/                    # docker-compose.yml, .env.example, ci/ (Fase 6)
  tests/                    # golden/, integration/ (Fase 6)
  package.json              # workspaces root (web/contracts/tokens)
  README.md
```

> Rilis backend menaruh kode API di `services/api/src/api/`. Bila ada patch lama dengan path berbeda (mis. `/api/routes/`), normalkan ke layout di atas dan rapikan import.

---

## 2. LOCKED CONTRACT — DO NOT TOUCH

- **Warna:** turquoise `#40E0D0` (positif/support), crimson `#E0183C` (negatif/resistance), base `#000000`. Heatmap dark turquoise->black->crimson, light turquoise->white->crimson, interpolasi OKLab/LCH.
- **Font:** Space Grotesk (UI) + JetBrains Mono (angka). JANGAN Inter.
- **Instrumen:** /ES mult \$50/pt step 5; /NQ mult \$20/pt step 10.
- **Sesi:** RTH 09:30-16:00 America/New_York, cadence 1 menit, replay 90 hari rolling (turunan saja).
- **Math:** Black-76; r = ln(1+SOFR); IV dari mid (Newton-Raphson -> bisection, tol 1e-6).
- **Dealer:** long calls / short puts. GEX_strike = gamma*VOL*M*F^2*0.01; VOL kumulatif sejak RTH open. Net GEX>0->pinning(turquoise), <0->volatile(crimson).
- **Levels:** Call/Put Wall by GAMMA-DOLLAR (gamma*OI per sisi) STATIK Top 3 (Divergensi #2 -> opsi B; menggantikan aturan raw-OI lama); Gamma Flip + Largest GEX/DEX by VOL dinamis.
- **Day-count 0DTE:** jam-riil ke settlement 16:00 ET via `t_expiry_from_clock` (Divergensi #3 -> opsi A; worker hitung per menit; `0.5/365` lama hanya dipakai bila `t_expiry` di-pin eksplisit, mis. di test).
- **HIRO:** cumulative dealer delta-notional sejak RTH open (`engine.hiro`), sebagai field Snapshot OPSIONAL `hiro` (Divergensi #5 -> opsi A; aditif seperti `ohlc`, TANPA bump schema_version). Garis intraday direkonstruksi FE dari urutan frame per-menit.
- **Auth:** Discord OAuth2 scopes `identify guilds.members.read`. Snapshot schema_version 1.
- **ENV (12 terkunci):** DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_GUILD_ID, DISCORD_DESK_ROLE_ID, SESSION_SECRET, CORS_ORIGINS, FEED_MODE, DATABENTO_API_KEY, DATA_DIR, TIMESCALE_DSN, REDIS_URL, SOFR_RATE. JANGAN tambah key wajib ke-13. (Toggle dev opsional non-locked: PUBLIC_BASE_URL, COOKIE_INSECURE, DISCORD_JOIN_URL.)
- **Akurasi:** GLBX-ES != SpotGamma-SPX (semesta opsi beda) -> validasi STRUKTURAL (arah rezim, urutan ordinal level, timing), bukan match angka-per-angka. Level by VOL boleh beda <= 1-2 strike.

---

## 3. Dependency matrix (versi terpin)

| Komponen | Dependensi inti |
| --- | --- |
| engine | python 3.11.*, numpy; paket flowdesk-engine==0.1.0 |
| api | fastapi==0.112.2, uvicorn[standard]==0.30.6, pydantic==2.8.2, asyncpg==0.29.0, redis==5.0.8, httpx==0.27.0, itsdangerous, flowdesk-engine==0.1.0, databento==0.34.0 (opsional) |
| api (dev) | pytest==8.3.2, fakeredis==2.23.5, ruff==0.5.7, mypy==1.11.1 |
| web | Next.js + React + TypeScript (Fase 4) |

`pyproject.toml` API: `[tool.pytest.ini_options] pythonpath=["src","."]`.

---

## 4. Build order / DAG

```
engine (0.1-0.9)
   └─> api.state/repo (1.0 Timescale, 1.1 Redis)
          └─> api REST (1.2) ─> api WS (1.3)
                 └─> worker + session state machine (1.4)
                        └─> auth: oauth + session + gating (1.5)
                               └─> FE auth contract: /api/me + cta + mock (1.6)
                                      └─> FRONTEND Fase 4 (shell, auth UI, chart)
                                             └─> Fase 5 (replay, settings, onboarding, landing)
                                                    └─> Fase 6 (ops, golden tests, CI/CD)
```

Jangan mulai sub-fase sebelum dependensinya ter-overlay & lolos verifikasi.

---

## 5. Wiring antarmuka

### 5.1 Snapshot (engine -> API -> FE)
- schema_version 1; field: instrument, session_date, ts, minute_index, state, stale, expired, forward, rate, axis{strike_min,strike_max,step}, regime{net_gamma,sign,stability_pct}, profile[]{strike,net_gex,net_dex,interpolated}, field{price_grid[],gamma[],delta[]}, levels{call_walls[],put_walls[],gamma_flip,largest_gex,largest_dex}, ohlc?{o,h,l,c}|null, hiro?{total,calls,puts,zerodte,retail}|null. (ohlc & hiro OPSIONAL/aditif, tanpa bump schema_version.)
- field.gamma.length == field.price_grid.length. state in PREMARKET|LIVE|STALE|CLOSED|HOLIDAY.

### 5.2 REST/WS (API -> FE)
- REST: /api/health, /api/snapshot/latest?instrument, /api/replay/sessions?instrument, /api/replay?instrument&date&from_minute&to_minute, /api/auth/discord/login, /api/auth/discord/callback?code, /api/me (PUBLIK), POST /api/me/recheck.
- WS /ws (cookie-gated): push {type:snapshot,data} per menit; juga status|heartbeat|error. (Auth ?token= + multiplex = backlog.)
- /api/instruments BELUM ada — FE sementara hardcode ["ES","NQ"].

### 5.3 Auth contract (rilis 1.6 — kunci untuk Fase 4)
- GET /api/me -> {access_state:"ANON"|"NO_DESK"|"DESK", discord_id?, has_desk, is_member, last_checked?, grace_until?, cta:{join_url, buy_url:"https://flowjob.id", recheck_supported:true}}.
- FE render: ANON->login CTA; NO_DESK->blur preview + join/buy CTA + tombol "Saya sudah punya DESK — cek ulang" (POST /api/me/recheck); DESK->full app. Grace -> DESK + banner.
- Endpoint data tetap 401/403. Detail + 6 error state + copy Indonesia: services/api/src/api/FE_AUTH_CONTRACT.md.
- Dev tanpa Discord: MOCK_ACCESS_STATE=NO_DESK python services/api/mocks/mock_me_server.py 8787 lalu arahkan FE ke http://localhost:8787.

### 5.4 Env wiring
- Backend baca 12 env terkunci (§2). FE butuh NEXT_PUBLIC_API_BASE -> URL API. CORS: set CORS_ORIGINS ke origin FE; FE fetch dengan credentials: "include".

---

## 6. Verifikasi setelah stitching

1. Persistensi: `find flowdesk -type f | sort` — pastikan tidak ada file hilang dari overlay terakhir.
2. Python compile: `cd flowdesk/services/api && python -m compileall src`.
3. Engine tests: `cd flowdesk/services/engine && pytest`.
4. API tests: `cd flowdesk/services/api && pip install -e . && pytest`.
5. Smoke API: `uvicorn api.main:app` lalu GET /api/health -> 200; GET /api/me tanpa cookie -> 200 access_state ANON.
6. Lint/type: `ruff check` + `mypy`.

---

## 7. Acceptance gate (PRD #12)

| ID | Kasus | Ekspektasi |
| --- | --- | --- |
| T-01 | Black-76 ATM/ITM/OTM | < 1e-6 vs referensi |
| T-02 | IV solver mid normal | konvergen < 50 iter |
| T-03 | IV likuiditas tipis | fallback bisection/interpolasi, tidak crash |
| T-04 | NetGEX tanda dealer | long call/short put benar |
| T-05 | Field zero-crossing | gamma_flip terinterpolasi |
| T-06 | Wall gamma-$ Top 3 | persis vs golden (gamma*OI per sisi, Div #2->B) |
| T-07 | State machine boundary | benar di 09:30, close, half-day |
| T-08 | Gap feed | STALE + tahan frame |
| T-09 | Gating non-DESK | 403 di endpoint data |
| T-10 | Pipeline 1 menit | < 60 dtk |

Staging FEED_MODE=historical wajib lolos sebelum flip live. Step regression gagal = blocker mutlak.

---

## 8. Checklist per sub-fase

### Fase 4 — Frontend inti
- [ ] Scaffold services/web (Next.js + TS) + packages/tokens (token §2 PRD) + packages/contracts (mirror snapshot + /api/me ke TS).
- [ ] App shell: topbar (44px) + layout left/axis/right + scrubber (56px) + floating glass toolbar (auto-fade 2.5s).
- [ ] Auth UI dari /api/me: ANON/NO_DESK/DESK + blur preview + tombol re-check (mock server dulu).
- [ ] Heatmap WebGL (field projection) + ProfileLine (NetGEX/NetDEX) berbagi sumbu strike (selaras baris).
- [ ] Price line dashed + tag; hover crosshair + tooltip; Regime pill + stability % (JetBrains Mono).
- [ ] WS client /ws (subscribe ES/NQ; reconnect backoff 1/2/4/max30s).
- [ ] Toggles: Gamma/Delta, GEX/DEX, smooth/block, zoom slider, segmented ES/NQ, dark/light (default Dark/Gamma/NetGEX/ES).
- [ ] Verifikasi AC-DB1..6, AC-P1..5, AC-D1..5.

### Fase 5 — Frontend lanjutan
- [ ] Replay: load /api/replay, play/pause, scrubber, 1x/2x/4x, step +-1m, badge REPLAY, "Kembali ke LIVE".
- [ ] Settings slide-in (360px) + persist localStorage flowdesk.prefs; section Akun (status DESK, re-check, logout).
- [ ] Onboarding tour 3-4 langkah (skippable, status per user).
- [ ] Landing page (8 section §3 PRD) + hero hover demo + demo replay statis 30 menit.
- [ ] Polish anti-AI-look (aturan §2.3 PRD).

### Fase 6 — Ops / Testing / CI/CD
- [ ] infra/docker-compose.yml: worker, api(8000), timescaledb(5432), redis(6379) + healthcheck + restart: unless-stopped.
- [ ] .env.example (12 key terkunci), secrets via ENV.
- [ ] Golden dataset (5 hari + 2-3 ekstrem) + regression tests (toleransi §7).
- [ ] Worker watchdog (>2m tanpa snapshot -> restart) + heartbeat alert Discord webhook.
- [ ] CI pipeline 8 langkah (lint->unit->regression->build->staging->smoke->approval->prod). Step 3 gagal = blokir.
- [ ] Backup Timescale mingguan + drill restore; telemetri + error tracking.

---

## 9. Catatan integrasi & jebakan

- Endpoint data pakai 403 FORBIDDEN generik; pembedaan not-member vs no-desk hanya via /api/me (access_state + is_member). FE jangan andalkan body 403.
- /api/me PUBLIK (anon -> 200 ANON). Sengaja (divergensi tercatat dari 1.5 yang 401).
- DISCORD_JOIN_URL default = https://flowjob.id sampai owner isi invite asli.
- Nama key Redis bukan locked contract — selaraskan antar modul, jangan asumsikan persis sama dengan contoh PRD.
- Saat menjahit, jika dua rilis mengubah file sama, menangkan rilis lebih baru; verifikasi ulang import.
