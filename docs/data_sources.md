# Data source evaluation

Evidence: [`spikes/check_sources.py`](../spikes/check_sources.py), run on **2026-10-04**. Output is in `spikes/output/` (gitignored, re-run to regenerate).
API terms and limits change; re-check the official docs before you rely on any number here.

| # | Source | Verdict |
|---|---|---|
| 1 | yfinance (Yahoo) prices | **Use** for historical and daily data |
| 2 | AMFI `NAVAll.txt` | **Use** for daily NAV of every scheme |
| 3 | mfapi.in | **Use** for NAV history and scheme metadata |
| 4 | AMC monthly portfolio disclosures | **Use (manual + parsers)**, the only free source of fund holdings |
| 5 | Alpha Vantage NEWS_SENTIMENT | **Pending**: needs a free API key (not yet tested) |
| 6a | GDELT DOC 2.0 API | **Fallback / backfill**: works, but strictly rate-limited |
| 6b | Publisher RSS (ET, Moneycontrol, Livemint) | **Use for forward collection** (no history) |
| — | niftyindices.com constituents CSV | **Use** for the universe definition |

---

## 1. yfinance
- **Endpoint:** Python library `yfinance` 1.7.0 (unofficial Yahoo Finance scraper; no key).
- **Tickers:** NSE symbol + `.NS` (e.g. `TCS.NS`, `M&M.NS`, `BAJAJ-AUTO.NS`); index `^NSEI`; volatility `^INDIAVIX`.
- **Result:** all 50 NIFTY constituents return data from 2015-01-01 to 2026-10-01, with **0 missing days** after each listing date. `^NSEI` has 12 missing days and `^INDIAVIX` 24 → forward-fill rule needed in Phase 2.
- **Short histories (listed after 2016):** BSE (2017-02), SBILIFE (2017-10), HDFCLIFE (2017-11), MAXHEALTH (2020-08), ETERNAL/Zomato (2021-07), JIOFIN (2023-08). TMPV is a 2025 demerger of Tata Motors, so check what history Yahoo maps to it before using it.
- **Timestamps:** daily bars dated in exchange-local dates; close is known at ~15:30 IST → `available_at = date 15:30 IST`.
- **Risks:** unofficial and can break or get rate-limited. Mitigation: cache everything to Parquet once, and keep the provider behind a small interface so a paid API (e.g. Twelve Data) can replace it.

## 2. AMFI NAVAll.txt
- **Endpoint:** `GET https://www.amfiindia.com/spages/NAVAll.txt` (no auth).
- **Format:** `;`-separated, 14,367 data lines. Header:
  `Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date`
- **Date format:** `01-Oct-2026`. NAVs are published in the evening (~21:00–23:00 IST), so `available_at = date 23:00 IST`.
- **Use:** daily ingestion job (Phase 5/15). Contains only the latest NAV, no history.

## 3. mfapi.in
- **Endpoints:** `GET https://api.mfapi.in/mf/search?q=<text>` and `GET https://api.mfapi.in/mf/<scheme_code>` (no auth).
- **Result:** UTI Nifty 50 Direct (120716) has 3,384 NAV points from 2013-01-02; PPFAS Flexi Cap Direct (122639) has 3,284 points from 2013-05-28.
- **Shape:** `{"meta": {fund_house, scheme_type, scheme_category, scheme_code, scheme_name, isin_growth, ...}, "data": [{"date": "dd-mm-yyyy", "nav": "string"}]}`, newest first. NAV is a **string** → parse to Decimal/float.
- **Note:** many funds were renamed (e.g. "Bluechip" → "Large Cap"), so search by the current name. Scheme codes are stable and are what we store.
- **Risk:** community-run service with no SLA → cache to Parquet; fall back to AMFI's historical NAV download.

## 4. AMC monthly portfolio disclosures (fund holdings)
- SEBI requires AMCs to publish full portfolios monthly (usually ~10 days after month-end). Each AMC publishes Excel files on its website; the format differs per AMC.
- **Not automatable from a single API.** Plan: download 24–36 months by hand into `data/raw/mutual_funds/holdings/<amc>/` and write one parser per AMC (6 AMCs: HDFC, ICICI Prudential, SBI, Axis, Kotak, PPFAS).
- Required columns: ISIN, instrument name, industry, % to NAV. Map ISIN → NSE symbol using the NIFTY CSV first, then the NSE equity master list.
- **Point-in-time rule:** `published_at` = disclosure date (store it); a backtest at date *t* uses the latest disclosure with `published_at ≤ t`.
- **Still to do (manual):** confirm for each of the 6 AMCs how many months are downloadable.

## 5. Alpha Vantage NEWS_SENTIMENT
- **Endpoint:** `GET https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=<T>&time_from=YYYYMMDDTHHMM&sort=EARLIEST&limit=1000&apikey=<KEY>`
- **Status:** **not yet tested**, because no key exists yet. Get a free key from https://www.alphavantage.co/support/#api-key, put it in `.env` as `ALPHAVANTAGE_API_KEY=...`, and re-run the spike.
- **Questions the spike answers:** which ticker format works for Indian stocks (`TCS`, `TCS.BSE`, …)? How many articles exist since 2022? What does the free-tier daily limit allow (historically ~25 requests/day; verify)?

## 6a. GDELT DOC 2.0
- **Endpoint:** `GET https://api.gdeltproject.org/api/v2/doc/doc?query=<q> sourcelang:english&mode=artlist&format=json&maxrecords=50&timespan=1w` (no auth).
- **Result:** the first query returned 50 English articles about TCS from the past week, from Indian publishers (economictimes.indiatimes.com, thehindubusinessline.com) with UTC `seendate`. Later queries got **HTTP 429** even with 20 s gaps, so the limit is enforced per IP and stricter than the documented "one per 5 s".
- **Limits:** DOC API searches a rolling recent window (roughly 3 months; verify). Deeper history means the GDELT raw files or the BigQuery dataset.
- **Use:** low-frequency backfill (a few queries per hour), not the main pipeline.

## 6b. Publisher RSS
| Feed | URL | Items |
|---|---|---|
| Economic Times Markets | `https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms` | 50 |
| Moneycontrol Business | `https://www.moneycontrol.com/rss/business.xml` | 15 |
| Livemint Markets | `https://www.livemint.com/rss/markets` | 35 |

- All returned HTTP 200 with a browser user-agent. They have **no history**: they only show the latest items, so value comes from collecting continuously from today.
- Store headline, summary, link and pubDate only (not full article text) to respect publisher terms.

## Entity-matching notes (for Phase 6)
- Aliases live in `config/universe.yaml`. Known collisions: "SBI" also matches "SBI Life"/"SBI Cards"; "Tata" is ambiguous; "Reliance" also matches Reliance Power/Infra; "HDFC" also matches HDFC Life/AMC. Use longest-match-first plus a stop-list.
