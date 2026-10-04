from datetime import UTC, datetime

from app.services.nav_data import parse_mfapi


def test_parse_mfapi_sorts_cleans_and_sets_available_at():
    payload = {
        "data": [
            {"date": "01-10-2026", "nav": "112.29"},
            {"date": "30-09-2026", "nav": "0"},
            {"date": "29-09-2026", "nav": "x"},
            {"date": "01-10-2026", "nav": "112.29"},
        ]
    }
    df = parse_mfapi(payload, "120586")
    assert df["nav"].tolist() == [112.29]  # zero, unparseable and duplicate rows dropped
    assert df["scheme_code"].iloc[0] == "120586"
    assert df["available_at"].iloc[0] == datetime(2026, 10, 1, 17, 30, tzinfo=UTC)  # 23:00 IST
