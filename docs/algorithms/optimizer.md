# Allocation engine (Phase 10)

Long-only mean-variance over the research universe (50 stocks, 15 funds) plus any fund the portfolio holds.
Settings: `config/optimizer.yaml`; caps: `config/recommendations.yaml` (shared with the recommendation engine).

## Problem
| Objective | Formula |
|---|---|
| `min_variance` (default) | minimise `wᵀΣw` |
| `balanced` | maximise `μ·w − λ/2 · wᵀΣw`, λ = 4 |

Subject to: `Σw = 1 − cash_floor` (cash held at the 5% floor), `0 ≤ wᵢ ≤ 20%`, and on look-through exposure
`E = H·w ≤ 15%` per company and `K·H·w ≤ 25%` per sector, where `H` is the company × asset matrix (identity
column for a stock, the latest published disclosure for a fund; see [exposure.md](exposure.md)) and `K` maps
companies to sectors. A fund without a disclosure has a zero column, so the caps cannot see inside it; it is
still limited by the 20% per-asset bound. All constraints are linear.

## Estimates (3 years of daily returns)
- `μ`: each asset's mean return shrunk 75% toward the cross-sectional mean. Raw means are too noisy to
  optimise on (they chase recent winners); the Phase 9 model shows no significant skill, so it is not used.
- `Σ`: sample covariance shrunk 20% toward its diagonal, for steadier weights.
- Assets with less than 80% of the window in history are left out (held ones are kept as they are).

## Solver
SciPy SLSQP with analytic gradients, started from a feasible point found by a linear programme (`linprog`);
the LP also reports cleanly when no allocation can meet every cap. Typical solve: under 0.1 s for ~65 assets.
Unit tests check closed-form cases: inverse-variance weights, a Lagrange balanced solution, a company cap
binding through a fund, the cash floor and infeasible caps (`backend/tests/test_optimizer.py`).

## Limits
Single-period, no transaction costs or taxes (Phase 12 adds costs and turnover), survivorship bias from
today's constituents, and look-through limited to funds with ingested disclosures.
