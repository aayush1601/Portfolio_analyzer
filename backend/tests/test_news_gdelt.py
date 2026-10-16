import re
from datetime import date

import pandas as pd
import pytest

from app.config import REPO_ROOT, Settings
from app.services import news_gdelt as g
from app.services.news_pipeline import load_news

CONFIG = REPO_ROOT / "config"


def test_re2_escape_leaves_spaces_and_ampersands():
    # RE2 rejects "\ " and "\&", which Python's re.escape would produce
    assert g.re2_escape("Dr. Reddy's") == r"Dr\. Reddy's"
    assert g.re2_escape("M&M (India)") == r"M&M \(India\)"


def test_query_targets_the_publishers_dates_and_universe():
    sql = g.build_query(CONFIG, date(2022, 1, 1), date(2023, 1, 1))
    assert "`gdelt-bq.gdeltv2.gkg_partitioned`" in sql
    assert "_PARTITIONTIME >= TIMESTAMP('2022-01-01')" in sql
    assert "'economictimes.indiatimes.com'" in sql
    assert "Infosys" in sql and "Nifty IT" in sql
    company_re = re.search(r"REGEXP_CONTAINS\(title, r'''(.*?)'''\)", sql).group(1)
    pattern = re.compile(company_re)  # RE2 syntax used here is a subset Python also accepts
    assert pattern.search("Infosys Q2 results beat estimates")
    assert not pattern.search("Infosysland is not a company")


def write_csv(path, rows):
    pd.DataFrame(rows, columns=["seen_at", "domain", "url", "title"]).to_csv(path, index=False)


def test_import_builds_raw_and_history_stores(tmp_path):
    data = tmp_path / "data"
    s = Settings(data_dir=data, config_dir=CONFIG)
    csv = tmp_path / "gdelt.csv"
    write_csv(
        csv,
        [
            ["2023-03-01T04:15:00Z", "livemint.com", "https://livemint.com/a", "Infosys Q4 profit rises 8%"],
            ["2023-03-01T04:15:00Z", "livemint.com", "https://livemint.com/a", "Infosys Q4 profit rises 8%"],
            ["2023-04-02T10:30:00Z", "moneycontrol.com", "https://mc.com/b", "SBI Card hikes fees"],
            ["2023-04-02T11:00:00Z", "moneycontrol.com", "https://mc.com/c", ""],
        ],
    )
    items = g.read_rows([csv])
    assert len(items) == 2  # the duplicate URL and the empty title are dropped
    g.write_raw(items, data / "raw" / "news" / "gdelt")
    g.write_raw(items, data / "raw" / "news" / "gdelt")  # re-import must not duplicate
    assert sorted(p.name for p in (data / "raw" / "news" / "gdelt").iterdir()) == [
        "2023-03.jsonl",
        "2023-04.jsonl",
    ]
    assert len((data / "raw" / "news" / "gdelt" / "2023-03.jsonl").read_text().splitlines()) == 1

    # "SBI Card" is a stop phrase, so only the Infosys article names a company and survives
    assert g.build_history(s) == 1
    news = load_news(data)
    row = news.iloc[0]
    assert row["symbols"].tolist() == ["INFY"]
    assert row["source"] == "gdelt:livemint.com"
    assert row["reliability"] == pytest.approx(0.85)
    assert row["published_at"] == pd.Timestamp("2023-03-01T04:15:00Z")  # when GDELT saw it: never early
    assert not row["published_at_estimated"]


def test_load_news_merges_live_and_history_once(tmp_path):
    from app.services.market_data import save

    def store(ids, day):
        t = pd.Timestamp(day, tz="UTC")
        return pd.DataFrame(
            {
                "news_id": ids,
                "headline": ids,
                "published_at": [t] * len(ids),
                "date": [t.tz_localize(None)] * len(ids),
            }
        )

    save(store(["live", "both"], "2026-10-10"), tmp_path / "processed" / "news")
    save(store(["old", "both"], "2023-01-05"), tmp_path / "processed" / "news_history")
    ids = load_news(tmp_path)["news_id"].tolist()
    assert sorted(ids) == ["both", "live", "old"]  # "both" appears once
    assert ids[0] == "old"  # sorted by time
