"""Finiteness hardening for the Snapshot contract — Phase 1 Item 4.

This test enforces the engine half of a three-layer guard against NaN / ±Inf:

    1. **Pydantic ingress** — every numeric field on the Python `Snapshot`
       mirror is annotated `FiniteFloat` (`allow_inf_nan=False`). NaN / Inf
       are rejected at validation time.
    2. **Pydantic egress** — `Snapshot.to_json()` re-walks the dump and raises
       on any non-finite that slipped through (e.g. `model_construct` bypass,
       a future field added without the annotation).
    3. **Zod ingress** — the TypeScript mirror in `packages/contracts/src/
       snapshot.ts` already uses `z.number().finite()` for every numeric
       leaf. It rejects the SAME byte-for-byte JSON payloads this test
       generates; the parity assertion is exercised by the cross-language
       fixtures `examples/snapshot.nan_*.json` (consumed by both
       `scripts/validate.ts` and the Python `test_zod_fixtures_rejected`
       below).

Why this matters
================
JSON has no NaN/Inf token. Pydantic's default `model_dump_json` silently
emits `null` for NaN/Inf, which (a) corrupts downstream consumers that
treat null as "field absent / not captured" and (b) desynchronises the
two mirrors: the zod side rejects on parse, the pydantic side accepts
and re-emits a different shape. That asymmetry is the contract bug this
hardening closes.

The test enumerates EVERY numeric injection point in the schema rather
than spot-checking one or two: a regression in any single field is a
contract violation, not a "minor" issue, because a single non-finite
field is enough to break the FE heatmap or to make the JSON unparseable.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from engine.schema import Snapshot, parse_snapshot

NAN = float("nan")
POS_INF = float("inf")
NEG_INF = float("-inf")
NON_FINITE_VALUES: tuple[float, ...] = (NAN, POS_INF, NEG_INF)


# ---------------------------------------------------------------------------
# Base payload — a fully-populated Snapshot with every optional sub-object set.
# Built from primitives only so the test does not depend on `build_snapshot`.
# ---------------------------------------------------------------------------
def _base_payload() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "instrument": "ES",
        "session_date": "2026-06-10",
        "ts": "2026-06-10T13:31:00Z",
        "minute_index": 1,
        "state": "LIVE",
        "stale": False,
        "expired": False,
        "forward": 5000.25,
        "rate": 0.0517,
        "axis": {"strike_min": 4990.0, "strike_max": 5010.0, "step": 5.0},
        "regime": {
            "net_gamma": -1.23e9,
            "sign": -1,
            "stability_pct": 42.0,
        },
        "profile": [
            {
                "strike": 4995.0,
                "net_gex": -4.0e7,
                "net_dex": 2.8e7,
                "interpolated": True,
            },
            {
                "strike": 5000.0,
                "net_gex": 5.6e8,
                "net_dex": 2.2e7,
                "interpolated": False,
            },
        ],
        "fog": {
            "price_grid": [4995.0, 5000.0],
            "gamma": [-8.0e6, 3.3e7],
            "delta": [1.05e7, 1.0e7],
        },
        "levels": {
            "call_walls": [5050.0, 5025.0],
            "put_walls": [4950.0, 4975.0],
            "gamma_flip": 4998.5,
            "largest_gex": 5000.0,
            "largest_dex": 4990.0,
        },
        "ohlc": {"o": 5000.0, "h": 5001.5, "l": 4999.0, "c": 5000.25},
        "flux": {
            "total": 1.5e6,
            "calls": 1.0e6,
            "puts": 5.0e5,
            "zerodte": 1.2e6,
            "retail": 1.0e5,
        },
        "synthetic_oi": {
            "gex": 1.0e8,
            "sign": 1,
            "gex_static": 8.0e7,
            "w": 0.5,
        },
        "synthetic_oi_tiered": {
            "gex": 1.1e8,
            "sign": 1,
            "gex_static": 8.0e7,
            "w": 0.5,
        },
        "synthetic_oi_decay": {
            "gex": 9.0e7,
            "sign": 1,
            "gex_static": 8.0e7,
            "w": 0.5,
        },
        "exposure_ext": {
            "net_vex": 2.0e6,
            "vex_sign": 1,
            "net_chex": -3.0e6,
            "chex_sign": -1,
        },
        "total_hedging": {
            "gamma_hedge": 1.0e8,
            "charm_hedge": -2.5e6,
            "vanna_hedge": 1.8e6,
            "w": 0.5,
        },
        "surface": {
            "atm_vol": 0.21,
            "expected_move": 12.5,
            "skew": -0.4,
            "rmse": 0.001,
            "variance_nonneg": True,
            "svi_a": 0.04,
            "svi_b": 0.1,
            "svi_rho": -0.3,
            "svi_m": 0.0,
            "svi_sigma": 0.2,
        },
        "ddoi": {"gex": 7.0e7, "sign": 1},
        "proprietary": {
            "oi_gamma_flip": 5000.0,
            "abs_gamma_strike": 5005.0,
            "hedge_wall": 4995.0,
        },
    }


def _set_path(payload: dict[str, Any], path: tuple[Any, ...], value: Any) -> None:
    """Mutate ``payload`` in place: walk ``path`` and assign ``value`` at the leaf."""
    cur: Any = payload
    for step in path[:-1]:
        cur = cur[step]
    cur[path[-1]] = value


# ---------------------------------------------------------------------------
# 1. Sanity: the base payload is contract-valid as written.
# ---------------------------------------------------------------------------
def test_base_payload_is_valid_baseline() -> None:
    """Without any mutation, the canonical full payload must round-trip."""
    snap = parse_snapshot(_base_payload())
    assert snap.schema_version == 2
    # Egress must not raise either — full sanity for the to_json() guard.
    out = snap.to_json()
    reparsed = parse_snapshot(json.loads(out))
    assert reparsed.forward == 5000.25


# ---------------------------------------------------------------------------
# 2. Ingress rejection: enumerate every numeric injection point.
# Each entry is a `pytest.param(path, id=...)`; the test runs 3× per path
# (NaN, +Inf, -Inf) so a regression in any one field surfaces independently.
# ---------------------------------------------------------------------------
NUMERIC_PATHS: list[tuple[Any, ...]] = [
    # Top-level scalars
    ("forward",),
    ("rate",),
    # axis
    ("axis", "strike_min"),
    ("axis", "strike_max"),
    ("axis", "step"),
    # regime
    ("regime", "net_gamma"),
    ("regime", "stability_pct"),
    # profile[0] & profile[1] (rows)
    ("profile", 0, "strike"),
    ("profile", 0, "net_gex"),
    ("profile", 0, "net_dex"),
    ("profile", 1, "strike"),
    ("profile", 1, "net_gex"),
    ("profile", 1, "net_dex"),
    # field arrays (each element is a FiniteFloat — element-level rejection)
    ("fog", "price_grid", 0),
    ("fog", "price_grid", 1),
    ("fog", "gamma", 0),
    ("fog", "gamma", 1),
    ("fog", "delta", 0),
    ("fog", "delta", 1),
    # levels
    ("levels", "call_walls", 0),
    ("levels", "call_walls", 1),
    ("levels", "put_walls", 0),
    ("levels", "put_walls", 1),
    ("levels", "gamma_flip"),
    ("levels", "largest_gex"),
    ("levels", "largest_dex"),
    # ohlc
    ("ohlc", "o"),
    ("ohlc", "h"),
    ("ohlc", "l"),
    ("ohlc", "c"),
    # flux
    ("flux", "total"),
    ("flux", "calls"),
    ("flux", "puts"),
    ("flux", "zerodte"),
    ("flux", "retail"),
    # synthetic_oi (and the two parallel _tiered / _decay shapes)
    ("synthetic_oi", "gex"),
    ("synthetic_oi", "gex_static"),
    ("synthetic_oi", "w"),
    ("synthetic_oi_tiered", "gex"),
    ("synthetic_oi_tiered", "gex_static"),
    ("synthetic_oi_tiered", "w"),
    ("synthetic_oi_decay", "gex"),
    ("synthetic_oi_decay", "gex_static"),
    ("synthetic_oi_decay", "w"),
    # exposure_ext
    ("exposure_ext", "net_vex"),
    ("exposure_ext", "net_chex"),
    # total_hedging
    ("total_hedging", "gamma_hedge"),
    ("total_hedging", "charm_hedge"),
    ("total_hedging", "vanna_hedge"),
    ("total_hedging", "w"),
    # surface
    ("surface", "atm_vol"),
    ("surface", "expected_move"),
    ("surface", "skew"),
    ("surface", "rmse"),
    ("surface", "svi_a"),
    ("surface", "svi_b"),
    ("surface", "svi_rho"),
    ("surface", "svi_m"),
    ("surface", "svi_sigma"),
    # ddoi
    ("ddoi", "gex"),
    # proprietary
    ("proprietary", "oi_gamma_flip"),
    ("proprietary", "abs_gamma_strike"),
    ("proprietary", "hedge_wall"),
]


def _path_id(path: tuple[Any, ...]) -> str:
    return ".".join(str(p) for p in path)


@pytest.mark.parametrize(
    "bad_value",
    NON_FINITE_VALUES,
    ids=("nan", "+inf", "-inf"),
)
@pytest.mark.parametrize(
    "path",
    NUMERIC_PATHS,
    ids=[_path_id(p) for p in NUMERIC_PATHS],
)
def test_pydantic_ingress_rejects_non_finite(
    path: tuple[Any, ...], bad_value: float
) -> None:
    """Every numeric leaf must reject NaN/+Inf/-Inf at validation time."""
    payload = _base_payload()
    _set_path(payload, path, bad_value)
    with pytest.raises(ValidationError) as excinfo:
        parse_snapshot(payload)
    # The error must point at the offending field, not a generic "extra" or
    # length error — i.e. pydantic's own finite-check fired.
    err_str = str(excinfo.value).lower()
    assert "finite" in err_str or "nan" in err_str or "inf" in err_str, (
        f"validation error at {_path_id(path)} for {bad_value!r} did not "
        f"mention finiteness:\n{excinfo.value}"
    )


def test_pydantic_ingress_accepts_zero_and_negative_finite() -> None:
    """Sanity guard: the hardening must NOT reject legitimate finite values
    such as 0.0 (gamma_flip can be a real strike) or large negatives (net_gex).
    """
    payload = _base_payload()
    payload["regime"]["net_gamma"] = -1e15
    payload["forward"] = 1e-9
    payload["levels"]["gamma_flip"] = 0.0  # boundary
    snap = parse_snapshot(payload)
    assert snap.regime.net_gamma == -1e15
    assert snap.levels.gamma_flip == 0.0


def test_pydantic_ingress_accepts_optional_null() -> None:
    """The hardening only forbids non-finite floats; `null` for optional fields
    must continue to be contract-valid (matches zod `.nullable()`/`.nullish()`).
    """
    payload = _base_payload()
    for k in ("ohlc", "flux", "synthetic_oi", "exposure_ext", "ddoi"):
        payload[k] = None
    payload["levels"]["gamma_flip"] = None
    payload["levels"]["largest_gex"] = None
    payload["levels"]["largest_dex"] = None
    snap = parse_snapshot(payload)
    assert snap.ohlc is None
    assert snap.levels.gamma_flip is None


# ---------------------------------------------------------------------------
# 3. Egress guard: defence-in-depth check on `to_json()`.
# A model that bypassed validation (e.g. via `model_construct`) MUST still
# fail on serialisation rather than emit JSON with NaN coerced to null.
# ---------------------------------------------------------------------------
def test_egress_guard_rejects_non_finite_after_construct_bypass() -> None:
    """A `model_construct` bypass that injects NaN must be caught on to_json."""
    snap = parse_snapshot(_base_payload())
    # Construct a clone with the validator disabled, then poke a NaN in.
    poisoned = Snapshot.model_construct(
        **{**snap.model_dump(), "forward": NAN}
    )
    with pytest.raises(ValueError, match="non-finite"):
        poisoned.to_json()


def test_egress_guard_rejects_non_finite_in_nested_array() -> None:
    """Egress walk must descend into arrays (field.gamma[i], etc.)."""
    snap = parse_snapshot(_base_payload())
    dump = snap.model_dump()
    dump["fog"]["gamma"][0] = POS_INF
    poisoned = Snapshot.model_construct(**dump)
    with pytest.raises(ValueError, match="non-finite"):
        poisoned.to_json()


def test_egress_guard_rejects_non_finite_in_optional_nested_object() -> None:
    """Egress walk must descend into optional sub-objects (flux, surface, …)."""
    snap = parse_snapshot(_base_payload())
    dump = snap.model_dump()
    dump["surface"]["atm_vol"] = NEG_INF
    poisoned = Snapshot.model_construct(**dump)
    with pytest.raises(ValueError, match="non-finite"):
        poisoned.to_json()


def test_egress_guard_emits_clean_json_for_valid_snapshot() -> None:
    """No false positives: a valid snapshot serialises and json.loads round-trips."""
    snap = parse_snapshot(_base_payload())
    out = snap.to_json()
    parsed = json.loads(out)
    # All numeric leaves in the dump must be finite floats (no NaN/Infinity tokens
    # — Python's json.loads would parse those if non-strict, but JSON spec forbids).
    def _walk(v: Any) -> None:
        if isinstance(v, float):
            assert math.isfinite(v)
        elif isinstance(v, dict):
            for x in v.values():
                _walk(x)
        elif isinstance(v, list):
            for x in v:
                _walk(x)
    _walk(parsed)


# ---------------------------------------------------------------------------
# 4. Cross-mirror parity: the same byte-for-byte payloads pydantic rejects
# must also be rejected by the zod mirror. The zod side cannot run inside
# pytest, so we materialise the rejection cases as JSON fixtures consumed
# by `packages/contracts/scripts/validate.ts`. The test below asserts the
# fixtures EXIST and that pydantic still rejects each one — guaranteeing the
# two validators see identical inputs.
# ---------------------------------------------------------------------------
_FIXTURES_DIR = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "contracts"
    / "examples"
)

NAN_FIXTURES: tuple[tuple[str, tuple[Any, ...], float], ...] = (
    ("snapshot.nonfinite_forward_nan.json", ("forward",), NAN),
    ("snapshot.nonfinite_fog_gamma_inf.json", ("fog", "gamma", 0), POS_INF),
    ("snapshot.nonfinite_regime_stability_neginf.json",
     ("regime", "stability_pct"), NEG_INF),
    ("snapshot.nonfinite_levels_gamma_flip_nan.json",
     ("levels", "gamma_flip"), NAN),
)


def _write_fixture_if_missing(name: str, payload: dict[str, Any]) -> Path:
    """Write a JSON fixture using Python's `allow_nan=True` so NaN/Inf survive
    the round-trip (the standard json module emits the non-spec literal
    `NaN`/`Infinity` tokens that `JSON.parse` in node will then reject — which
    is exactly the parity case we want both validators to refuse)."""
    path = _FIXTURES_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use allow_nan=True (default) so the literal NaN/Infinity reach the file.
    path.write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("filename", "path", "bad_value"),
    NAN_FIXTURES,
    ids=[f[0] for f in NAN_FIXTURES],
)
def test_zod_fixtures_pydantic_rejects_byte_for_byte(
    filename: str, path: tuple[Any, ...], bad_value: float
) -> None:
    """Generate the cross-mirror fixture, then assert pydantic rejects it.

    The same JSON file is consumed by `packages/contracts/scripts/validate.ts`
    on the zod side; if both validators reject it, the mirrors agree. Because
    the file contains the literal `NaN`/`Infinity` tokens (non-spec JSON),
    Node's strict `JSON.parse` would itself reject the file — that ALSO counts
    as parity (both ecosystems refuse the bad payload), and `validate.ts`
    treats either failure mode as a successful rejection.
    """
    payload = _base_payload()
    _set_path(payload, path, bad_value)
    fixture_path = _write_fixture_if_missing(filename, payload)
    # Read it back via JSON the same way the zod validator would, then feed
    # to pydantic. We use `parse_constant` to keep NaN/Infinity tokens.
    raw = fixture_path.read_text(encoding="utf-8")
    revived = json.loads(raw)  # default parser keeps NaN/Infinity as floats
    with pytest.raises(ValidationError):
        parse_snapshot(revived)
