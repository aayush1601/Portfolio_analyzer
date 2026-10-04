"""RSS news collector: fetch → parse → dedupe → append to daily JSONL files.

Started in Phase 1 so news accumulates for the backtest (RSS has no history).
Run every 30 min:  uv run python -m app.services.news_rss   (from backend/)
Phase 6 turns this into the full pipeline; Phase 15 moves it to Lambda + S3.
"""

import hashlib
import html
import json
import logging
import re
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx
import yaml
from defusedxml import ElementTree
from pydantic import BaseModel

from app.config import get_settings

log = logging.getLogger(__name__)
TAG_RE = re.compile(r"<[^>]+>")
SEEN_LOOKBACK_DAYS = 7  # RSS items rarely stay in a feed longer than this


class FeedConfig(BaseModel):
    name: str
    url: str
    reliability: float


class RawNewsItem(BaseModel):
    news_id: str
    source: str
    url: str
    headline: str
    summary: str
    published_at: datetime | None  # publisher time (UTC); None if feed date unparseable
    ingested_at: datetime  # when we saw it; live decisions may only use news with ingested_at <= t


def news_id(url: str, title: str) -> str:
    """Stable id for dedupe: same article from the same URL/title always hashes the same."""
    key = f"{url.strip().lower().split('?')[0]}|{' '.join(title.lower().split())}"
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def clean_text(text: str | None) -> str:
    return " ".join(html.unescape(TAG_RE.sub(" ", text or "")).split())


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(UTC)


def parse_feed(xml_text: str, source: str, ingested_at: datetime) -> list[RawNewsItem]:
    root = ElementTree.fromstring(xml_text)  # defusedxml: blocks entity-expansion attacks
    items = []
    for item in root.iter("item"):
        title = clean_text(item.findtext("title"))
        url = (item.findtext("link") or "").strip()
        if not title or not url:
            continue
        items.append(
            RawNewsItem(
                news_id=news_id(url, title),
                source=source,
                url=url,
                headline=title,
                summary=clean_text(item.findtext("description")),
                published_at=parse_date(item.findtext("pubDate")),
                ingested_at=ingested_at,
            )
        )
    return items


def load_feeds(config_dir: Path) -> list[FeedConfig]:
    data = yaml.safe_load((config_dir / "news_sources.yaml").read_text())
    return [FeedConfig(**f) for f in data["rss"]]


def seen_ids(out_dir: Path, today: date) -> set[str]:
    ids: set[str] = set()
    for back in range(SEEN_LOOKBACK_DAYS):
        f = out_dir / f"{today - timedelta(days=back)}.jsonl"
        if f.exists():
            ids.update(json.loads(line)["news_id"] for line in f.read_text().splitlines() if line)
    return ids


def collect(feeds: list[FeedConfig], out_dir: Path, client: httpx.Client) -> int:
    """Fetch all feeds and append unseen items to out_dir/<today>.jsonl. Returns number of new items."""
    now = datetime.now(UTC)
    out_dir.mkdir(parents=True, exist_ok=True)
    seen = seen_ids(out_dir, now.date())
    new: list[RawNewsItem] = []
    for feed in feeds:
        try:
            resp = client.get(feed.url)
            resp.raise_for_status()
            items = parse_feed(resp.text, feed.name, now)
        except (httpx.HTTPError, ElementTree.ParseError) as e:
            # One broken feed must not stop the others.
            log.warning("feed failed", extra={"fields": {"feed": feed.name, "error": str(e)}})
            continue
        fresh = [i for i in items if i.news_id not in seen]
        seen.update(i.news_id for i in fresh)
        new.extend(fresh)
        log.info("feed ok", extra={"fields": {"feed": feed.name, "items": len(items), "new": len(fresh)}})
    with (out_dir / f"{now.date()}.jsonl").open("a") as fh:
        fh.writelines(i.model_dump_json() + "\n" for i in new)
    return len(new)


def main() -> None:
    from app.utils.log import setup_logging

    settings = get_settings()
    setup_logging(settings.log_level)
    headers = {"User-Agent": "Mozilla/5.0 (portfolio-intelligence academic project)"}
    with httpx.Client(timeout=30, headers=headers, follow_redirects=True) as client:
        n = collect(load_feeds(settings.config_dir), settings.data_dir / "raw" / "news" / "rss", client)
    log.info("collection done", extra={"fields": {"new_items": n}})


if __name__ == "__main__":
    main()
