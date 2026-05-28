"""Dashboard summary response schemas (P12)."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CurrencyAmount(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    currency: str
    amount: Decimal


class MonthCurrencyAmount(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    month: str
    currency: str
    amount: Decimal


class ClosedSummary(BaseModel):
    count: int
    win_rate: Decimal | None
    per_currency_pnl: list[CurrencyAmount]
    monthly_pnl: list[MonthCurrencyAmount]


class OpenSummary(BaseModel):
    count: int
    per_currency_net_cash_flow: list[CurrencyAmount]


class DashboardSummary(BaseModel):
    closed: ClosedSummary
    open: OpenSummary
