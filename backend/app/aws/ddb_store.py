"""Portfolio store on DynamoDB (UserData table), with the same methods as the local JSON store.

Item per portfolio: PK = USER#<sub>, SK = PORTFOLIO#<pid>, `doc` = the Portfolio as JSON. Risk snapshots and
alerts use SK = PORTFOLIO#<pid>#RISK#<date> and ALERT#<ts>#<pid> (docs/data_model.md, AP4/AP6). The user id
always comes from the authenticated caller, never the request body (isolation, NFR4).
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import yaml

from app.models.portfolio import Portfolio, PortfolioCreate


class DynamoPortfolioStore:
    def __init__(self, table_name: str, demo_file: Path, table=None):
        if table is None:
            import boto3

            table = boto3.resource("dynamodb").Table(table_name)
        self.table = table
        self.demo_file = demo_file

    def _items(self, user: str, prefix: str) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        q = Key("PK").eq(f"USER#{user}") & Key("SK").begins_with(prefix)
        items, kw = [], {"KeyConditionExpression": q}
        while True:
            page = self.table.query(**kw)
            items += page["Items"]
            if "LastEvaluatedKey" not in page:
                return items
            kw["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def _seed(self, user: str) -> None:
        if not self._items(user, "PORTFOLIO#"):  # first visit: start with the demo portfolios
            for demo in yaml.safe_load(self.demo_file.read_text())["portfolios"]:
                self.create(user, PortfolioCreate(**demo))

    def save(self, user: str, p: Portfolio) -> None:
        self.table.put_item(
            Item={"PK": f"USER#{user}", "SK": f"PORTFOLIO#{p.portfolio_id}", "doc": p.model_dump_json()}
        )

    def create(self, user: str, body: PortfolioCreate) -> Portfolio:
        p = Portfolio(**body.model_dump(), portfolio_id=uuid.uuid4().hex[:12], created_at=datetime.now(UTC))
        self.save(user, p)
        return p

    def list(self, user: str) -> list[Portfolio]:
        self._seed(user)
        docs = [i["doc"] for i in self._items(user, "PORTFOLIO#") if i["SK"].count("#") == 1]
        return sorted((Portfolio.model_validate_json(d) for d in docs), key=lambda p: p.created_at)

    def get(self, user: str, portfolio_id: str) -> Portfolio | None:
        item = self.table.get_item(Key={"PK": f"USER#{user}", "SK": f"PORTFOLIO#{portfolio_id}"}).get("Item")
        return Portfolio.model_validate_json(item["doc"]) if item else None

    def all(self) -> Iterator[tuple[str, Portfolio]]:
        """Every (user, portfolio). A scan: fine at dev scale; production would use the AP10 index."""
        kw: dict = {}
        while True:
            page = self.table.scan(**kw)
            for i in page["Items"]:
                if i["SK"].startswith("PORTFOLIO#") and i["SK"].count("#") == 1:
                    yield i["PK"].removeprefix("USER#"), Portfolio.model_validate_json(i["doc"])
            if "LastEvaluatedKey" not in page:
                return
            kw["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def put_snapshot(self, user: str, sk: str, data: dict) -> None:
        self.table.put_item(Item={"PK": f"USER#{user}", "SK": sk, **data})
