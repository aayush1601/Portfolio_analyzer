"""Phase 0 feasibility spike. Throw-away code: proves each data source exists.

Run:  .venv/bin/python spikes/check_sources.py
Optional: ALPHAVANTAGE_API_KEY in env (or .env) to test news coverage.
"""
import os
import time
from pathlib import Path

import requests
import yfinance as yf

TIMEOUT = 30


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def check_prices() -> None:
    section("1. yfinance prices")
    tickers = ["TCS.NS", "INFY.NS", "RELIANCE.NS", "HDFCBANK.NS", "^NSEI", "^INDIAVIX"]
    px = yf.download(tickers, start="2015-01-01", auto_adjust=True, progress=False)
    close = px["Close"]
    print("shape:", close.shape, "range:", close.index.min().date(), "->", close.index.max().date())
    for t in tickers:
        s = close[t].dropna()
        print(f"  {t:12s} first={s.index.min().date() if len(s) else None} rows={len(s)} "
              f"missing_after_first={close[t].loc[s.index.min():].isna().sum() if len(s) else 'n/a'}")


def check_amfi() -> None:
    section("2. AMFI NAVAll.txt")
    r = requests.get("https://www.amfiindia.com/spages/NAVAll.txt", timeout=TIMEOUT)
    lines = [ln for ln in r.text.splitlines() if ln.count(";") >= 5]
    print("status:", r.status_code, "data lines:", len(lines))
    print("header:", lines[0])
    print("sample:", lines[1])


def check_mfapi() -> None:
    section("3. mfapi.in search + NAV history")
    for q in ["UTI Nifty 50 Index Fund Direct Growth", "Parag Parikh Flexi Cap Direct Growth"]:
        hits = requests.get("https://api.mfapi.in/mf/search", params={"q": q}, timeout=TIMEOUT).json()
        print(f"search '{q}': {len(hits)} hits; first: {hits[:1]}")
        if hits:
            nav = requests.get(f"https://api.mfapi.in/mf/{hits[0]['schemeCode']}", timeout=TIMEOUT).json()
            data = nav["data"]
            print(f"  meta: {nav['meta']}")
            print(f"  NAV points={len(data)} oldest={data[-1]} latest={data[0]}")


def check_gdelt() -> None:
    section("6. GDELT DOC 2.0 (fallback news)")
    # GDELT allows 1 request / 5 s. Last query probes history depth (DOC API is a rolling window).
    queries = [('"Tata Consultancy Services"', {"timespan": "1w"}),
               ('"Infosys"', {"timespan": "1w"}),
               ('"HDFC Bank"', {"timespan": "1w"}),
               ('"Infosys"', {"startdatetime": "20240101000000", "enddatetime": "20240131000000"})]
    for q, window in queries:
        time.sleep(20)
        r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", params={
            "query": f"{q} sourcelang:english", "mode": "artlist", "maxrecords": 50,
            "format": "json", **window}, timeout=TIMEOUT)
        q = f"{q} {window}"
        try:
            arts = r.json().get("articles", [])
        except ValueError:
            print(f"  {q}: non-JSON response ({r.status_code}): {r.text[:120]!r}")
            continue
        print(f"  {q}: {len(arts)} articles last 1w; sample: "
              f"{[(a['seendate'], a['domain'], a['title'][:60]) for a in arts[:2]]}")


def check_rss() -> None:
    section("6b. Publisher RSS (fallback news, no history)")
    feeds = {
        "Economic Times Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "Moneycontrol Business": "https://www.moneycontrol.com/rss/business.xml",
        "Livemint Markets": "https://www.livemint.com/rss/markets",
    }
    for name, url in feeds.items():
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
            print(f"  {name}: status={r.status_code} items={r.text.count('<item>')}")
        except requests.RequestException as e:
            print(f"  {name}: FAILED {type(e).__name__}")


def load_key() -> str | None:
    key = os.environ.get("ALPHAVANTAGE_API_KEY")
    env = Path(__file__).resolve().parents[1] / ".env"
    if not key and env.exists():
        for ln in env.read_text().splitlines():
            if ln.startswith("ALPHAVANTAGE_API_KEY="):
                key = ln.split("=", 1)[1].strip() or None
    return key


def check_alpha_vantage() -> None:
    section("5. Alpha Vantage NEWS_SENTIMENT")
    key = load_key()
    if not key:
        print("  SKIPPED: no ALPHAVANTAGE_API_KEY (get free key: https://www.alphavantage.co/support/#api-key)")
        return
    for t in ["TCS", "TCS.BSE", "INFY", "RELIANCE.BSE", "HDFCBANK.BSE"]:
        r = requests.get("https://www.alphavantage.co/query", params={
            "function": "NEWS_SENTIMENT", "tickers": t, "time_from": "20220101T0000",
            "sort": "EARLIEST", "limit": 1000, "apikey": key}, timeout=TIMEOUT).json()
        feed = r.get("feed", [])
        span = (feed[0]["time_published"], feed[-1]["time_published"]) if feed else None
        print(f"  {t:14s} -> {len(feed)} articles span={span} {r.get('Information') or r.get('Note') or ''}")


if __name__ == "__main__":
    for check in (check_prices, check_amfi, check_mfapi, check_gdelt, check_rss, check_alpha_vantage):
        try:
            check()
        except Exception as e:  # spike: report and keep going
            print(f"  FAILED: {type(e).__name__}: {e}")
