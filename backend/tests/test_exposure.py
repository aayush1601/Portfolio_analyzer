from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest
from openpyxl import Workbook

from app.analytics.exposure import UNMAPPED, effective_exposure, fund_analytics, latest_holdings, stress
from app.services.fund_holdings import ingest, norm

SECTORS = {"TCS": "Information Technology", "INFY": "Information Technology"}


def holdings(rows):
    return pd.DataFrame(
        rows, columns=["scheme_code", "as_of_month", "published_at", "isin", "symbol", "weight"]
    )


# Worked example from docs/algorithms/exposure.md: direct TCS 20%; fund A 30% (TCS 8%, INFY 6%);
# fund B 20% (TCS 4%, INFY 5%); 30% cash.
H = holdings(
    [
        ("A", "2026-08", date(2026, 9, 10), "INE467B01029", "TCS", 0.08),
        ("A", "2026-08", date(2026, 9, 10), "INE009A01021", "INFY", 0.06),
        ("B", "2026-08", date(2026, 9, 10), "INE467B01029", "TCS", 0.04),
        ("B", "2026-08", date(2026, 9, 10), "INE009A01021", "INFY", 0.05),
    ]
)


@pytest.fixture
def exp():
    return effective_exposure("p", date(2026, 10, 1), {"TCS": 0.2}, {"A": 0.3, "B": 0.2}, H, SECTORS)


def test_worked_example_companies(exp):
    tcs, infy = exp.companies
    assert (tcs.symbol, tcs.direct, tcs.indirect, tcs.effective) == ("TCS", 0.2, 0.032, 0.232)
    assert {(v.fund, v.contribution) for v in tcs.via} == {("A", 0.024), ("B", 0.008)}
    assert (infy.symbol, infy.effective) == ("INFY", 0.028)


def test_worked_example_sectors_overlap_hhi(exp):
    sectors = {s.sector: s for s in exp.sectors}
    assert sectors["Information Technology"].effective == pytest.approx(0.26)
    assert sectors["Information Technology"].direct == pytest.approx(0.2)
    # residual: 0.3·(1−0.14) + 0.2·(1−0.09) = 0.258 + 0.182 = 0.44; sectors then sum to 1 − cash = 0.7
    assert sectors[UNMAPPED].effective == pytest.approx(0.44) == exp.unmapped
    assert sum(s.effective for s in exp.sectors) == pytest.approx(0.7)
    assert exp.overlap[0].overlap == pytest.approx(0.09)  # min(8,4) + min(6,5)
    assert exp.hhi_effective == pytest.approx(0.054608)
    assert exp.holdings_as_of == {"A": "2026-08", "B": "2026-08"}


def test_fund_without_disclosure_counts_as_unmapped():
    e = effective_exposure("p", date(2026, 10, 1), {}, {"A": 0.3, "Z": 0.5}, H, SECTORS)
    assert e.unmapped == pytest.approx(0.258 + 0.5)
    assert "fund Z" in e.notes[0]


def test_latest_holdings_is_point_in_time():
    h = pd.concat(
        [H, holdings([("A", "2026-09", date(2026, 10, 10), "INE467B01029", "TCS", 0.5)])], ignore_index=True
    )
    assert set(latest_holdings(h, date(2026, 10, 9))["as_of_month"]) == {"2026-08"}  # Sep not published yet
    after = latest_holdings(h, date(2026, 10, 10))
    assert after[after["scheme_code"] == "A"]["as_of_month"].unique().tolist() == ["2026-09"]


def test_stress_is_linear_in_effective_sector_exposure(exp):
    r = stress(exp, {"Information Technology": -0.10, UNMAPPED: -0.05}, 1_000_000, "custom")
    # 0.26·−0.10 + 0.44·−0.05 = −0.026 − 0.022 = −0.048
    assert r.estimated_loss == pytest.approx(-0.048)
    assert r.estimated_loss_inr == pytest.approx(-48_000)
    assert [c.symbol for c in r.top_contributors] == ["TCS", UNMAPPED, "INFY"]


def sebi_sheet(wb, title, as_of, rows):
    ws = wb.create_sheet(title)
    ws.append([None, "XYZ Mutual Fund"])
    ws.append([None, "SCHEME NAME :", title + " (An open ended scheme)"])
    ws.append([None, "PORTFOLIO STATEMENT AS ON :", as_of])
    ws.append([])
    ws.append([None, "Name of the Instrument", "ISIN", "Industry", "Quantity", "% to Net Assets"])
    ws.append([None, "EQUITY & EQUITY RELATED"])
    for r in rows:
        ws.append([None, *r])
    ws.append([None, "Total", None, None, None, 100])


def test_ingest_generic_sebi_workbook(tmp_path):
    wb = Workbook()
    wb.remove(wb.active)
    sebi_sheet(
        wb,
        "Alpha Large Cap Fund",
        datetime(2026, 8, 31),
        [
            ("Tata Consultancy Services Ltd.", "INE467B01029", "IT - Software", 10, 6.5),
            ("Some Other Ltd.", "INE000X01010", "Banks", 5, 3.5),
            (
                "Tata Consultancy Services Ltd.",
                "INE467B01029",
                "IT - Software",
                1,
                0.5,
            ),  # duplicate ISIN: summed
            ("TREPS", None, None, None, 2.0),  # no ISIN: not a holding row
        ],
    )
    sebi_sheet(wb, "Not In Universe Fund", "31-Aug-2026", [("X", "INE000X01010", "Banks", 1, 100)])
    (tmp_path / "xyz").mkdir()
    wb.save(tmp_path / "xyz" / "aug.xlsx")

    out = ingest(tmp_path, {norm("Alpha Large Cap Fund"): "999"}, {"INE467B01029": "TCS"})
    assert out["scheme_code"].unique().tolist() == ["999"]
    assert out["as_of_month"].unique().tolist() == ["2026-08"]
    assert out["published_at"].iloc[0] == date(2026, 9, 10)  # month-end + SEBI's 10-day deadline
    tcs = out[out["isin"] == "INE467B01029"].iloc[0]
    assert (tcs["symbol"], tcs["weight"]) == ("TCS", pytest.approx(0.07))
    assert out[out["isin"] == "INE000X01010"]["symbol"].isna().all()


def test_fund_analytics_returns_and_cagr():
    idx = pd.bdate_range("2021-01-01", "2026-10-01")
    nav = pd.Series(100 * 1.0002 ** np.arange(len(idx)), index=idx)
    market = nav.pct_change()
    meta = {"scheme_code": 1, "name": "F", "amc": "A", "category": "C", "expense_ratio": 0.01}
    f = fund_analytics(meta, nav, market, 0.06, H[H["scheme_code"] == "A"].assign(industry="IT", name="n"))
    one_year_ago = nav[: idx[-1] - pd.DateOffset(years=1)].iloc[-1]
    assert f.returns["cagr_1y"] == pytest.approx(nav.iloc[-1] / one_year_ago - 1)
    assert f.returns["1d"] == pytest.approx(0.0002)
    assert f.risk.beta == pytest.approx(1.0)
    assert f.holdings_as_of == "2026-08" and f.top_holdings[0].symbol == "TCS"
    assert f.sector_mix[0].weight == pytest.approx(0.14)
    assert any("aum" in n for n in f.notes)


def test_fund_analytics_before_any_disclosure_is_ingested():
    from app.services.fund_holdings import COLUMNS

    nav = pd.Series([10.0, 10.1, 10.2], index=pd.bdate_range("2026-09-29", periods=3))
    f = fund_analytics(
        {"scheme_code": 1, "name": "F", "amc": "A", "category": "C"},
        nav,
        nav.pct_change(),
        None,
        pd.DataFrame(columns=COLUMNS),
    )
    assert f.top_holdings == [] and f.sector_mix == [] and f.holdings_as_of is None
