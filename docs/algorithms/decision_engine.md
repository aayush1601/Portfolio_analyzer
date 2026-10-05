# Decision engine (Phase 11 full)

Turns every signal into one explained action per holding. Settings: `config/recommendations.yaml` (v2).

## Components (each 0–100, higher favours keeping or adding)
| Component | Source | Weight |
|---|---|---|
| news | exposure-weighted FinBERT sentiment, shrunk by evidence (Phase 7–8) | 0.20 |
| risk | 1-year volatility, 10% → 100, 50% → 0 (Phase 4) | 0.20 |
| portfolio_fit | distance from the company / sector caps on look-through exposure, or fund overlap (Phase 5) | 0.25 |
| allocation | gap to the Phase 10 model allocation: `50 + 50·clip((target − current) / 0.10, −1, 1)` | 0.35 |
| expected_return | Phase 9 model rank with SHAP drivers; **weight 0** until it shows significant skill | 0 |

`final_score` is the weighted mean of the components that exist. ≥ 65 → BUY / INCREASE, ≤ 35 → REDUCE,
otherwise HOLD; adding needs at least two scored components.

## Safety rules (applied last; they can only make an action more cautious)
- Effective company exposure above 15% → REDUCE; a sector at or above 25% blocks BUY / INCREASE.
- A fund that would add exposure to a company or sector already at a cap cannot be INCREASEd.
- An overridden call stays visible (`blocked_action`), with the rule that overrode it.

## SWITCH (funds)
1. The model allocation drops the fund (target 0) and gives weight to a fund of the same category you do not
   hold → SWITCH to the one it gives most.
2. Otherwise, two held funds overlapping ≥ 50% → the smaller switches to the same-category fund that overlaps
   least with your other funds.

## Additions
Assets you do not hold that the model allocation gives at least 3% are listed as "worth considering", with
their target weight and rupee amount. They satisfy every cap by construction.

## Honest limits
The allocation component inherits the optimiser's assumptions (3-year estimates, no costs or taxes,
survivorship bias); with min-variance as the goal it pushes toward low-volatility holdings and can call for
large turnover. Whether any of this helps is what the Phase 12 backtest and ablation measure.
