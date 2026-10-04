"""News pipeline (Phase 6): raw RSS JSONL → deduped, entity-mapped, scored NewsItem rows in Parquet.

Run after the collector:  uv run python -m app.services.news_pipeline   (from backend/)
Input:  data/raw/news/rss/*.jsonl  (app.services.news_rss)
Output: data/processed/news/year=YYYY/…parquet  (NewsItem, docs/data_model.md; sentiment comes in Phase 7)
"""

import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from app.config import get_settings
from app.services.market_data import read, save

log = logging.getLogger(__name__)
IST = "Asia/Kolkata"


def _pattern(phrases: list[str], case_sensitive: bool) -> re.Pattern:
    # Longest first, so at any position the regex prefers "SBI Life" over "SBI". Lookarounds instead of \b
    # because aliases can start or end with punctuation (L&T, Dr. Reddy's).
    alts = "|".join(re.escape(p) for p in sorted(set(phrases), key=len, reverse=True))
    return re.compile(rf"(?<![\w&])(?:{alts})(?![\w&])", 0 if case_sensitive else re.IGNORECASE)


@dataclass
class Mapper:
    alias_to_symbol: dict[str, str | None]  # None = stop phrase
    symbol_sector: dict[str, str]
    aliases: re.Pattern
    sector_patterns: list[tuple[re.Pattern, str]]
    events: re.Pattern
    importance: dict[str, float]
    reliability: dict[str, float]

    @classmethod
    def from_config(cls, config_dir: Path) -> "Mapper":
        u = yaml.safe_load((config_dir / "universe.yaml").read_text())
        n = yaml.safe_load((config_dir / "news_sources.yaml").read_text())
        alias_to_symbol: dict[str, str | None] = {}
        for s in u["stocks"]:
            for a in s["aliases"]:
                alias_to_symbol[a] = s["symbol"]
        alias_to_symbol.update({stop: None for stop in n["entity_stoplist"]})
        sector_patterns = []
        for sector, kws in n["sector_keywords"].items():
            for kw in kws:
                sector_patterns.append((_pattern([kw], bool(re.search(r"\b[A-Z]{2,}\b", kw))), sector))
        return cls(
            alias_to_symbol=alias_to_symbol,
            symbol_sector={s["symbol"]: s["sector"] for s in u["stocks"]},
            aliases=_pattern(list(alias_to_symbol), case_sensitive=True),
            sector_patterns=sector_patterns,
            events=re.compile(
                r"\b(?:" + "|".join(re.escape(k) for k in n["event_keywords"]) + ")", re.IGNORECASE
            ),
            importance=n["importance"],
            reliability={f["name"]: f["reliability"] for f in n["rss"]},
        )

    def symbols(self, text: str) -> list[str]:
        found = (self.alias_to_symbol[m.group(0)] for m in self.aliases.finditer(text))
        return sorted({s for s in found if s})

    def sectors(self, text: str, symbols: list[str]) -> list[str]:
        keyword = {sector for pat, sector in self.sector_patterns if pat.search(text)}
        return sorted(keyword | {self.symbol_sector[s] for s in symbols})

    def score(self, headline: str, summary: str) -> dict:
        text = f"{headline} {summary}"
        symbols = self.symbols(text)
        keyword_sectors = any(pat.search(text) for pat, _ in self.sector_patterns)
        w = self.importance
        importance = (
            w["base"]
            + w["symbol_in_headline"] * bool(self.symbols(headline))
            + w["event_keyword"] * bool(self.events.search(text))
            + w["focused"] * (1 <= len(symbols) <= 2)
            + w["sector_keyword"] * keyword_sectors
        )
        return {
            "symbols": symbols,
            "sectors": self.sectors(text, symbols),
            "importance": round(min(1.0, importance), 4),
        }


def recency(age_hours: float, half_life_hours: float) -> float:
    """Exponential time decay used by the sentiment aggregates (Phase 7) and impact (Phase 8)."""
    return 0.5 ** (max(age_hours, 0.0) / half_life_hours)


def tidy(text: str) -> str:
    """Undo double HTML escaping (&amp;amp;) and the "#39;" apostrophes some feeds emit."""
    return html.unescape(html.unescape(text or "")).replace("#39;", "'")


def load_raw(raw_dir: Path) -> pd.DataFrame:
    rows = [
        json.loads(line)
        for f in sorted(raw_dir.glob("*.jsonl"))
        for line in f.read_text().splitlines()
        if line
    ]
    df = pd.DataFrame(rows)
    for col in ("published_at", "ingested_at"):
        df[col] = pd.to_datetime(df[col], utc=True, format="ISO8601")
    return df


def process(raw: pd.DataFrame, mapper: Mapper) -> pd.DataFrame:
    df = raw.sort_values("ingested_at").drop_duplicates("news_id")
    df = df.assign(headline=df["headline"].map(tidy), summary=df["summary"].map(tidy))
    # The same wire story often appears on several sites under different URLs: keep the first one we saw.
    df = df.assign(_h=df["headline"].str.lower().str.replace(r"\W+", " ", regex=True).str.strip())
    df = df.drop_duplicates("_h").drop(columns="_h")

    # Publisher time is missing for some items and occasionally in the future (bad feed clocks).
    # Neither can be trusted, so fall back to when we saw it; the flag keeps that visible to the backtest.
    bad = df["published_at"].isna() | (df["published_at"] > df["ingested_at"])
    df["published_at_estimated"] = bad
    df.loc[bad, "published_at"] = df.loc[bad, "ingested_at"]

    scored = pd.DataFrame([mapper.score(h, s) for h, s in zip(df["headline"], df["summary"], strict=True)])
    df = pd.concat([df.reset_index(drop=True), scored], axis=1)
    df["reliability"] = df["source"].map(mapper.reliability)
    df["date"] = df["published_at"].dt.tz_convert(IST).dt.tz_localize(None).dt.normalize()  # IST calendar day
    return df.sort_values("published_at", ignore_index=True)


def load_news(data_dir: Path, since: datetime | None = None) -> pd.DataFrame:
    return read(data_dir / "processed" / "news", "published_at", since)


def main() -> None:
    from app.utils.log import setup_logging

    settings = get_settings()
    setup_logging(settings.log_level)
    news = process(
        load_raw(settings.data_dir / "raw" / "news" / "rss"), Mapper.from_config(settings.config_dir)
    )
    save(news, settings.data_dir / "processed" / "news")
    log.info(
        "news pipeline done",
        extra={
            "fields": {
                "items": len(news),
                "with_symbols": int(news["symbols"].str.len().gt(0).sum()),
                "with_sectors": int(news["sectors"].str.len().gt(0).sum()),
                "estimated_times": int(news["published_at_estimated"].sum()),
            }
        },
    )


if __name__ == "__main__":
    main()
