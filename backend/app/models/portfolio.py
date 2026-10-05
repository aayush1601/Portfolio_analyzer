"""Portfolio models (docs/data_model.md, docs/api/openapi.yaml). Weights are fractions, money is INR."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, model_validator


class AssetType(StrEnum):
    STOCK = "STOCK"
    MF = "MF"
    CASH = "CASH"


class Holding(BaseModel):
    asset_type: AssetType
    asset_id: str = Field(min_length=1, max_length=20, description="NSE symbol, AMFI scheme code, or INR")
    quantity: float = Field(gt=0)
    avg_cost: float = Field(default=0, ge=0, description="Per unit; ignored for CASH")

    @model_validator(mode="after")
    def cash_is_inr(self) -> "Holding":
        if self.asset_type is AssetType.CASH and self.asset_id != "INR":
            raise ValueError("CASH asset_id must be INR")
        return self


def _unique(holdings: list[Holding]) -> list[Holding]:
    keys = [(h.asset_type, h.asset_id) for h in holdings]
    if len(keys) != len(set(keys)):
        raise ValueError("each asset may appear only once; merge duplicate holdings")
    return holdings


Holdings = Annotated[list[Holding], Field(max_length=200), AfterValidator(_unique)]


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    holdings: Holdings


class Portfolio(PortfolioCreate):
    portfolio_id: str
    created_at: datetime


class HoldingValue(Holding):
    price: float
    price_date: date | None  # date of the price/NAV used; may lag as_of (NAVs publish ~23:00 IST)
    value: float
    weight: float
    pl: float  # unrealised: value − quantity × avg_cost
    daily_pl: float


class ValuePoint(BaseModel):
    date: date
    value: float


class ValueHistory(BaseModel):
    """Today's holdings valued on past dates: how this mix would have moved, not the user's trades."""

    portfolio_id: str
    invested: float  # Σ quantity × avg_cost, plus cash
    points: list[ValuePoint]


class PortfolioSnapshot(BaseModel):
    portfolio_id: str
    as_of: date
    total_value: float
    daily_pl: float
    total_pl: float
    holdings: list[HoldingValue]
