"""Lambda entry points (Phase 14 API, Phase 15 event pipeline). One image, one handler per function.

API:        api                     API Gateway HTTP API → FastAPI (Mangum)
Schedules:  market_ingest           EventBridge Scheduler, weekdays after the NSE close → emits MarketDataUpdated
            nav_ingest              daily after AMFI publishes NAVs
            news_ingest             every 30 min: RSS → news pipeline → unscored headlines to SQS
            holdings_ingest         monthly: parse AMC disclosures uploaded to s3://…/raw/mutual_funds/holdings/
Queue:      news_score              SQS (batches) → FinBERT → sentiment → emits NewsScored   [FinBERT image]
Events:     news_impact             on NewsScored: exposure-weighted impact per portfolio → SNS alert if breached
            risk_refresh            on MarketDataUpdated: risk snapshot per portfolio → DynamoDB
Every job reads data mirrored from S3 (app.aws.storage) and writes back what it changed.
"""

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal

from app.aws.events import emit
from app.aws.storage import persist, sync_down
from app.config import get_settings
from app.utils.log import setup_logging

setup_logging(get_settings().log_level)
log = logging.getLogger(__name__)

_api = None


def api(event, context):
    global _api
    if _api is None:
        from mangum import Mangum

        from app.main import app

        _api = Mangum(app, lifespan="off")
    return _api(event, context)


def _ddb(value):
    """DynamoDB wants Decimal, not float."""
    return json.loads(json.dumps(value, default=str), parse_float=Decimal)


def market_ingest(event, context):
    from app.services import market_data

    sync_down(force=True)
    as_of = market_data.refresh()
    persist("processed/market/prices")
    emit("MarketDataUpdated", {"as_of": as_of})
    return {"as_of": as_of}


def nav_ingest(event, context):
    from app.services import nav_data

    sync_down(force=True)
    nav_data.refresh()
    persist("processed/nav")
    return {"ok": True}


def holdings_ingest(event, context):
    from app.services import fund_holdings

    sync_down(("processed/", "raw/mutual_funds/"), force=True)
    fund_holdings.refresh()
    persist("processed/fund_holdings.parquet")
    return {"ok": True}


def unscored(news, done_ids: set[str]) -> list[dict]:
    """Headlines not yet scored, as SQS message bodies."""
    todo = news[~news["news_id"].isin(done_ids)]
    return [{"news_id": r.news_id, "headline": r.headline} for r in todo.itertuples()]


def news_ingest(event, context):
    import boto3

    from app.services import news_pipeline, news_rss
    from app.services.sentiment import load_sentiment

    s = get_settings()
    sync_down(force=True)
    news_rss.refresh()
    persist("raw/news/rss")
    news_pipeline.refresh()
    persist("processed/news")
    from app.services.news_pipeline import load_news

    messages = unscored(load_news(s.data_dir), set(load_sentiment(s.data_dir)["news_id"]))
    if s.news_queue_url:
        sqs = boto3.client("sqs")
        for i in range(0, len(messages), 10):
            sqs.send_message_batch(
                QueueUrl=s.news_queue_url,
                Entries=[
                    # One group → strictly one batch at a time (single writer); news_id makes resends idempotent.
                    {
                        "Id": str(j),
                        "MessageBody": json.dumps(m),
                        "MessageGroupId": "news",
                        "MessageDeduplicationId": str(m["news_id"]),
                    }
                    for j, m in enumerate(messages[i : i + 10])
                ],
            )
    return {"queued": len(messages)}


def news_score(event, context):
    """SQS batch → FinBERT. Raising makes SQS retry the batch; after 3 receives it lands in the DLQ."""
    import pandas as pd

    from app.services.sentiment import MODEL, load_sentiment, score_texts, sentiment_path

    s = get_settings()
    msgs = [json.loads(r["body"]) for r in event.get("Records", [])]
    if not msgs:
        return {"scored": 0}
    sync_down(("processed/",), force=True)
    done = load_sentiment(s.data_dir)
    msgs = [m for m in msgs if m["news_id"] not in set(done["news_id"])]  # SQS is at-least-once
    if msgs:
        scored = score_texts([m["headline"] for m in msgs]).assign(
            news_id=[m["news_id"] for m in msgs], model=MODEL
        )
        path = sentiment_path(s.data_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.concat([done, scored], ignore_index=True).to_parquet(path, index=False)
        persist("processed/sentiment.parquet")
        emit("NewsScored", {"count": len(msgs)})
    return {"scored": len(msgs)}


def news_impact(event, context):
    """Exposure-weighted news impact per portfolio; publish an SNS alert when it crosses the threshold."""
    import boto3

    from app.api.portfolio import get_news, get_store

    s = get_settings()
    sync_down(force=True)
    store = get_store()
    sns = boto3.client("sns") if s.alerts_topic_arn else None
    alerts = 0
    for user, p in store.all():
        n = get_news(p.portfolio_id, user, store, limit=5)
        if not n.alert:
            continue
        alerts += 1
        now = datetime.now(UTC).isoformat()
        store.put_snapshot(
            user,
            f"ALERT#{now}#{p.portfolio_id}",
            _ddb(
                {
                    "type": "negative_news",
                    "portfolio_id": p.portfolio_id,
                    "impact": n.portfolio_news_impact,
                    "created_at": now,
                }
            ),
        )
        if sns:
            top = "; ".join(i.headline for i in n.items[:3])
            sns.publish(
                TopicArn=s.alerts_topic_arn,
                Subject=f"Portfolio Intelligence: negative news for {p.name}"[:100],
                Message=(
                    f"News impact for '{p.name}' is {n.portfolio_news_impact:+.3f}, past the "
                    f"{-n.alert_threshold:+.2f} alert threshold.\n\nMost impactful: {top}\n\n"
                    "Research output, not financial advice."
                ),
            )
    return {"alerts": alerts}


def risk_refresh(event, context):
    """Store a risk snapshot per portfolio after new prices land (AP4: latest risk snapshot)."""
    from fastapi import HTTPException

    from app.api.portfolio import get_risk, get_store

    sync_down(force=True)
    store = get_store()
    done = 0
    for user, p in store.all():
        try:
            r = get_risk(p.portfolio_id, user, store, 0.95, 252)
        except HTTPException as e:  # e.g. a portfolio of cash only: nothing to rate
            log.info("risk skipped", extra={"fields": {"portfolio_id": p.portfolio_id, "reason": e.detail}})
            continue
        store.put_snapshot(
            user,
            f"PORTFOLIO#{p.portfolio_id}#RISK#{r.as_of}",
            _ddb(
                {
                    "risk_score": r.risk_score,
                    "risk_band": r.risk_band,
                    "volatility_ann": r.volatility_ann,
                    "var_1d": r.var_1d.historical,
                    "weights_version": r.score_weights_version,
                }
            ),
        )
        done += 1
    return {"snapshots": done}
