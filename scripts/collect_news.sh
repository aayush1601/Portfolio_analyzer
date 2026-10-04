#!/bin/sh
# Collects RSS once, then rebuilds the processed news store. Scheduled every 30 min by launchd
# (see com.portfolio-intelligence.news.plist).
cd "$(dirname "$0")/../backend" || exit 1
/opt/homebrew/bin/uv run --no-dev python -m app.services.news_rss
exec /opt/homebrew/bin/uv run --no-dev python -m app.services.news_pipeline
