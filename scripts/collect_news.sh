#!/bin/sh
# Collects RSS once, rebuilds the processed news store, then FinBERT-scores new headlines. Scheduled every 30 min by launchd
# (see com.portfolio-intelligence.news.plist).
cd "$(dirname "$0")/../backend" || exit 1
/opt/homebrew/bin/uv run --no-dev python -m app.services.news_rss
/opt/homebrew/bin/uv run --no-dev python -m app.services.news_pipeline
exec /opt/homebrew/bin/uv run --no-dev --group ml python -m app.services.sentiment score
