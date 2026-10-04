# Look-through (direct + indirect) exposure

## Definitions
- `w_i` = portfolio weight of asset *i* (stock, fund or cash), by market value; Σ w_i = 1.
- `h_{f,s}` = weight of stock *s* inside fund *f*, from the latest **published** disclosure. Σ_s h_{f,s} ≤ 1, because funds also hold cash, debt and non-universe stocks.

| Quantity | Formula |
|---|---|
| Effective company exposure | `E_s = w_s^direct + Σ_f w_f · h_{f,s}` |
| Indirect part | `I_s = Σ_f w_f · h_{f,s}` |
| Effective sector exposure | `E_k = Σ_s E_s · 1[sector(s) = k]`; the unmapped fund residual `Σ_f w_f (1 − Σ_s h_{f,s})` goes to "Other/Unmapped" so sectors sum to 1 − cash |
| Fund overlap (pairwise) | `Overlap(A,B) = Σ_s min(h_{A,s}, h_{B,s})` |
| Concentration | `HHI = Σ_s E_s²`; effective number of holdings `N_eff = 1 / HHI` |

## Worked example (this becomes `test_effective_exposure`)
Direct TCS = 20%; Fund A = 30% (TCS 8%, INFY 6%); Fund B = 20% (TCS 4%, INFY 5%).

| | Direct | via A | via B | **Effective** |
|---|---|---|---|---|
| TCS | 20.0% | 30%×8% = 2.4% | 20%×4% = 0.8% | **23.2%** |
| INFY | 0.0% | 30%×6% = 1.8% | 20%×5% = 1.0% | **2.8%** |
| IT sector (TCS + INFY only) | 20.0% | 4.2% | 1.8% | **26.0%** |

Overlap(A, B) over these two stocks = min(8, 4) + min(6, 5) = **9%**.
HHI over these two names only = 0.232² + 0.028² = 0.053824 + 0.000784 = **0.054608**.

## Point-in-time rule
Holdings for month *m* are published ~10 days after month-end. At date *t*, use the latest disclosure with `published_at ≤ t`. Never use the month-end date itself.

## How it is used downstream
- **Risk / stress:** sector shocks are applied to `E_k`, not to direct weights.
- **News impact:** an article about stock *s* affects the portfolio in proportion to `E_s`, so a fund-only holder is still affected.
- **Optimiser:** each fund is optimised as **one asset** (its NAV return series), while the sector/company caps are enforced on look-through `E_k`/`E_s`. This is linear in `w`: `E = H w`, where `H` is the stock×asset matrix (identity columns for direct stocks, `h_{f,·}` for funds).
- **Decision engine:** never recommend BUY/INCREASE for an asset whose increase would push any `E_s` or `E_k` above its cap.
