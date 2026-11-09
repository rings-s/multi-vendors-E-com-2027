"""Dashboard analytics: the pandas/numpy computations and the scoped endpoints."""

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.modules.analytics import service as analytics
from app.modules.analytics.service import ITEM_COLUMNS, ORDER_COLUMNS, PAYMENT_COLUMNS, REFUND_COLUMNS, Window, frame
from tests.helpers import API, Client, active_merchant, create_admin, create_product, paid_order, register_customer

# 2026-11-07 is a Saturday; the 7-day window is Sun 2026-11-01 .. Sat 2026-11-07,
# and the previous period is Sun 2026-10-25 .. Sat 2026-10-31.
NOW = datetime(2026, 11, 7, 12, tzinfo=UTC)
WINDOW = Window.ending(7, NOW)


def orders(*rows: tuple[str, int, str, str]) -> Any:
    return frame([(date.fromisoformat(d), t, s, m) for d, t, s, m in rows], ORDER_COLUMNS)


def refunds(*rows: tuple[str, int]) -> Any:
    return frame([(date.fromisoformat(d), a) for d, a in rows], REFUND_COLUMNS)


def test_window_uses_riyadh_calendar_days() -> None:
    assert (WINDOW.start, WINDOW.end) == (date(2026, 11, 1), date(2026, 11, 7))
    assert WINDOW.previous_start == date(2026, 10, 25)
    # 22:30 UTC is already the next day in Riyadh (UTC+3).
    assert Window.ending(7, datetime(2026, 11, 7, 22, 30, tzinfo=UTC)).end == date(2026, 11, 8)


def test_kpis_compare_with_the_previous_period() -> None:
    df = orders(
        ("2026-10-26", 10000, "COMPLETED", "m1"),
        ("2026-10-30", 10000, "COMPLETED", "m1"),
        ("2026-11-01", 10000, "PAID", "m1"),
        ("2026-11-03", 20000, "PAID", "m2"),
        ("2026-11-07", 60000, "SHIPPED", "m1"),
        ("2026-10-01", 99999, "PAID", "m1"),  # outside both periods
    )
    kpis = analytics.compute_kpis(df, refunds(("2026-11-02", 4500), ("2026-10-27", 1000)), WINDOW)
    assert kpis.gross_sales.model_dump() == {"current": 90000, "previous": 20000, "change_pct": 350.0}
    assert kpis.orders.model_dump() == {"current": 3, "previous": 2, "change_pct": 50.0}
    assert kpis.average_order_value.current == 30000
    assert kpis.median_order_value.current == 20000
    assert kpis.refund_rate.model_dump() == {"current": 5.0, "previous": 5.0, "change_points": 0.0}


def test_kpis_without_history_have_no_change() -> None:
    kpis = analytics.compute_kpis(orders(("2026-11-02", 500, "PAID", "m1")), refunds(), WINDOW)
    assert kpis.gross_sales.change_pct is None
    assert kpis.refund_rate.previous is None and kpis.refund_rate.change_points is None


def test_trend_fills_empty_days_and_carries_the_moving_average_across_periods() -> None:
    df = orders(("2026-10-31", 7000, "PAID", "m1"), ("2026-11-07", 14000, "PAID", "m1"))
    trend = analytics.compute_trend(df, WINDOW)
    assert [p.date for p in trend.points] == [f"2026-11-0{d}" for d in range(1, 8)]
    assert [p.gross_sales for p in trend.points] == [0, 0, 0, 0, 0, 0, 14000]
    # 2026-11-01's trailing 7 days include 2026-10-31 from the previous period.
    assert trend.points[0].moving_average == 1000
    assert trend.points[-1].moving_average == 2000
    assert trend.moving_average_days == 7
    assert trend.slope_per_day is not None and trend.slope_per_day > 0


def test_trend_slope_is_the_least_squares_fit() -> None:
    df = orders(*[(f"2026-11-0{d}", 1000 * d, "PAID", "m1") for d in range(1, 8)])
    assert analytics.compute_trend(df, WINDOW).slope_per_day == 1000


def test_weekdays_start_on_sunday() -> None:
    df = orders(("2026-11-01", 3000, "PAID", "m1"), ("2026-11-01", 1000, "PAID", "m1"))  # Sunday
    weekdays = analytics.compute_weekdays(df, WINDOW)
    assert [w.weekday for w in weekdays] == list(range(7))
    assert (weekdays[0].average_orders, weekdays[0].average_gross_sales) == (2.0, 4000)
    assert all(w.average_orders == 0 for w in weekdays[1:])


def test_statuses_are_ranked_by_count() -> None:
    df = orders(
        ("2026-11-02", 100, "PAID", "m1"),
        ("2026-11-02", 900, "SHIPPED", "m1"),
        ("2026-11-03", 200, "PAID", "m1"),
        ("2026-10-28", 100, "CANCELLED", "m1"),  # previous period
    )
    assert [(s.key, s.count, s.amount) for s in analytics.compute_statuses(df, WINDOW)] == [
        ("PAID", 2, 300),
        ("SHIPPED", 1, 900),
    ]


def test_payment_methods_fold_the_tail_into_other() -> None:
    rows = [("applepay", 500)] * 4 + [("card", 100)] * 3 + [("stcpay", 50)] * 2 + [(None, 10), ("mada", 20)]
    slices = analytics.compute_payment_methods(frame(rows, PAYMENT_COLUMNS, day=False))
    assert [(s.key, s.count, s.amount) for s in slices] == [
        ("applepay", 4, 2000),
        ("card", 3, 300),
        ("stcpay", 2, 100),
        ("OTHER", 2, 30),
    ]


def test_top_items_rank_by_revenue_and_use_the_latest_title() -> None:
    items = frame(
        [("p1", "Oud", 1, 1000), ("p2", "Musk", 5, 500), ("p1", "Oud (new)", 2, 2000)], ITEM_COLUMNS, day=False
    )
    top = analytics.compute_top_items(items)
    assert [(t.id, t.label, t.count, t.amount) for t in top] == [("p1", "Oud (new)", 3, 3000), ("p2", "Musk", 5, 500)]


def test_top_merchants_use_names() -> None:
    df = orders(("2026-11-02", 100, "PAID", "a"), ("2026-11-02", 500, "PAID", "b"), ("2026-11-03", 100, "PAID", "a"))
    top = analytics.compute_top_merchants(df, WINDOW, {"b": "Najd Oud"})
    assert [(t.label, t.count, t.amount) for t in top] == [("Najd Oud", 1, 500), ("a", 2, 200)]


def test_empty_data_produces_zeroed_charts() -> None:
    empty_orders, empty_refunds = orders(), refunds()
    assert analytics.compute_kpis(empty_orders, empty_refunds, WINDOW).gross_sales.current == 0
    assert len(analytics.compute_trend(empty_orders, WINDOW).points) == 7
    assert analytics.compute_trend(empty_orders, WINDOW).slope_per_day == 0
    assert analytics.compute_statuses(empty_orders, WINDOW) == []
    assert analytics.compute_payment_methods(frame([], PAYMENT_COLUMNS, day=False)) == []
    assert analytics.compute_top_items(frame([], ITEM_COLUMNS, day=False)) == []


# -- endpoints --------------------------------------------------------------------------


async def test_analytics_endpoints_are_computed_from_data_and_scoped(client: Client) -> None:
    admin = await create_admin(client)
    before = await client.get(f"{API}/admin/analytics", admin, params={"days": 7})
    merchant = await active_merchant(client, admin)
    other = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    other_product = await create_product(client, other)
    customer = await register_customer(client)
    await paid_order(client, customer, product)
    await paid_order(client, customer, other_product)

    after = await client.get(f"{API}/admin/analytics", admin, params={"days": 7})
    assert after["days"] == 7 and len(after["trend"]["points"]) == 7
    assert after["kpis"]["orders"]["current"] == before["kpis"]["orders"]["current"] + 2
    assert after["kpis"]["gross_sales"]["current"] == before["kpis"]["gross_sales"]["current"] + 2 * 11500
    assert after["trend"]["points"][-1]["date"] == after["end"]
    assert sum(w["average_orders"] for w in after["weekdays"]) > 0
    assert merchant.extra["merchant_id"] in {m["id"] for m in after["top_merchants"]}

    mine = await client.get(f"{API}/merchant/analytics", merchant)
    assert mine["days"] == 30
    assert mine["kpis"]["orders"]["current"] == 1
    assert mine["kpis"]["gross_sales"]["current"] == 11500
    assert mine["top_merchants"] == []
    assert [i["id"] for i in mine["top_items"]] == [product["id"]]
    assert [(s["key"], s["count"]) for s in mine["payment_methods"]] == [("mock", 1)]
    assert sum(s["count"] for s in mine["order_statuses"]) == 1


@pytest.mark.parametrize("days", [3, 366])
async def test_analytics_period_is_bounded(client: Client, days: int) -> None:
    admin = await create_admin(client)
    await client.get(f"{API}/admin/analytics", admin, params={"days": days}, expect=422)


async def test_analytics_requires_the_right_role(client: Client) -> None:
    customer = await register_customer(client)
    assert (await client.request("GET", f"{API}/admin/analytics", customer)).status_code == 403
    assert (await client.request("GET", f"{API}/merchant/analytics", customer)).status_code == 403
