"""Allocation engine (Phase 10): long-only mean-variance with caps on look-through exposure.

maximise   μ·w − λ/2 · wᵀΣw          (balanced)     or   minimise  wᵀΣw   (min_variance)
subject to Σw = 1 − cash_floor,  0 ≤ wᵢ ≤ max_asset,  H·w ≤ company cap,  K·H·w ≤ sector cap

Each fund is one asset (its NAV returns); H maps assets to the companies they hold (identity for a stock,
the latest published disclosure for a fund), so the caps see through funds (docs/algorithms/exposure.md).
"""

import numpy as np
import pandas as pd
from scipy.optimize import linprog, minimize

TRADING_DAYS = 252


def shrunk_mu(R: pd.DataFrame, alpha: float) -> pd.Series:
    """Annual mean return per asset, shrunk toward the cross-sectional mean (James-Stein style)."""
    m = R.mean() * TRADING_DAYS
    return (1 - alpha) * m + alpha * m.mean()


def shrunk_cov(R: pd.DataFrame, delta: float) -> pd.DataFrame:
    """Annual covariance, shrunk toward its own diagonal: (1 − δ)·S + δ·diag(S)."""
    S = R.cov() * TRADING_DAYS
    return (1 - delta) * S + delta * pd.DataFrame(np.diag(np.diag(S)), index=S.index, columns=S.columns)


def lookthrough_matrix(
    assets: list[str], stocks: set[str], holdings: pd.DataFrame
) -> tuple[pd.DataFrame, list[str]]:
    """H (company × asset). Returns H and the funds whose look-through is unknown (no disclosure)."""
    companies = sorted({a for a in assets if a in stocks} | set(holdings["symbol"].dropna()) & stocks)
    H = pd.DataFrame(0.0, index=companies, columns=assets)
    unknown = []
    for a in assets:
        if a in stocks:
            H.loc[a, a] = 1.0
            continue
        h = holdings[(holdings["scheme_code"] == a) & holdings["symbol"].isin(companies)]
        if h.empty:
            unknown.append(a)
        for r in h.groupby("symbol")["weight"].sum().items():
            H.loc[r[0], a] = r[1]
    return H, unknown


def optimize(
    mu: pd.Series,
    Sigma: pd.DataFrame,
    H: pd.DataFrame,
    sector_of: dict[str, str],
    *,
    risk_aversion: float | None,
    max_asset: float,
    cash_floor: float,
    caps: dict[str, float],
) -> tuple[pd.Series, list[str]]:
    """Target weights (index = assets) and the constraints they bind on."""
    assets = list(mu.index)
    n = len(assets)
    m, S = mu.to_numpy(), Sigma.loc[assets, assets].to_numpy()
    Hm = H[assets].to_numpy()
    sectors = sorted({sector_of[c] for c in H.index})
    K = np.array([[1.0 if sector_of[c] == k else 0.0 for c in H.index] for k in sectors]).reshape(
        len(sectors), len(H.index)
    )
    KH = K @ Hm
    budget = 1 - cash_floor
    if n * max_asset < budget - 1e-9:
        raise ValueError(f"{n} assets × {max_asset:.0%} max each cannot fill {budget:.0%} of the portfolio")

    # Annual variances are ~0.01: scaling the objective keeps SLSQP's line search well conditioned.
    scale = 100.0
    if risk_aversion is None:  # minimum variance

        def f(x):
            return scale * 0.5 * x @ S @ x, scale * (S @ x)
    else:

        def f(x):
            return scale * (-m @ x + 0.5 * risk_aversion * x @ S @ x), scale * (-m + risk_aversion * S @ x)

    cons = [{"type": "eq", "fun": lambda x: x.sum() - budget, "jac": lambda x: np.ones(n)}]
    if len(Hm):
        cons.append({"type": "ineq", "fun": lambda x: caps["company"] - Hm @ x, "jac": lambda x: -Hm})
    if len(KH):
        cons.append({"type": "ineq", "fun": lambda x: caps["sector"] - KH @ x, "jac": lambda x: -KH})
    # Start SLSQP from a point that already meets every cap (a quick LP); from an infeasible start its line
    # search can stall. The LP also tells us cleanly when no allocation can satisfy the caps.
    A_ub = np.vstack([Hm, KH]) if len(Hm) else None
    b_ub = np.r_[np.full(len(Hm), caps["company"]), np.full(len(KH), caps["sector"])] if len(Hm) else None
    lp = linprog(
        np.zeros(n), A_ub=A_ub, b_ub=b_ub, A_eq=np.ones((1, n)), b_eq=[budget], bounds=[(0, max_asset)] * n
    )
    if not lp.success:
        raise ValueError("no allocation can satisfy every cap at once; loosen a cap or add assets")
    x0 = lp.x
    res = minimize(f, x0, jac=True, method="SLSQP", bounds=[(0, max_asset)] * n, constraints=cons,
                   options={"maxiter": 1000, "ftol": 1e-10})  # fmt: skip
    if not res.success:
        raise ValueError(f"the optimiser could not satisfy every cap: {res.message}")
    x = np.where(res.x < 1e-6, 0.0, res.x)
    x *= budget / x.sum()

    tol = 1e-4
    binding = [
        f"max {max_asset:.0%} per asset: {a}" for a, v in zip(assets, x, strict=True) if v > max_asset - tol
    ]
    binding += [
        f"company cap: {c}" for c, v in zip(H.index, Hm @ x, strict=True) if v > caps["company"] - tol
    ]
    binding += [f"sector cap: {k}" for k, v in zip(sectors, KH @ x, strict=True) if v > caps["sector"] - tol]
    return pd.Series(x, index=assets), binding


def stats(w: pd.Series, mu: pd.Series, Sigma: pd.DataFrame, cash: float, rf: float) -> tuple[float, float]:
    """(annual expected return, annual volatility) of risky weights w plus cash earning rf."""
    a = list(w.index)
    return float(mu[a] @ w + cash * rf), float(np.sqrt(w @ Sigma.loc[a, a].to_numpy() @ w))


def effective_sectors(w: pd.Series, H: pd.DataFrame, sector_of: dict[str, str]) -> pd.Series:
    """Look-through sector exposure of risky weights w (companies in universe only)."""
    e = H[list(w.index)].to_numpy() @ w.to_numpy()
    return pd.Series(e, index=H.index).groupby(sector_of).sum()
