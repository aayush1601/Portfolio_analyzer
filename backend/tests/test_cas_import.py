import json

import httpx
import pytest

from app.services import cas_import as cas
from app.services.market_data import save
from app.services.nav_data import load_navs
from tests.test_portfolio import NAVS, client  # noqa: F401  (client is a fixture)


def scheme(amfi, units, value, cost, name="Fund"):
    return {
        "scheme": name,
        "amfi": amfi,
        "close": units,
        "valuation": {"date": "2026-09-30", "nav": 1, "value": value, "cost": cost},
    }


CAS = {
    "statement_period": {"from": "01-Jan-2020", "to": "30-Sep-2026"},
    "folios": [
        {
            "folio": "1/23",
            "amc": "A",
            "schemes": [
                scheme("120594", 100, 19140, 18000, "ICICI Tech"),
                scheme("999001", 0, 0, 0, "Closed"),
            ],
        },
        {
            "folio": "4/56",
            "amc": "A",
            "schemes": [scheme("120594", 50, 9570, 9500, "ICICI Tech")],
        },  # same scheme, other folio
        {
            "folio": "7/89",
            "amc": "B",
            "schemes": [scheme("", 10, 100, 90, "No code fund"), scheme("150000", 20, 400, None, "Outside")],
        },
    ],
}


def test_funds_from_cas_aggregates_across_folios_and_skips_closed_and_uncoded():
    funds, skipped = cas.funds_from_cas(CAS)
    by = {f.scheme_code: f for f in funds}
    assert set(by) == {"120594", "150000"}  # closed scheme dropped
    assert (by["120594"].units, by["120594"].value, by["120594"].cost) == (150, 28710, 27500)
    assert by["150000"].cost is None
    assert skipped == ["No code fund"]


def test_parse_cas_rejects_non_pdf_and_oversize():
    with pytest.raises(cas.CASImportError, match="isn't a PDF"):
        cas.parse_cas(b"hello", "ABCDE1234F")
    with pytest.raises(cas.CASImportError, match="over 10 MB"):
        cas.parse_cas(b"%PDF" + b"0" * cas.MAX_PDF_BYTES, "x")


def test_register_funds_appends_navs_and_records_metadata(tmp_path):
    save(NAVS, tmp_path / "processed" / "nav")
    payload = {
        "meta": {
            "scheme_name": "Outside Fund - Direct Growth",
            "fund_house": "B MF",
            "scheme_category": "Equity Scheme - Small Cap Fund",
        },
        "data": [{"date": "01-10-2026", "nav": "21.5"}, {"date": "30-09-2026", "nav": "21.0"}],
    }
    client_ = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    reg = cas.register_funds(["150000"], tmp_path, client_)
    assert reg["150000"]["category"] == "Small Cap Fund"
    assert json.loads(cas.registry_path(tmp_path).read_text())["150000"]["amc"] == "B MF"
    navs = load_navs(tmp_path)
    assert set(navs["scheme_code"]) == {"120594", "150000"}  # existing NAVs kept
    assert cas.register_funds(["150000"], tmp_path, client_) == reg  # already registered: no refetch


def test_import_endpoint_creates_a_portfolio_and_completes_the_phone_session(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(cas, "parse_cas", lambda data, pw: CAS)
    monkeypatch.setattr(cas, "register_funds", lambda codes, d, c: {"150000": {"name": "Outside Fund"}})
    files = {"file": ("cas.pdf", b"%PDF-1.4 fake", "application/pdf")}

    assert client.post("/import", files=files, data={"password": "x", "token": "nope"}).status_code == 403

    s = client.post("/import/session?port=5173").json()
    assert s["phone_url"].endswith(f"#/import/{s['token']}") and s["qr_svg"].startswith("<svg")
    r = client.post(
        "/import", files=files, data={"password": "ABCDE1234F", "token": s["token"], "name": "Mine"}
    )
    assert r.status_code == 201
    body = r.json()
    assert [f["scheme_code"] for f in body["funds"]] == ["120594", "150000"]  # by value
    assert body["funds"][1]["in_universe"] is False and body["skipped"] == ["No code fund"]
    assert client.get(f"/import/session/{s['token']}").json()["portfolio_id"] == body["portfolio_id"]

    unnamed = client.post(
        "/import", files=files, data={"password": "x", "token": s["token"]}
    )  # no name given
    assert unnamed.status_code == 201
    names = {p["portfolio_id"]: p["name"] for p in client.get("/portfolio").json()}
    assert names[unnamed.json()["portfolio_id"]] == "Imported funds (30-Sep-2026)"

    from app.api.portfolio import get_store

    saved = {h.asset_id: h for h in get_store().get("local", body["portfolio_id"]).holdings}
    assert saved["120594"].quantity == 150 and saved["120594"].avg_cost == pytest.approx(
        27500 / 150, abs=1e-4
    )
    assert saved["150000"].avg_cost == pytest.approx(400 / 20)  # no cost in statement: today's value


MFC_PAGE = """Consolidated Account Summary
( As on Date: 16-Oct-2026 )
MFCentralCASSummary_v2.1_1_ALL-16/10/2026 1:33:31pm Page 3 of 3
Units Client Id Scheme Details NAV Date NAV
HDFC Flexi Cap Fund - Regular Plan - Growth 1,42,000.00 1,39,408.00 (2,592.00)
(-1.83%) 36119364 70.460 15-Oct-2026 1,978.541
Bandhan Small Cap Fund-Direct Plan-
Growth
1,50,000.00 1,63,809.64 13,809.64
(+9.21%) 6516819 2,902.985 15-Oct-2026 56.428
Total 3,03,217.64"""


def test_parse_mfcentral_summary_resolves_names_by_nav():
    navs = {"101762": "1978.54100", "147946": "56.42800"}  # any other candidate code has no matching NAV

    def mfapi(r):
        code = r.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json={"data": [{"date": "15-10-2026", "nav": navs.get(code, "1.0")}]})

    parsed = cas.parse_mfcentral_summary([MFC_PAGE], httpx.Client(transport=httpx.MockTransport(mfapi)))
    funds, skipped = cas.funds_from_cas(parsed)
    by = {f.scheme_code: f for f in funds}
    assert set(by) == {"101762", "147946"} and skipped == []
    assert (by["101762"].units, by["101762"].cost, by["101762"].value) == (70.46, 142000, 139408)
    assert by["147946"].name == "Bandhan Small Cap Fund-Direct Plan- Growth"
    assert parsed["statement_period"]["to"] == "16-Oct-2026"
