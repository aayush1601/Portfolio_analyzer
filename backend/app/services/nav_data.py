"""Mutual fund NAV history: mfapi.in → Parquet NavPoint rows.

Pulled forward from Phase 5 because Phase 3 needs NAVs to value fund holdings; fund analytics stay in Phase 5.
Run daily after ~23:00 IST:  uv run python -m app.services.nav_data   (from backend/)
Output: data/processed/nav/year=YYYY/…parquet
"""

import json
import logging
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import yaml

from app.config import get_settings
from app.services.market_data import read, save

log = logging.getLogger(__name__)
NAV_PUBLISHED_IST = pd.Timedelta(hours=23)  # AMFI publishes ~21:00–23:00 IST (docs/data_sources.md)


def load_scheme_codes(config_dir: Path, data_dir: Path | None = None) -> list[str]:
    """Universe funds, plus funds registered by CAS imports (data_dir/processed/extra_funds.json)."""
    u = yaml.safe_load((config_dir / "universe.yaml").read_text())
    codes = [str(f["scheme_code"]) for f in u["mutual_funds"]]
    extra = data_dir / "processed" / "extra_funds.json" if data_dir else None
    if extra and extra.exists():
        codes += [c for c in json.loads(extra.read_text()) if c not in codes]
    return codes


def parse_mfapi(payload: dict, scheme_code: str) -> pd.DataFrame:
    """mfapi `data` (newest first, dd-mm-yyyy, NAV as string) → scheme_code, date, nav, available_at."""
    df = pd.DataFrame(payload["data"])
    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df = df[df["nav"] > 0].drop_duplicates("date").sort_values("date", ignore_index=True)
    df["scheme_code"] = scheme_code
    df["available_at"] = (df["date"] + NAV_PUBLISHED_IST).dt.tz_localize("Asia/Kolkata").dt.tz_convert("UTC")
    return df[["scheme_code", "date", "nav", "available_at"]]


def collect(codes: list[str], client: httpx.Client) -> pd.DataFrame:
    frames = []
    for code in codes:
        try:
            resp = client.get(f"https://api.mfapi.in/mf/{code}")
            resp.raise_for_status()
            frames.append(parse_mfapi(resp.json(), code))
        except (httpx.HTTPError, KeyError, ValueError) as e:
            # One broken scheme must not stop the others; it shows up as missing in the summary.
            log.warning("nav failed", extra={"fields": {"scheme_code": code, "error": str(e)}})
    return pd.concat(frames, ignore_index=True)


def load_navs(data_dir: Path, since: date | None = None) -> pd.DataFrame:
    return read(data_dir / "processed" / "nav", "scheme_code", since)


def refresh(settings=None):
    """One run of this job; called by the CLI below and by the scheduled Lambda (app/aws/handlers.py)."""
    settings = settings or get_settings()
    codes = load_scheme_codes(settings.config_dir, settings.data_dir)
    with httpx.Client(timeout=30) as client:
        navs = collect(codes, client)
    save(navs, settings.data_dir / "processed" / "nav")
    log.info(
        "nav data done",
        extra={
            "fields": {
                "schemes": navs["scheme_code"].nunique(),
                "rows": len(navs),
                "to": str(navs["date"].max().date()),
                "missing": sorted(set(codes) - set(navs["scheme_code"])),
            }
        },
    )


def main() -> None:
    from app.utils.log import setup_logging

    setup_logging(get_settings().log_level)
    refresh()


if __name__ == "__main__":
    main()
