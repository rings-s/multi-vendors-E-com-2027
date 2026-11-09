"""Response shapes for the dashboard analytics endpoints. Money is in halalas."""

from pydantic import BaseModel


class Delta(BaseModel):
    """A figure for the selected period next to the same figure for the period before it."""

    current: int
    previous: int
    change_pct: float | None  # relative change in percent; None when the previous period is 0


class RateDelta(BaseModel):
    """A percentage (0-100) for both periods; ``change_points`` is the difference in points."""

    current: float | None
    previous: float | None
    change_points: float | None


class AnalyticsKpis(BaseModel):
    gross_sales: Delta
    orders: Delta
    average_order_value: Delta
    median_order_value: Delta
    refund_rate: RateDelta  # successful refunds as a share of gross sales


class TrendPoint(BaseModel):
    date: str  # ISO date, Asia/Riyadh
    orders: int
    gross_sales: int
    moving_average: int  # trailing mean of gross_sales over ``moving_average_days``


class SalesTrend(BaseModel):
    points: list[TrendPoint]
    moving_average_days: int
    slope_per_day: int | None  # least-squares slope of daily gross sales, halalas per day


class WeekdayPoint(BaseModel):
    weekday: int  # 0 = Sunday ... 6 = Saturday (JavaScript ``Date.getDay()``)
    average_orders: float
    average_gross_sales: int


class BreakdownSlice(BaseModel):
    key: str  # an enum value (order status, payment method) or ``OTHER`` / ``UNKNOWN``
    count: int
    amount: int


class RankedItem(BaseModel):
    id: str
    label: str
    count: int  # orders for merchants, units sold for products and services
    amount: int


class Analytics(BaseModel):
    currency: str = "SAR"
    days: int
    start: str  # first day of the period (inclusive)
    end: str  # last day of the period (inclusive, today)
    kpis: AnalyticsKpis
    trend: SalesTrend
    weekdays: list[WeekdayPoint]
    order_statuses: list[BreakdownSlice]
    payment_methods: list[BreakdownSlice]
    top_merchants: list[RankedItem]  # marketplace view only; empty for a merchant
    top_items: list[RankedItem]  # best-selling products and services
