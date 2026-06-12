"""
FlowDesk — Validasi greeks Black-76 (options on futures).
Membuktikan ulang: harga, delta, gamma, vega, VANNA, CHARM, parity,
dan round-trip IV. Greeks analitik dicocokkan dengan finite-difference.
TANPA dependensi eksternal (hanya math) — jalankan: python black76_validate.py

Konvensi:
  F = harga futures (forward), K = strike, T = waktu (tahun), sigma = IV,
  r = ln(1+SOFR) -> continuously compounded.
  Black-76: diskon e^{-rT}, underlying log-normal pada forward.

Greeks yang dikunci (LOCKED):
  d1 = (ln(F/K) + 0.5*sigma^2*T) / (sigma*sqrt(T)); d2 = d1 - sigma*sqrt(T)
  Delta_call = e^{-rT} N(d1);   Delta_put = -e^{-rT} N(-d1)
  Gamma      = e^{-rT} phi(d1) / (F*sigma*sqrt(T))
  Vega       = F e^{-rT} phi(d1) sqrt(T)
  Vanna      = dDelta/dsigma = -e^{-rT} phi(d1) d2 / sigma   (call == put)
  Charm_call = dDelta/dt = r e^{-rT} N(d1) + e^{-rT} phi(d1) d2 / (2T)
  Charm_put  = Charm_call - r e^{-rT}
  (t = waktu kalender; dDelta/dt, BUKAN dDelta/dT)
"""
import math

SQRT_2PI = math.sqrt(2.0 * math.pi)


def phi(x):
    """PDF normal standar."""
    return math.exp(-0.5 * x * x) / SQRT_2PI


def N(x):
    """CDF normal standar via erf (tanpa scipy)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def d1_d2(F, K, T, sigma):
    v = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / v
    d2 = d1 - v
    return d1, d2


def price(F, K, T, sigma, r, call=True):
    d1, d2 = d1_d2(F, K, T, sigma)
    disc = math.exp(-r * T)
    if call:
        return disc * (F * N(d1) - K * N(d2))
    return disc * (K * N(-d2) - F * N(-d1))


def delta(F, K, T, sigma, r, call=True):
    d1, _ = d1_d2(F, K, T, sigma)
    disc = math.exp(-r * T)
    return disc * N(d1) if call else -disc * N(-d1)


def gamma(F, K, T, sigma, r):
    d1, _ = d1_d2(F, K, T, sigma)
    return math.exp(-r * T) * phi(d1) / (F * sigma * math.sqrt(T))


def vega(F, K, T, sigma, r):
    d1, _ = d1_d2(F, K, T, sigma)
    return F * math.exp(-r * T) * phi(d1) * math.sqrt(T)


def vanna(F, K, T, sigma, r):
    """dDelta/dsigma. Sama untuk call & put."""
    d1, d2 = d1_d2(F, K, T, sigma)
    return -math.exp(-r * T) * phi(d1) * d2 / sigma


def charm(F, K, T, sigma, r, call=True):
    """dDelta/dt (t = waktu kalender, naik). Catatan: T turun saat t naik."""
    d1, d2 = d1_d2(F, K, T, sigma)
    disc = math.exp(-r * T)
    base = r * disc * N(d1) + disc * phi(d1) * d2 / (2.0 * T)
    return base if call else base - r * disc


def implied_vol(target, F, K, T, r, call=True, tol=1e-8, max_iter=100):
    """Newton -> fallback bisection. Mengembalikan sigma yang memulihkan harga target."""
    sigma = 0.2
    for _ in range(max_iter):
        p = price(F, K, T, sigma, r, call)
        v = vega(F, K, T, sigma, r)
        if v < 1e-12:
            break
        diff = p - target
        if abs(diff) < tol:
            return sigma
        sigma -= diff / v
        if sigma <= 1e-6 or sigma > 5.0:
            break
    lo, hi = 1e-6, 5.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if price(F, K, T, mid, r, call) > target:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def fd_vanna(F, K, T, sigma, r, h=1e-5):
    return (delta(F, K, T, sigma + h, r) - delta(F, K, T, sigma - h, r)) / (2 * h)


def fd_charm(F, K, T, sigma, r, h=1e-6, call=True):
    # dDelta/dt = -dDelta/dT (t naik <=> T turun)
    up = delta(F, K, T - h, sigma, r, call)
    dn = delta(F, K, T + h, sigma, r, call)
    return (up - dn) / (2 * h)


def fd_gamma(F, K, T, sigma, r, h=1e-3):
    return (delta(F + h, K, T, sigma, r) - delta(F - h, K, T, sigma, r)) / (2 * h)


def run_case(name, F, K, T, sigma, r):
    print(f"\n=== {name} ===")
    print(f"F={F} K={K} T={T:.6f} sigma={sigma} r={r:.10f}")
    g_an, g_fd = gamma(F, K, T, sigma, r), fd_gamma(F, K, T, sigma, r)
    v_an, v_fd = vanna(F, K, T, sigma, r), fd_vanna(F, K, T, sigma, r)
    c_an, c_fd = charm(F, K, T, sigma, r), fd_charm(F, K, T, sigma, r)
    print(f"gamma : analytic={g_an: .10e} fd={g_fd: .10e} |diff|={abs(g_an-g_fd):.2e}")
    print(f"vanna : analytic={v_an: .10e} fd={v_fd: .10e} |diff|={abs(v_an-v_fd):.2e}")
    print(f"charm : analytic={c_an: .10e} fd={c_fd: .10e} |diff|={abs(c_an-c_fd):.2e}")
    # parity: c - p = e^{-rT}(F - K)
    c = price(F, K, T, sigma, r, True)
    p = price(F, K, T, sigma, r, False)
    parity = (c - p) - math.exp(-r * T) * (F - K)
    print(f"parity c-p-e^(-rT)(F-K) = {parity:.2e}")
    # round-trip IV
    iv = implied_vol(c, F, K, T, r, True)
    print(f"round-trip IV: input={sigma} recovered={iv:.10f} |diff|={abs(iv-sigma):.2e}")


if __name__ == "__main__":
    r = math.log(1.036)  # SOFR ~3.6% -> r=ln(1+SOFR)
    print(f"r = ln(1.036) = {r:.10f}")
    run_case("ATM 1DTE /ES", F=5000.0, K=5000.0, T=1/365.0, sigma=0.20, r=r)
    run_case("OTM 1DTE /ES", F=5000.0, K=5050.0, T=1/365.0, sigma=0.20, r=r)
    run_case("ITM 0.5DTE /NQ", F=18000.0, K=17900.0, T=0.5/365.0, sigma=0.25, r=r)
    print("\nSemua greek analitik harus cocok finite-difference hingga ~1e-6 atau lebih ketat.")
