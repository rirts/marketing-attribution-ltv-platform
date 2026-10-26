import pandas as pd
from scripts.attribution import compute_attribution, model_linear, model_time_decay
from scripts.ltv import compute_ltv


def test_attribution_reconciles_cents_and_preserves_unattributed():
    orders = pd.DataFrame(
        {
            "order_id": [1, 2],
            "customer_id": [1, 2],
            "order_ts": pd.to_datetime(["2025-02-01"] * 2),
            "amount": [100.0, 5.0],
        }
    )
    touches = pd.DataFrame(
        {
            "customer_id": [1] * 3,
            "channel_id": [1, 2, 3],
            "event_ts": pd.to_datetime(["2025-01-30", "2025-01-31", "2025-02-01"]),
        }
    )
    result = compute_attribution(orders, touches)
    assert result.groupby("model").attributed_revenue.sum().round(2).eq(105).all()
    assert set(result[result.order_id == 2].channel_id) == {-1}
    for fn in [
        model_linear,
        lambda t, a: model_time_decay(t, pd.Timestamp("2025-02-01"), a),
    ]:
        assert round(sum(x[2] for x in fn(touches, 100)), 2) == 100


def test_ltv_includes_zero_buyers_and_excludes_immature_horizons():
    customers = pd.DataFrame(
        {
            "customer_id": [1, 2, 3],
            "signup_date": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-03-01"]),
        }
    )
    orders = pd.DataFrame(
        {
            "order_id": [1],
            "customer_id": [1],
            "order_ts": pd.to_datetime(["2025-01-15"]),
            "amount": [100.0],
        }
    )
    result = compute_ltv(customers, orders, as_of_date="2025-03-05")
    assert result[result.horizon_days == 30].revenue.mean() == 50
    assert set(result.customer_id) == {1, 2}
    assert not result.horizon_days.isin([90, 180]).any()


def test_empty_orders_produce_zeros_for_observed_customers():
    customers = pd.DataFrame(
        {"customer_id": [1], "signup_date": pd.to_datetime(["2025-01-01"])}
    )
    result = compute_ltv(customers, pd.DataFrame(), as_of_date="2025-12-31")
    assert len(result) == 4
    assert result.revenue.eq(0).all()
