#!/bin/sh
# Runs the RSS collector once. Scheduled every 30 min by launchd (see com.portfolio-intelligence.news.plist).
cd "$(dirname "$0")/../backend" && exec /opt/homebrew/bin/uv run --no-dev python -m app.services.news_rss
