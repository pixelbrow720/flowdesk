# FlowDesk API — Release 1.6 (FE Auth Contract)

**Patch murni** (hanya file baru/berubah relatif ke 1.5). Root `flowdesk/`;
`unzip -o flowdesk-1.6-fe-contract.zip` menimpa repo langsung. Tidak ada
dependensi baru → `pyproject.toml` TIDAK ikut (tak berubah dari 1.5).

TASK: definisikan + implementasikan kontrak backend yang dipakai FE untuk
merender pengalaman denied/preview-blur & onboarding (PRD #6), agar Fase 4
bisa membangun UI di atasnya.

## Isi patch (file untuk rilis ini)

```
flowdesk/services/api/
  src/api/
    entitlement.py          [BARU]  proyeksi session -> access_state + cta (pure)
    models.py               [UBAH]  + Cta, + MeResponse.access_state, discord_id Optional
    main.py                 [UBAH]  /api/me jadi PUBLIK (ANON=200); /recheck tetap 401 anon
    FE_AUTH_CONTRACT.md     [BARU]  kontrak FE: ANON/NO_DESK/DESK + 6 error state PRD #6
  mocks/
    me_anon.json            [BARU]  rekaman respons /api/me state ANON
    me_no_desk.json         [BARU]  rekaman respons state NO_DESK
    me_desk.json            [BARU]  rekaman respons state DESK
    me_grace.json           [BARU]  bonus: DESK + grace_until (banner)
    mock_me_server.py       [BARU]  mock server stdlib (tanpa deps) untuk FE
  tests/
    test_me_contract.py     [BARU]  asersi bentuk /api/me tiap state
    test_auth.py            [UBAH]  /api/me anon kini 200 ANON (bukan 401)
  README.1.6.md             [BARU]  berkas ini
```

## Setup & run

```bash
# dari root repo, overlay patch
unzip -o flowdesk-1.6-fe-contract.zip

# jalankan API (deps & env dari 1.5; tak ada deps baru)
cd flowdesk/services/api
uvicorn api.main:app --reload   # GET /api/me kini publik

# mock untuk FE tanpa Discord live (stdlib, tanpa deps):
MOCK_ACCESS_STATE=NO_DESK python mocks/mock_me_server.py 8787
# FE -> NEXT_PUBLIC_API_BASE=http://localhost:8787
```

## Checklist verifikasi manual

- [ ] `python -m compileall src/api/entitlement.py src/api/models.py src/api/main.py`
- [ ] `pytest tests/test_me_contract.py tests/test_auth.py` hijau (butuh fastapi/httpx/itsdangerous + engine di PYTHONPATH).
- [ ] `GET /api/me` tanpa cookie -> `200` `{access_state:"ANON", discord_id:null, cta:{buy_url:"https://flowjob.id", recheck_supported:true, ...}}`.
- [ ] Login DESK -> `GET /api/me` -> `access_state:"DESK"`. Login member tanpa DESK -> `NO_DESK`.
- [ ] Cabut role -> `POST /api/me/recheck` -> `DESK` + `grace_until` terisi (hari ini). Setelah grace habis -> `NO_DESK`.
- [ ] `POST /api/me/recheck` tanpa session -> `401`.
- [ ] Endpoint data (`/api/snapshot`, `/api/replay*`, `/ws`) tetap `401`/`403` untuk non-DESK.
- [ ] 4 fixture di `mocks/*.json` mem-parse ke `MeResponse` dan cocok state-nya.

Verifikasi sandbox (tanpa FastAPI/jaringan): harness `verify_contract.py`
membuktikan mapping `build_me_response` (ANON/NO_DESK/DESK/grace), CTA terkunci,
dan parsing 4 fixture → **25/25 PASS**. Tes HTTP TestClient di
`test_me_contract.py`/`test_auth.py` dijalankan di environment nyata (fastapi/
httpx/itsdangerous tidak terpasang di sandbox).

## Integration Notes

- **`/api/me` sekarang PUBLIK** (perubahan perilaku dari 1.5 yang `401` saat
  anonim). Gerbang keras `401/403` tetap di endpoint data. FE merender
  sepenuhnya dari `/api/me` (lihat `FE_AUTH_CONTRACT.md`).
- `access_state`: tanpa session=`ANON`; `has_desk`=`DESK`; dalam grace=`DESK`
  (+banner); selain itu=`NO_DESK` (termasuk bukan-anggota; bedakan via
  `is_member`).
- `cta.buy_url` dikunci `https://flowjob.id` (dari TASK). `cta.join_url` dari
  env opsional non-locked `DISCORD_JOIN_URL` (default = buy_url sampai owner
  isi invite asli). `recheck_supported` selalu `true`.
- Tidak menambah env key baru: 12 key terkunci tetap; `DISCORD_JOIN_URL`
  opsional (seperti `PUBLIC_BASE_URL`/`COOKIE_INSECURE`).
- Pembeda not-member vs no-desk TIDAK dibedakan di kode HTTP endpoint data
  (keduanya `403 FORBIDDEN`); pembedaan disuguhkan via `/api/me`
  (`access_state` + `is_member`) yang menjadi sumber kebenaran UX FE.

## TODO-FROM-OWNER

- **`DISCORD_JOIN_URL`**: isi dengan link invite Discord guild FlowDesk yang
  sebenarnya (saat ini default ke `https://flowjob.id`).
- Konfirmasi copy Indonesia untuk 6 error state (lihat `FE_AUTH_CONTRACT.md` §3)
  bila ada preferensi wording resmi.
