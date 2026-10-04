from datetime import UTC, datetime

import httpx

from app.services.news_rss import FeedConfig, collect, news_id, parse_feed

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>TCS Q2 profit rises 8%</title><link>https://ex.com/a?utm=x</link>
  <description>&lt;p&gt;Tata Consultancy &amp;amp; more&lt;/p&gt;</description>
  <pubDate>Thu, 02 Oct 2026 13:30:00 +0530</pubDate></item>
<item><title>No link item</title></item>
<item><title>Bad date</title><link>https://ex.com/b</link><pubDate>yesterday</pubDate></item>
</channel></rss>"""
NOW = datetime(2026, 10, 4, tzinfo=UTC)


def test_parse_feed_cleans_and_converts_to_utc():
    items = parse_feed(RSS, "ex", NOW)
    assert [i.headline for i in items] == ["TCS Q2 profit rises 8%", "Bad date"]
    assert items[0].summary == "Tata Consultancy & more"
    assert items[0].published_at == datetime(2026, 10, 2, 8, 0, tzinfo=UTC)  # 13:30 IST = 08:00 UTC
    assert items[1].published_at is None


def test_news_id_ignores_query_string_case_and_spacing():
    assert news_id("https://ex.com/a?utm=1", "TCS  profit") == news_id("HTTPS://ex.com/a", "tcs profit")


def test_collect_dedupes_across_runs_and_survives_broken_feed(tmp_path):
    def handler(request):
        return httpx.Response(200, text=RSS) if "good" in str(request.url) else httpx.Response(500)

    feeds = [
        FeedConfig(name="good", url="https://good/rss", reliability=1),
        FeedConfig(name="bad", url="https://bad/rss", reliability=1),
    ]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert collect(feeds, tmp_path, client) == 2
    assert collect(feeds, tmp_path, client) == 0  # second run: everything already seen
    lines = next(tmp_path.glob("*.jsonl")).read_text().splitlines()
    assert len(lines) == 2
