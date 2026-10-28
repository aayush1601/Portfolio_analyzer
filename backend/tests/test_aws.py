"""AWS layer against moto (no network, no account): DynamoDB store, S3 sync, Lambda handlers."""

import io
import json
from types import SimpleNamespace

import boto3
import pandas as pd
import pytest
from moto import mock_aws

from app.config import REPO_ROOT, get_settings

BUCKET, TABLE = "pi-test-data", "pi-test-userdata"


@pytest.fixture
def aws(tmp_path, monkeypatch):
    for k, v in {
        "AWS_DEFAULT_REGION": "ap-south-1",
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "STORAGE": "s3",
        "S3_BUCKET": BUCKET,
        "DDB_TABLE": TABLE,
        "DATA_DIR": str(tmp_path),
    }.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    from app.api import portfolio as api
    from app.aws import storage

    api.get_store.cache_clear()
    storage._seen_version, storage._etags = None, {}
    with mock_aws():
        boto3.client("s3").create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "ap-south-1"}
        )
        boto3.client("dynamodb").create_table(
            TableName=TABLE,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"} for a in ("PK", "SK")],
            BillingMode="PAY_PER_REQUEST",
        )
        yield tmp_path
    get_settings.cache_clear()
    api.get_store.cache_clear()


def test_dynamo_store_seeds_demos_and_round_trips(aws):
    from app.aws.ddb_store import DynamoPortfolioStore
    from app.models.portfolio import PortfolioCreate

    store = DynamoPortfolioStore(TABLE, REPO_ROOT / "config" / "demo_portfolios.yaml")
    assert {p.name for p in store.list("u1")} == {"Demo: stocks + IT fund", "Demo: funds only"}
    p = store.create(
        "u1",
        PortfolioCreate(name="Mine", holdings=[{"asset_type": "CASH", "asset_id": "INR", "quantity": 5}]),
    )
    store.put_snapshot("u1", f"PORTFOLIO#{p.portfolio_id}#RISK#2026-10-01", {"risk_score": 30})
    assert store.get("u1", p.portfolio_id).name == "Mine"
    assert store.get("u2", p.portfolio_id) is None  # another user cannot read it
    assert len(store.list("u1")) == 3  # the risk snapshot is not mistaken for a portfolio
    assert sorted(u for u, _ in store.all()) == ["u1"] * 3


def test_persist_and_sync_down_mirror_a_dataset(aws):
    from app.aws import storage

    ds = aws / "processed" / "nav"
    (ds / "year=2026").mkdir(parents=True)
    (ds / "year=2026" / "a.parquet").write_text("one")
    storage.persist("processed/nav")
    (ds / "year=2026" / "a.parquet").unlink()
    (ds / "year=2026" / "b.parquet").write_text("two")
    storage.persist("processed/nav")  # a.parquet is gone locally, so it goes from S3 too
    keys = [
        o["Key"] for o in boto3.client("s3").list_objects_v2(Bucket=BUCKET, Prefix="processed/")["Contents"]
    ]
    assert keys == ["processed/nav/year=2026/b.parquet"]

    (ds / "year=2026" / "b.parquet").unlink()
    assert storage.sync_down(("processed/",), force=True) == 1
    assert (ds / "year=2026" / "b.parquet").read_text() == "two"
    assert storage.sync_down(("processed/",)) == 0  # version unchanged: one HEAD, no listing

    # another container writes: the version changes, so the next request picks the new file up
    boto3.client("s3").put_object(Bucket=BUCKET, Key="processed/nav/year=2026/c.parquet", Body=b"three")
    storage._bump(boto3.client("s3"), BUCKET)
    assert storage.sync_down(("processed/",)) == 1
    assert (ds / "year=2026" / "c.parquet").read_text() == "three"

    # a job rewrites the dataset under a new file name: the old local copy must go, or rows would duplicate
    boto3.client("s3").delete_object(Bucket=BUCKET, Key="processed/nav/year=2026/c.parquet")
    storage._bump(boto3.client("s3"), BUCKET)
    storage.sync_down(("processed/",))
    assert not (ds / "year=2026" / "c.parquet").exists()
    assert (ds / "year=2026" / "b.parquet").exists()


def test_api_handler_serves_an_http_api_event(aws):
    from app.aws import handlers

    event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": "/health",
        "rawQueryString": "",
        "headers": {"host": "x.execute-api.ap-south-1.amazonaws.com"},
        "requestContext": {"http": {"method": "GET", "path": "/health", "sourceIp": "1.2.3.4", "protocol": "HTTP/1.1", "userAgent": "t"}, "stage": "$default"},
        "isBase64Encoded": False,
    }  # fmt: skip
    r = handlers.api(event, SimpleNamespace())
    assert r["statusCode"] == 200 and json.loads(r["body"])["status"] == "ok"


def test_news_score_scores_only_new_headlines(aws, monkeypatch):
    from app.aws import handlers
    from app.services import sentiment

    calls = []

    def fake_score(texts):
        calls.append(texts)
        return pd.DataFrame(
            {"p_pos": 0.7, "p_neu": 0.2, "p_neg": 0.1, "score": 0.6, "label": "positive", "confidence": 0.7},
            index=range(len(texts)),
        )

    monkeypatch.setattr(sentiment, "score_texts", fake_score)
    record = lambda i: {"body": json.dumps({"news_id": i, "headline": f"h{i}"})}  # noqa: E731
    assert handlers.news_score({"Records": [record("a"), record("b")]}, None) == {"scored": 2}
    assert handlers.news_score({"Records": [record("a"), record("c")]}, None) == {
        "scored": 1
    }  # a is a redelivery
    assert calls == [["ha", "hb"], ["hc"]]
    obj = boto3.client("s3").get_object(Bucket=BUCKET, Key="processed/sentiment.parquet")
    assert len(pd.read_parquet(io.BytesIO(obj["Body"].read()))) == 3


def test_news_score_failure_raises_so_sqs_retries_and_writes_nothing(aws, monkeypatch):
    """Failure mode (Phase 18): if FinBERT crashes, the batch must fail loudly. SQS then redelivers it and,
    after 3 receives, parks it in the DLQ (alarmed). A half-written sentiment file must never be saved."""
    from app.aws import handlers
    from app.services import sentiment

    def broken(texts):
        raise RuntimeError("model failed to load")

    monkeypatch.setattr(sentiment, "score_texts", broken)
    record = {"body": json.dumps({"news_id": "x", "headline": "hx"})}
    with pytest.raises(RuntimeError):
        handlers.news_score({"Records": [record]}, None)
    s3 = boto3.client("s3")
    with pytest.raises(s3.exceptions.NoSuchKey):
        s3.get_object(Bucket=BUCKET, Key="processed/sentiment.parquet")


def test_unscored_headlines_become_queue_messages():
    from app.aws.handlers import unscored

    now = pd.Timestamp("2026-10-16T10:00Z")
    news = pd.DataFrame(
        {
            "news_id": ["a", "b", "old"],
            "headline": ["A", "B", "Old"],
            "published_at": [now, now - pd.Timedelta(days=1), now - pd.Timedelta(days=400)],
        }
    )
    # "a" is already scored; "old" is history (GDELT), scored on a laptop, never queued to Lambda
    assert unscored(news, {"a"}, now=now) == [{"news_id": "b", "headline": "B"}]


def test_news_impact_alerts_by_sns_and_records_the_alert(aws, monkeypatch):
    from app.api import portfolio as api
    from app.aws import handlers

    sns = boto3.client("sns")
    topic = sns.create_topic(Name="alerts")["TopicArn"]
    monkeypatch.setenv("ALERTS_TOPIC_ARN", topic)
    get_settings.cache_clear()
    store = api.get_store()
    pid = store.list("u1")[0].portfolio_id
    fake = SimpleNamespace(
        alert=True,
        portfolio_news_impact=-0.05,
        alert_threshold=0.02,
        items=[SimpleNamespace(headline="TCS slumps")],
    )
    monkeypatch.setattr(
        api,
        "get_news",
        lambda portfolio_id, user, store, limit: (
            fake if portfolio_id == pid else SimpleNamespace(alert=False)
        ),
    )
    assert handlers.news_impact({}, None) == {"alerts": 1}
    items = boto3.resource("dynamodb").Table(TABLE).scan()["Items"]
    alert = [i for i in items if i["SK"].startswith("ALERT#")]
    assert len(alert) == 1 and alert[0]["portfolio_id"] == pid and float(alert[0]["impact"]) == -0.05


def test_import_tokens_live_in_dynamodb_so_any_container_sees_them(aws):
    from app.services import cas_import as cas

    token = cas.new_token(owner="user-sub-1")
    cas._tokens.clear()  # a different container: nothing in memory
    assert cas.check_token(token) and cas.token_result(token) is None
    assert cas.token_owner(token) == "user-sub-1"  # the phone's upload lands in this account
    cas.complete_token(token, "abc123abc123")
    assert cas.token_result(token) == "abc123abc123"
    assert not cas.check_token("nope")


def test_secrets_come_from_ssm_and_skip_the_placeholder(aws, monkeypatch):
    ssm = boto3.client("ssm")
    ssm.put_parameter(Name="/pi-test/secrets/ALPHAVANTAGE_API_KEY", Value="k-123", Type="SecureString")
    ssm.put_parameter(Name="/pi-test/secrets/UNUSED", Value="unset", Type="SecureString")
    monkeypatch.setenv("SSM_SECRETS_PATH", "/pi-test/secrets/")
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.alphavantage_api_key.get_secret_value() == "k-123" and s.storage == "s3"
    finally:
        get_settings.cache_clear()


def test_backtest_on_aws_is_handed_to_the_worker_lambda(aws, monkeypatch):
    """A run takes over a minute, longer than API Gateway's 30 s: the API records QUEUED in S3 (so every
    container's run list shows it) and invokes the backtest Lambda asynchronously; the worker writes DONE."""
    from app.api import backtests
    from app.aws import handlers

    monkeypatch.setenv("BACKTEST_FUNCTION", "pi-test-backtest")
    get_settings.cache_clear()
    calls = []
    monkeypatch.setattr(backtests, "_invoke", lambda fn, payload: calls.append((fn, payload)))
    monkeypatch.setattr(backtests.svc, "run", lambda overrides, run_id: {"run_id": run_id})

    out = backtests.start(backtests.BacktestRequest(cost_bps=5), background=None)
    assert out["status"] == "QUEUED"
    assert calls == [("pi-test-backtest", {"run_id": out["run_id"], "overrides": {"cost_bps": 5.0}})]
    key = f"backtests/{out['run_id']}/results.json"
    body = boto3.client("s3").get_object(Bucket=BUCKET, Key=key)["Body"].read()
    assert json.loads(body)["status"] == "QUEUED"

    # the worker: runs and persists (svc.run is stubbed, so results.json stays as the API wrote it)
    assert handlers.backtest(calls[0][1], None) == {"run_id": out["run_id"]}
