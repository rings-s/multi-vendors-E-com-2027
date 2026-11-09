"""Dashboard analytics for the marketplace (``merchant_id=None``) or one merchant.

SQL only selects the raw rows of the requested period and the period before it,
always scoped to the merchant when one is given. pandas and numpy do the
aggregation in the pure ``compute_*`` functions below, so every figure can be
tested without a database. Days are calendar days in Asia/Riyadh, money is in
halalas, and every figure comes from recorded orders, payments and refunds
(nothing is interpolated or forecast).
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sqlmodel import Date, String, cast, col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import utcnow
from app.modules.analytics.schemas import (
    Analytics,
    AnalyticsKpis,
    BreakdownSlice,
    Delta,
    RankedItem,
    RateDelta,
    SalesTrend,
    TrendPoint,
    WeekdayPoint,
)
from app.modules.merchants.models import Merchant
from app.modules.orders.models import MerchantOrder, OrderItem
from app.modules.payments.models import CAPTURED_STATUSES, Payment, Refund, RefundStatus

TIMEZONE = "Asia/Riyadh"
RIYADH = ZoneInfo(TIMEZONE)
MOVING_AVERAGE_DAYS = 7
TOP_N = 5
MAX_PAYMENT_METHODS = 4  # the rest are folded into OTHER

ORDER_COLUMNS = ["day", "total", "status", "merchant_id"]
REFUND_COLUMNS = ["day", "amount"]
PAYMENT_COLUMNS = ["method", "amount"]
ITEM_COLUMNS = ["item_id", "label", "quantity", "amount"]


@dataclass(frozen=True)
class Window:
    """``days`` calendar days ending today (inclusive), plus the same length before it."""

    start: date
    end: date
    days: int

    @classmethod
    def ending(cls, days: int, now: datetime | None = None) -> "Window":
        end = (now or utcnow()).astimezone(RIYADH).date()
        return cls(start=end - timedelta(days=days - 1), end=end, days=days)

    @property
    def previous_start(self) -> date:
        return self.start - timedelta(days=self.days)

    @staticmethod
    def utc(day: date) -> datetime:
        """The instant a Riyadh calendar day begins (for index-friendly timestamptz filters)."""
        return datetime.combine(day, time.min, tzinfo=RIYADH)


# -- frames -----------------------------------------------------------------------------


def frame(rows: list[Any], columns: list[str], *, day: bool = True) -> pd.DataFrame:
    df = pd.DataFrame.from_records([tuple(r) for r in rows], columns=columns)
    if day:
        df["day"] = pd.to_datetime(df["day"])
    for name in ("total", "amount", "quantity"):
        if name in df:
            df[name] = df[name].fillna(0).astype("int64")
    return df


def _between(df: pd.DataFrame, first: date, last: date) -> pd.DataFrame:
    days = df["day"]
    return df[(days >= pd.Timestamp(first)) & (days <= pd.Timestamp(last))]


def daily(orders: pd.DataFrame, first: date, last: date) -> pd.DataFrame:
    """Orders and gross sales for every day from ``first`` to ``last``; empty days are 0."""
    grouped = orders.groupby("day").agg(orders=("total", "size"), gross_sales=("total", "sum"))
    index = pd.date_range(first, last, freq="D")
    return grouped.reindex(index, fill_value=0).astype("int64")


# -- computations -----------------------------------------------------------------------


def _change_pct(current: float, previous: float) -> float | None:
    return round((current - previous) / previous * 100, 2) if previous else None


def _delta(current: int, previous: int) -> Delta:
    return Delta(current=current, previous=previous, change_pct=_change_pct(current, previous))


def _order_stats(totals: np.ndarray[Any, np.dtype[np.int64]]) -> tuple[int, int, int, int]:
    if totals.size == 0:
        return 0, 0, 0, 0
    return (
        int(totals.sum()),
        int(totals.size),
        round(float(totals.mean())),
        round(float(np.median(totals))),
    )


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 2) if whole else None


def compute_kpis(orders: pd.DataFrame, refunds: pd.DataFrame, window: Window) -> AnalyticsKpis:
    previous_end = window.start - timedelta(days=1)
    cur = _order_stats(_between(orders, window.start, window.end)["total"].to_numpy(dtype=np.int64))
    prev = _order_stats(_between(orders, window.previous_start, previous_end)["total"].to_numpy(dtype=np.int64))
    cur_refunds = int(_between(refunds, window.start, window.end)["amount"].sum())
    prev_refunds = int(_between(refunds, window.previous_start, previous_end)["amount"].sum())
    cur_rate, prev_rate = _rate(cur_refunds, cur[0]), _rate(prev_refunds, prev[0])
    return AnalyticsKpis(
        gross_sales=_delta(cur[0], prev[0]),
        orders=_delta(cur[1], prev[1]),
        average_order_value=_delta(cur[2], prev[2]),
        median_order_value=_delta(cur[3], prev[3]),
        refund_rate=RateDelta(
            current=cur_rate,
            previous=prev_rate,
            change_points=round(cur_rate - prev_rate, 2) if cur_rate is not None and prev_rate is not None else None,
        ),
    )


def compute_trend(orders: pd.DataFrame, window: Window) -> SalesTrend:
    # The moving average runs over the previous period too, so the first days of the
    # selected period already have a full trailing window behind them.
    full = daily(orders, window.previous_start, window.end)
    full["moving_average"] = full["gross_sales"].rolling(MOVING_AVERAGE_DAYS, min_periods=1).mean()
    current = full.loc[pd.Timestamp(window.start) :]
    gross = current["gross_sales"].to_numpy(dtype=np.float64)
    slope = None
    if gross.size >= 2:
        slope = round(float(np.polyfit(np.arange(gross.size, dtype=np.float64), gross, 1)[0]))
    return SalesTrend(
        points=[
            TrendPoint(date=day.date().isoformat(), orders=n, gross_sales=g, moving_average=round(ma))
            for day, n, g, ma in zip(
                pd.DatetimeIndex(current.index),
                current["orders"].tolist(),
                current["gross_sales"].tolist(),
                current["moving_average"].tolist(),
                strict=True,
            )
        ],
        moving_average_days=MOVING_AVERAGE_DAYS,
        slope_per_day=slope,
    )


def compute_weekdays(orders: pd.DataFrame, window: Window) -> list[WeekdayPoint]:
    """Average orders and sales per weekday over the period (Sunday first, as in Saudi Arabia)."""
    days = daily(orders, window.start, window.end)
    weekday = (pd.DatetimeIndex(days.index).dayofweek + 1) % 7  # pandas: Monday=0 -> JavaScript: Sunday=0
    means = days.groupby(weekday).mean().reindex(range(7), fill_value=0)
    return [
        WeekdayPoint(weekday=int(w), average_orders=round(n, 2), average_gross_sales=round(g))
        for w, n, g in zip(means.index, means["orders"].tolist(), means["gross_sales"].tolist(), strict=True)
    ]


def _slices(grouped: pd.DataFrame) -> list[BreakdownSlice]:
    return [
        BreakdownSlice(key=str(key), count=int(n), amount=int(a))
        for key, n, a in zip(grouped.index, grouped["count"].tolist(), grouped["amount"].tolist(), strict=True)
    ]


def _ranked(grouped: pd.DataFrame) -> pd.DataFrame:
    return grouped.sort_values(["count", "amount"], ascending=False, kind="stable")


def compute_statuses(orders: pd.DataFrame, window: Window) -> list[BreakdownSlice]:
    current = _between(orders, window.start, window.end)
    grouped = current.groupby("status").agg(count=("total", "size"), amount=("total", "sum"))
    return _slices(_ranked(grouped.sort_index()))


def compute_payment_methods(payments: pd.DataFrame) -> list[BreakdownSlice]:
    methods = payments.assign(method=payments["method"].fillna("UNKNOWN").replace("", "UNKNOWN"))
    grouped = _ranked(methods.groupby("method").agg(count=("amount", "size"), amount=("amount", "sum")).sort_index())
    if len(grouped) > MAX_PAYMENT_METHODS:
        head = grouped.iloc[: MAX_PAYMENT_METHODS - 1]
        tail = grouped.iloc[MAX_PAYMENT_METHODS - 1 :].sum()
        other = pd.DataFrame({"count": [tail["count"]], "amount": [tail["amount"]]}, index=["OTHER"])
        grouped = pd.concat([head, other])
    return _slices(grouped)


def compute_top_merchants(orders: pd.DataFrame, window: Window, names: dict[str, str]) -> list[RankedItem]:
    current = _between(orders, window.start, window.end)
    grouped = current.groupby("merchant_id").agg(count=("total", "size"), amount=("total", "sum"))
    top = grouped.sort_index().sort_values(["amount", "count"], ascending=False, kind="stable").head(TOP_N)
    return [
        RankedItem(id=str(mid), label=names.get(str(mid), str(mid)), count=int(n), amount=int(a))
        for mid, n, a in zip(top.index, top["count"].tolist(), top["amount"].tolist(), strict=True)
    ]


def compute_top_items(items: pd.DataFrame) -> list[RankedItem]:
    grouped = items.groupby("item_id").agg(label=("label", "last"), count=("quantity", "sum"), amount=("amount", "sum"))
    top = grouped.sort_index().sort_values(["amount", "count"], ascending=False, kind="stable").head(TOP_N)
    return [
        RankedItem(id=str(iid), label=str(label), count=int(n), amount=int(a))
        for iid, label, n, a in zip(
            top.index, top["label"].tolist(), top["count"].tolist(), top["amount"].tolist(), strict=True
        )
    ]


# -- queries ----------------------------------------------------------------------------


def _local_day(column: Any) -> Any:
    return cast(func.timezone(TIMEZONE, column), Date)


async def _fetch_orders(session: AsyncSession, merchant_id: uuid.UUID | None, since: datetime) -> pd.DataFrame:
    stmt = select(
        _local_day(MerchantOrder.paid_at),
        MerchantOrder.total,
        MerchantOrder.status,
        cast(MerchantOrder.merchant_id, String),
    ).where(col(MerchantOrder.paid_at) >= since)
    if merchant_id is not None:
        stmt = stmt.where(MerchantOrder.merchant_id == merchant_id)
    return frame(list((await session.exec(stmt)).all()), ORDER_COLUMNS)


async def _fetch_refunds(session: AsyncSession, merchant_id: uuid.UUID | None, since: datetime) -> pd.DataFrame:
    at = func.coalesce(Refund.completed_at, Refund.created_at)
    stmt = select(_local_day(at), Refund.amount).where(Refund.status == RefundStatus.SUCCEEDED.value, at >= since)
    if merchant_id is not None:
        stmt = stmt.where(Refund.merchant_id == merchant_id)
    return frame(list((await session.exec(stmt)).all()), REFUND_COLUMNS)


async def _fetch_payments(session: AsyncSession, merchant_id: uuid.UUID | None, since: datetime) -> pd.DataFrame:
    stmt = select(Payment.payment_method, Payment.amount).where(
        col(Payment.status).in_([s.value for s in CAPTURED_STATUSES]),
        func.coalesce(Payment.paid_at, Payment.created_at) >= since,
    )
    if merchant_id is not None:
        stmt = stmt.where(Payment.merchant_id == merchant_id)
    return frame(list((await session.exec(stmt)).all()), PAYMENT_COLUMNS, day=False)


async def _fetch_items(session: AsyncSession, merchant_id: uuid.UUID | None, since: datetime) -> pd.DataFrame:
    stmt = (
        select(
            cast(func.coalesce(OrderItem.product_id, OrderItem.service_id), String),
            OrderItem.title,
            OrderItem.quantity,
            OrderItem.line_total,
        )
        .join(MerchantOrder, col(MerchantOrder.id) == col(OrderItem.merchant_order_id))
        .where(col(MerchantOrder.paid_at) >= since)
        .order_by(col(MerchantOrder.paid_at))  # so "last" picks the most recent title
    )
    if merchant_id is not None:
        stmt = stmt.where(MerchantOrder.merchant_id == merchant_id)
    return frame(list((await session.exec(stmt)).all()), ITEM_COLUMNS, day=False)


async def _merchant_names(session: AsyncSession, ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    rows = await session.exec(
        select(Merchant.id, Merchant.business_name).where(col(Merchant.id).in_([uuid.UUID(i) for i in ids]))
    )
    return {str(mid): name for mid, name in rows.all()}


async def build(
    session: AsyncSession, merchant_id: uuid.UUID | None, days: int, now: datetime | None = None
) -> Analytics:
    window = Window.ending(days, now)
    since_previous, since_current = Window.utc(window.previous_start), Window.utc(window.start)
    orders = await _fetch_orders(session, merchant_id, since_previous)
    refunds = await _fetch_refunds(session, merchant_id, since_previous)
    payments = await _fetch_payments(session, merchant_id, since_current)
    items = await _fetch_items(session, merchant_id, since_current)
    top_merchants: list[RankedItem] = []
    if merchant_id is None:
        ranked = compute_top_merchants(orders, window, {})
        names = await _merchant_names(session, [r.id for r in ranked])
        top_merchants = [r.model_copy(update={"label": names.get(r.id, r.label)}) for r in ranked]
    return Analytics(
        days=days,
        start=window.start.isoformat(),
        end=window.end.isoformat(),
        kpis=compute_kpis(orders, refunds, window),
        trend=compute_trend(orders, window),
        weekdays=compute_weekdays(orders, window),
        order_statuses=compute_statuses(orders, window),
        payment_methods=compute_payment_methods(payments),
        top_merchants=top_merchants,
        top_items=compute_top_items(items),
    )
