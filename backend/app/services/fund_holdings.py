"""Fund holdings (Phase 5): AMC monthly portfolio disclosures (Excel) → one normalised Parquet file.

Save the monthly files as downloaded, under data/raw/mutual_funds/holdings/ (any sub-folders and file
names, .xls or .xlsx). Each sheet in SEBI's standard layout (a header row with ISIN, % to AUM/NAV/Net
Assets, an "as on" date above it) is matched to a universe fund by its scheme name; others are skipped.
Run:     uv run python -m app.services.fund_holdings   (from backend/)
Output:  data/processed/fund_holdings.parquet
"""

import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml

from app.config import get_settings

log = logging.getLogger(__name__)
ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")
PCT_RE = re.compile(r"%\s*(to|of)")
# SEBI: monthly portfolios are disclosed within 10 days of month-end. We don't know the exact day, so the
# deadline is the conservative "could have known it" date (point-in-time rule, docs/algorithms/exposure.md).
PUBLISH_LAG = timedelta(days=10)
COLUMNS = ["scheme_code", "as_of_month", "published_at", "isin", "symbol", "name", "industry", "weight"]


def norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def find_header(df: pd.DataFrame) -> tuple[int, dict[str, int]] | None:
    """Row index and column positions of the holdings table header, or None if this isn't a holdings sheet."""
    for i, row in df.head(40).iterrows():
        cols: dict[str, int] = {}
        for j, cell in enumerate(row):
            c = str(cell).lower()
            if "isin" in c:
                cols.setdefault("isin", j)
            elif PCT_RE.search(c):
                cols.setdefault("weight", j)
            elif "industry" in c:
                cols.setdefault("industry", j)
            elif "name" in c or "instrument" in c:
                cols.setdefault("name", j)
        if {"isin", "weight", "name"} <= cols.keys():
            return int(i), cols
    return None


def sheet_as_of(top: pd.DataFrame) -> date | None:
    """The portfolio date: a date cell, or a date written after "as on", in the rows above the header."""
    for cell in top.to_numpy().ravel():
        if isinstance(cell, datetime):
            return cell.date()
        if isinstance(cell, str) and "as on" in cell.lower():
            text = re.split(r"as on\s*:?", cell, flags=re.I)[-1].strip()
            if text and not pd.isna(d := pd.to_datetime(text, dayfirst=True, errors="coerce")):
                return d.date()
    return None


def match_scheme(title: str, names: dict[str, str]) -> str | None:
    """Scheme code whose (normalised) name appears in the sheet title; the longest name wins."""
    t = norm(title)
    hits = [(len(n), code) for n, code in names.items() if n in t]
    return max(hits)[1] if hits else None


def parse_sheet(df: pd.DataFrame, names: dict[str, str]) -> pd.DataFrame | None:
    found = find_header(df)
    if found is None:
        return None
    hdr, cols = found
    top = df.iloc[:hdr]
    code = match_scheme(" ".join(str(c) for c in top.to_numpy().ravel() if isinstance(c, str)), names)
    as_of = sheet_as_of(top)
    if code is None or as_of is None:
        title = " | ".join(str(c) for c in top.to_numpy().ravel() if isinstance(c, str))[:200]
        log.info(
            "holdings sheet skipped (no universe scheme name or date)", extra={"fields": {"title": title}}
        )
        return None

    body = df.iloc[hdr + 1 :]
    rows = pd.DataFrame(
        {
            "isin": body.iloc[:, cols["isin"]].astype(str).str.strip(),
            "name": body.iloc[:, cols["name"]].astype(str).str.strip(),
            "industry": body.iloc[:, cols["industry"]].astype(str).str.strip()
            if "industry" in cols
            else None,
            "weight": pd.to_numeric(body.iloc[:, cols["weight"]], errors="coerce"),
        }
    )
    rows = rows[rows["isin"].str.match(ISIN_RE) & rows["weight"].notna()]
    if rows["weight"].sum() > 1.5:  # most AMCs print 6.77 for 6.77%; a few print 0.0677
        rows["weight"] /= 100
    rows = rows.groupby("isin", as_index=False).agg({"name": "first", "industry": "first", "weight": "sum"})
    month_end = (pd.Timestamp(as_of) + pd.offsets.MonthEnd(0)).date()
    return rows.assign(
        scheme_code=code, as_of_month=f"{month_end:%Y-%m}", published_at=month_end + PUBLISH_LAG
    )


def ingest(raw_dir: Path, names: dict[str, str], isin_to_symbol: dict[str, str]) -> pd.DataFrame:
    frames = []
    for f in sorted(p for p in raw_dir.rglob("*") if p.suffix.lower() in {".xls", ".xlsx"}):
        try:
            sheets = pd.read_excel(f, sheet_name=None, header=None)
        except Exception as e:  # one corrupt download must not stop the rest
            log.warning("unreadable workbook", extra={"fields": {"file": str(f), "error": str(e)}})
            continue
        for sheet, df in sheets.items():
            rows = parse_sheet(df, names)
            if rows is not None:
                frames.append(rows)
                log.info("sheet ok", extra={"fields": {"file": f.name, "sheet": sheet, "rows": len(rows)}})
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    out = pd.concat(frames, ignore_index=True)
    out["symbol"] = out["isin"].map(isin_to_symbol)  # None = not a universe stock (or not a stock)
    out = out.drop_duplicates(["scheme_code", "as_of_month", "isin"], keep="last")
    return out[COLUMNS].sort_values(["scheme_code", "as_of_month", "weight"], ascending=[True, True, False])


def load_universe_maps(config_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    """(normalised scheme name or alias → scheme code, ISIN → NSE symbol)."""
    u = yaml.safe_load((config_dir / "universe.yaml").read_text())
    names = {}
    for f in u["mutual_funds"]:
        for n in [f["name"], *f.get("holdings_aliases", [])]:
            names[norm(n)] = str(f["scheme_code"])
    return names, {s["isin"]: s["symbol"] for s in u["stocks"]}


def load_holdings(data_dir: Path) -> pd.DataFrame:
    f = data_dir / "processed" / "fund_holdings.parquet"
    return pd.read_parquet(f) if f.exists() else pd.DataFrame(columns=COLUMNS)


def main() -> None:
    from app.utils.log import setup_logging

    settings = get_settings()
    setup_logging(settings.log_level)
    names, isin_map = load_universe_maps(settings.config_dir)
    out = ingest(settings.data_dir / "raw" / "mutual_funds" / "holdings", names, isin_map)
    dest = settings.data_dir / "processed" / "fund_holdings.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(dest, index=False)
    months = out.groupby("scheme_code")["as_of_month"].nunique().to_dict()
    log.info(
        "fund holdings done",
        extra={"fields": {"months_per_scheme": months, "missing": sorted(set(names.values()) - set(months))}},
    )


if __name__ == "__main__":
    main()
