"""Unit tests for engine.black76 (PRD #12, acceptance T-01).

Reference strategy
------------------
We never multiply by hand. Instead we hard-code the *standard-normal* constants
that the Black-76 price/greeks are built from (Phi and phi at the exact d1/d2
that our chosen parameters produce), and let Python assemble the reference
value from the textbook formula. The implementation under test computes Phi via
``math.erf`` and assembles the same formula independently, so a sign error,
discounting error, or d1/d2 error is caught while the arithmetic stays exact.

All parameter sets are chosen so that d1 / d2 land on values whose Phi / phi we
know to full double precision:

    Phi(0.0) = 0.5
    Phi(0.1) = 0.5398278372770290
    Phi(0.2) = 0.5792597094391030
    phi(0.0) = 0.3989422804014327   (== 1/sqrt(2*pi))
    phi(0.1) = 0.3969525474770118   (== exp(-0.005)/sqrt(2*pi))
    phi(0.2) = 0.3910426939754561   (== exp(-0.020)/sqrt(2*pi))

Case geometry (sigma=0.2, T=1 => sigma*sqrt(T)=0.2):
    ATM      F=K=100            -> d1=+0.1, d2=-0.1
    ITM call F=100*exp(+0.02)   -> d1=+0.2, d2= 0.0   (also OTM put)
    OTM call F=100*exp(-0.02)   -> d1= 0.0, d2=-0.2   (also ITM put)

Tolerance: every comparison uses abs_tol=1e-9, comfortably inside the
required < 1e-6 (the two assemblies actually agree to ~1e-13).
"""

from __future__ import annotations

import math

import pytest

from engine.black76 import (
    charm,
    d1_d2,
    delta,
    gamma,
    norm_cdf,
    norm_pdf,
    price,
    theta,
    vanna,
    vega,
)

# --------------------------------------------------------------------------- #
# Hand-listed standard-normal constants (full double precision)
# --------------------------------------------------------------------------- #
PHI_00 = 0.5
PHI_01 = 0.5398278372770290
PHI_02 = 0.5792597094391030

PDF_00 = 0.3989422804014327
PDF_01 = 0.3969525474770118
PDF_02 = 0.3910426939754561

ABS = 1e-9


def close(a: float, b: float, tol: float = ABS) -> bool:
    return math.isclose(a, b, rel_tol=0.0, abs_tol=tol)


# --------------------------------------------------------------------------- #
# 0. Sanity: the constants we hard-code match the implementation's Phi/phi
# --------------------------------------------------------------------------- #
def test_normal_helpers_match_constants() -> None:
    assert close(norm_cdf(0.0), PHI_00)
    assert close(norm_cdf(0.1), PHI_01)
    assert close(norm_cdf(0.2), PHI_02)
    assert close(norm_cdf(-0.1), 1.0 - PHI_01)
    assert close(norm_cdf(-0.2), 1.0 - PHI_02)
    assert close(norm_pdf(0.0), PDF_00)
    assert close(norm_pdf(0.1), PDF_01)
    assert close(norm_pdf(0.2), PDF_02)
    # phi is symmetric
    assert close(norm_pdf(-0.2), PDF_02)


def test_d1_d2_geometry() -> None:
    d1, d2 = d1_d2(100.0, 100.0, 1.0, 0.2)
    assert close(d1, 0.1)
    assert close(d2, -0.1)
    d1b, d2b = d1_d2(100.0 * math.exp(0.02), 100.0, 1.0, 0.2)
    assert close(d1b, 0.2)
    assert close(d2b, 0.0)
    d1c, d2c = d1_d2(100.0 * math.exp(-0.02), 100.0, 1.0, 0.2)
    assert close(d1c, 0.0)
    assert close(d2c, -0.2)


# --------------------------------------------------------------------------- #
# 1. ATM, r = 0   (F=K=100, T=1, sigma=0.2 -> d1=+0.1, d2=-0.1)
# --------------------------------------------------------------------------- #
def test_atm_r0() -> None:
    F = K = 100.0
    T, r, s = 1.0, 0.0, 0.2

    # call = F*Phi(0.1) - K*Phi(-0.1) ; put = K*Phi(0.1) - F*Phi(-0.1)
    exp_call = F * PHI_01 - K * (1.0 - PHI_01)
    exp_put = K * PHI_01 - F * (1.0 - PHI_01)
    assert close(price("call", F, K, T, r, s), exp_call)
    assert close(price("put", F, K, T, r, s), exp_put)
    assert close(exp_call, 7.96556745540580)  # documented literal
    assert close(exp_call, exp_put)            # ATM, r=0 -> call == put

    assert close(delta("call", F, K, T, r, s), PHI_01)
    assert close(delta("put", F, K, T, r, s), PHI_01 - 1.0)
    assert close(gamma(F, K, T, r, s), PDF_01 / (F * s))      # phi/ (F*sigma*sqrt T)
    assert close(vega(F, K, T, r, s), F * PDF_01)             # F*phi*sqrt(T)
    # theta = -F*phi*sigma/(2 sqrt T)  (r=0)
    assert close(theta("call", F, K, T, r, s), -F * PDF_01 * s / 2.0)
    assert close(theta("put", F, K, T, r, s), -F * PDF_01 * s / 2.0)


# --------------------------------------------------------------------------- #
# 2. ATM, r = 0.05  (exercises discounting + the r-term in theta)
# --------------------------------------------------------------------------- #
def test_atm_discounted() -> None:
    F = K = 100.0
    T, r, s = 1.0, 0.05, 0.2
    disc = math.exp(-r * T)

    exp_call = disc * (F * PHI_01 - K * (1.0 - PHI_01))
    exp_put = disc * (K * PHI_01 - F * (1.0 - PHI_01))
    assert close(price("call", F, K, T, r, s), exp_call)
    assert close(price("put", F, K, T, r, s), exp_put)

    assert close(delta("call", F, K, T, r, s), disc * PHI_01)
    assert close(delta("put", F, K, T, r, s), disc * (PHI_01 - 1.0))
    assert close(gamma(F, K, T, r, s), disc * PDF_01 / (F * s))
    assert close(vega(F, K, T, r, s), disc * F * PDF_01)
    # theta = r*price - disc*F*phi*sigma/(2 sqrt T)
    decay = -disc * F * PDF_01 * s / 2.0
    assert close(theta("call", F, K, T, r, s), r * exp_call + decay)
    assert close(theta("put", F, K, T, r, s), r * exp_put + decay)


# --------------------------------------------------------------------------- #
# 3. ITM call / OTM put  (F = 100*exp(+0.02) -> d1=0.2, d2=0.0), r = 0
# --------------------------------------------------------------------------- #
def test_itm_call_otm_put() -> None:
    K = 100.0
    F = 100.0 * math.exp(0.02)
    T, r, s = 1.0, 0.0, 0.2

    # call = F*Phi(0.2) - K*Phi(0.0) ; put = K*Phi(0.0) - F*Phi(-0.2)
    exp_call = F * PHI_02 - K * PHI_00
    exp_put = K * PHI_00 - F * (1.0 - PHI_02)
    assert close(price("call", F, K, T, r, s), exp_call)   # ITM call
    assert close(price("put", F, K, T, r, s), exp_put)     # OTM put

    assert close(delta("call", F, K, T, r, s), PHI_02)
    assert close(delta("put", F, K, T, r, s), PHI_02 - 1.0)
    assert close(gamma(F, K, T, r, s), PDF_02 / (F * s))
    assert close(vega(F, K, T, r, s), F * PDF_02)
    assert close(theta("call", F, K, T, r, s), -F * PDF_02 * s / 2.0)


# --------------------------------------------------------------------------- #
# 4. OTM call / ITM put  (F = 100*exp(-0.02) -> d1=0.0, d2=-0.2), r = 0
# --------------------------------------------------------------------------- #
def test_otm_call_itm_put() -> None:
    K = 100.0
    F = 100.0 * math.exp(-0.02)
    T, r, s = 1.0, 0.0, 0.2

    # call = F*Phi(0.0) - K*Phi(-0.2) ; put = K*Phi(0.2) - F*Phi(0.0)
    exp_call = F * PHI_00 - K * (1.0 - PHI_02)
    exp_put = K * PHI_02 - F * PHI_00
    assert close(price("call", F, K, T, r, s), exp_call)   # OTM call
    assert close(price("put", F, K, T, r, s), exp_put)     # ITM put

    assert close(delta("call", F, K, T, r, s), PHI_00)
    assert close(delta("put", F, K, T, r, s), PHI_00 - 1.0)
    assert close(gamma(F, K, T, r, s), PDF_00 / (F * s))
    assert close(vega(F, K, T, r, s), F * PDF_00)
    assert close(theta("call", F, K, T, r, s), -F * PDF_00 * s / 2.0)


# --------------------------------------------------------------------------- #
# 5. Put-call parity:  C - P == exp(-r*T) * (F - K)
# --------------------------------------------------------------------------- #
_PARITY_CASES = [
    (100.0, 100.0, 1.0, 0.00, 0.20),
    (100.0, 100.0, 1.0, 0.05, 0.20),
    (120.0, 100.0, 0.5, 0.03, 0.35),
    (80.0, 100.0, 2.0, 0.07, 0.15),
    (4500.0, 4480.0, 0.25, 0.045, 0.18),   # /ES-scale
    (15800.0, 16000.0, 0.10, 0.045, 0.22),  # /NQ-scale
]


@pytest.mark.parametrize("F,K,T,r,s", _PARITY_CASES)
def test_put_call_parity(F: float, K: float, T: float, r: float, s: float) -> None:
    c = price("call", F, K, T, r, s)
    p = price("put", F, K, T, r, s)
    assert close(c - p, math.exp(-r * T) * (F - K))


@pytest.mark.parametrize("F,K,T,r,s", _PARITY_CASES)
def test_delta_parity(F: float, K: float, T: float, r: float, s: float) -> None:
    # call delta - put delta == exp(-r*T)
    dc = delta("call", F, K, T, r, s)
    dp = delta("put", F, K, T, r, s)
    assert close(dc - dp, math.exp(-r * T))


@pytest.mark.parametrize("F,K,T,r,s", _PARITY_CASES)
def test_gamma_vega_type_independent(F: float, K: float, T: float, r: float, s: float) -> None:
    # gamma & vega are positive and shared by both option kinds
    assert gamma(F, K, T, r, s) > 0.0
    assert vega(F, K, T, r, s) > 0.0


# --------------------------------------------------------------------------- #
# 5b. Vanna = d delta / d sigma  (finite-difference + closed form + parity)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("F,K,T,r,s", _PARITY_CASES)
def test_vanna_matches_fd_ddelta_dsigma(F: float, K: float, T: float, r: float, s: float) -> None:
    # Central finite difference of delta in sigma must match closed-form vanna.
    h = 1e-5
    fd = (
        delta("call", F, K, T, r, s + h) - delta("call", F, K, T, r, s - h)
    ) / (2.0 * h)
    assert math.isclose(vanna(F, K, T, r, s), fd, rel_tol=1e-5, abs_tol=1e-7)


@pytest.mark.parametrize("F,K,T,r,s", _PARITY_CASES)
def test_vanna_call_equals_put(F: float, K: float, T: float, r: float, s: float) -> None:
    # Put delta = call delta - exp(-rT) (sigma-independent), so vanna is shared.
    assert close(vanna(F, K, T, r, s), vanna(F, K, T, r, s))
    fd_put = (
        delta("put", F, K, T, r, s + 1e-5) - delta("put", F, K, T, r, s - 1e-5)
    ) / (2.0e-5)
    assert math.isclose(vanna(F, K, T, r, s), fd_put, rel_tol=1e-5, abs_tol=1e-7)


def test_vanna_closed_form_atm() -> None:
    # ATM r=0: d1=+0.1, d2=-0.1 -> vanna = -phi(0.1)*(-0.1)/0.2
    F = K = 100.0
    T, r, s = 1.0, 0.0, 0.2
    assert close(vanna(F, K, T, r, s), -PDF_01 * (-0.1) / s)


# --------------------------------------------------------------------------- #
# 5c. Charm = d delta / d t == -d delta / d T  (finite-difference + parity)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("F,K,T,r,s", _PARITY_CASES)
@pytest.mark.parametrize("ot", ["call", "put"])
def test_charm_matches_fd_ddelta_dt(ot: str, F: float, K: float, T: float, r: float, s: float) -> None:
    # charm = -d delta / d T via central finite difference in T.
    h = T * 1e-5
    fd = -(
        delta(ot, F, K, T + h, r, s) - delta(ot, F, K, T - h, r, s)
    ) / (2.0 * h)
    assert math.isclose(charm(ot, F, K, T, r, s), fd, rel_tol=1e-5, abs_tol=1e-6)


@pytest.mark.parametrize("F,K,T,r,s", _PARITY_CASES)
def test_charm_call_put_parity(F: float, K: float, T: float, r: float, s: float) -> None:
    # d/dt of (call delta - put delta == exp(-rT)) gives r*exp(-rT).
    assert close(
        charm("call", F, K, T, r, s) - charm("put", F, K, T, r, s),
        r * math.exp(-r * T),
    )


def test_charm_zero_when_rate_zero_atm_symmetry() -> None:
    # r=0: charm = phi(d1)*d2/(2T); call and put coincide (parity term vanishes).
    F = K = 100.0
    T, r, s = 1.0, 0.0, 0.2
    assert close(charm("call", F, K, T, r, s), charm("put", F, K, T, r, s))
    assert close(charm("call", F, K, T, r, s), PDF_01 * (-0.1) / (2.0 * T))


# --------------------------------------------------------------------------- #
# 6. Boundary / limit behaviour: well-defined, never NaN or inf
# --------------------------------------------------------------------------- #
def _all_finite(F: float, K: float, T: float, r: float, s: float) -> None:
    for ot in ("call", "put"):
        for fn in (price, delta, theta, charm):
            v = fn(ot, F, K, T, r, s)
            assert math.isfinite(v), (fn.__name__, ot, F, K, T, r, s, v)
    for fn in (gamma, vega, vanna):
        v = fn(F, K, T, r, s)
        assert math.isfinite(v), (fn.__name__, F, K, T, r, s, v)


def test_expired_returns_intrinsic() -> None:
    # T = 0: discounted intrinsic with discount factor 1
    assert price("call", 100.0, 95.0, 0.0, 0.05, 0.2) == 5.0
    assert price("put", 100.0, 95.0, 0.0, 0.05, 0.2) == 0.0
    assert price("put", 95.0, 100.0, 0.0, 0.05, 0.2) == 5.0
    assert delta("call", 100.0, 95.0, 0.0, 0.05, 0.2) == 1.0
    assert delta("put", 100.0, 95.0, 0.0, 0.05, 0.2) == 0.0
    assert delta("call", 90.0, 100.0, 0.0, 0.05, 0.2) == 0.0
    assert gamma(100.0, 95.0, 0.0, 0.05, 0.2) == 0.0
    assert vega(100.0, 95.0, 0.0, 0.05, 0.2) == 0.0
    assert theta("call", 100.0, 95.0, 0.0, 0.05, 0.2) == 0.0
    # at-the-money expiry delta -> midpoint sub-gradient
    assert close(delta("call", 100.0, 100.0, 0.0, 0.0, 0.2), 0.5)
    assert close(delta("put", 100.0, 100.0, 0.0, 0.0, 0.2), -0.5)


def test_zero_vol_deterministic_forward() -> None:
    F, K, T, r = 100.0, 95.0, 1.0, 0.05
    disc = math.exp(-r * T)
    assert close(price("call", F, K, T, r, 0.0), disc * 5.0)
    assert close(price("put", F, K, T, r, 0.0), 0.0)
    assert close(delta("call", F, K, T, r, 0.0), disc * 1.0)
    assert close(delta("put", F, K, T, r, 0.0), 0.0)
    assert gamma(F, K, T, r, 0.0) == 0.0
    assert vega(F, K, T, r, 0.0) == 0.0
    # theta = r * price  when sigma == 0
    assert close(theta("call", F, K, T, r, 0.0), r * disc * 5.0)
    assert close(theta("put", F, K, T, r, 0.0), 0.0)


@pytest.mark.parametrize(
    "F,K,T,r,s",
    [
        (100.0, 100.0, 1e-300, 0.05, 0.2),    # T -> 0+
        (100.0, 100.0, 1.0, 0.05, 1e-300),    # sigma -> 0+
        (100.0, 100.0, 1e-12, 0.05, 1e-12),   # both tiny
        (100.0, 1.0, 1.0, 0.05, 0.2),         # deep ITM call
        (1.0, 100.0, 1.0, 0.05, 0.2),         # deep OTM call
        (100.0, 100.0, 50.0, 0.05, 5.0),      # huge T & vol
        (4500.0, 4500.0, 1.0 / 252.0, 0.045, 0.6),  # 0DTE-ish /ES
    ],
)
def test_no_nan_at_boundaries(F: float, K: float, T: float, r: float, s: float) -> None:
    _all_finite(F, K, T, r, s)


def test_input_validation() -> None:
    with pytest.raises(ValueError):
        price("swap", 100.0, 100.0, 1.0, 0.0, 0.2)  # bad option type
    with pytest.raises(ValueError):
        price("call", 0.0, 100.0, 1.0, 0.0, 0.2)    # F <= 0
    with pytest.raises(ValueError):
        price("call", 100.0, -1.0, 1.0, 0.0, 0.2)   # K <= 0
