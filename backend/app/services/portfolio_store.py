"""Local portfolio store: one JSON file per portfolio under data/portfolios/<user>/.

Phase 14 swaps this for DynamoDB UserData (AP2/AP3) behind the same methods.
"""

import re
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import yaml

from app.models.portfolio import Portfolio, PortfolioCreate

PID_PATTERN = r"^[0-9a-f]{12}$"
USER_RE = re.compile(r"^[\w-]{1,64}$")  # Cognito `sub` is a UUID; also keeps paths inside root


class PortfolioStore:
    def __init__(self, root: Path, demo_file: Path):
        self.root = root
        self.demo_file = demo_file

    def _dir(self, user: str) -> Path:
        if not USER_RE.match(user):
            raise ValueError("invalid user id")
        d = self.root / user
        if not d.exists():  # first visit: start with the demo portfolios (PRODUCT.md)
            d.mkdir(parents=True)
            for demo in yaml.safe_load(self.demo_file.read_text())["portfolios"]:
                self.create(user, PortfolioCreate(**demo))
        return d

    def save(self, user: str, p: Portfolio) -> None:
        (self._dir(user) / f"{p.portfolio_id}.json").write_text(p.model_dump_json(indent=2))

    def create(self, user: str, body: PortfolioCreate) -> Portfolio:
        p = Portfolio(**body.model_dump(), portfolio_id=uuid.uuid4().hex[:12], created_at=datetime.now(UTC))
        self.save(user, p)
        return p

    def list(self, user: str) -> list[Portfolio]:
        ps = [Portfolio.model_validate_json(f.read_text()) for f in self._dir(user).glob("*.json")]
        return sorted(ps, key=lambda p: p.created_at)

    def all(self) -> Iterator[tuple[str, Portfolio]]:
        """Every (user, portfolio), for the scheduled pipeline jobs."""
        for d in sorted(p for p in self.root.glob("*") if p.is_dir()):
            for f in d.glob("*.json"):
                yield d.name, Portfolio.model_validate_json(f.read_text())

    def put_snapshot(self, user: str, sk: str, data: dict) -> None:
        """Locally, risk snapshots and alerts are not persisted (DynamoDB only)."""

    def get(self, user: str, portfolio_id: str) -> Portfolio | None:
        f = self._dir(user) / f"{portfolio_id}.json"
        return Portfolio.model_validate_json(f.read_text()) if f.exists() else None
