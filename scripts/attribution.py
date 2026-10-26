from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
import pandas as pd
from sqlalchemy import text, select
from common.db import get_engine

WINDOW_DAYS = 30
HALF_LIFE_DAYS = 7  # para time-decay


def load_data(eng):
    # Cargamos orders y touches con los IDs ya en DB
    q_orders = """
        SELECT o.order_id, o.order_ts, o.customer_id, o.amount
        FROM fact_orders o
    """
    q_touches = """
        SELECT t.touch_id, t.event_ts, t.customer_id, t.channel_id
        FROM fact_touches t
    """
    orders = pd.read_sql(q_orders, eng, parse_dates=["order_ts"])
    touches = pd.read_sql(q_touches, eng, parse_dates=["event_ts"])
    return orders, touches


def window_touches_for_order(touches_cust, order_ts):
    start = order_ts - timedelta(days=WINDOW_DAYS)
    return touches_cust[
        (touches_cust["event_ts"] <= order_ts) & (touches_cust["event_ts"] >= start)
    ].copy()


def model_last_click(tws, amount):
    if tws.empty:
        return []
    row = tws.sort_values("event_ts").iloc[-1]
    return [(row.channel_id, 1.0, amount)]


def model_first_click(tws, amount):
    if tws.empty:
        return []
    row = tws.sort_values("event_ts").iloc[0]
    return [(row.channel_id, 1.0, amount)]


def allocate_revenue(channels, weights, amount):
    """Allocate whole cents, placing rounding residue by largest fractional remainder."""
    cents = int(
        (Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    if cents < 0:
        raise ValueError("This demo expects non-negative order amounts")
    weights = [Decimal(str(w)) for w in weights]
    total = sum(weights)
    raw = [Decimal(cents) * w / total for w in weights]
    allocated = [int(v) for v in raw]
    remainder = cents - sum(allocated)
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - allocated[i], reverse=True)[
        :remainder
    ]:
        allocated[i] += 1
    return [
        (int(ch), float(w / total), value / 100)
        for ch, w, value in zip(channels, weights, allocated)
    ]


def model_linear(tws, amount):
    if tws.empty:
        return []
    return allocate_revenue(tws.channel_id, [1] * len(tws), amount)


def model_time_decay(tws, order_ts, amount):
    if tws.empty:
        return []
    delta = (order_ts - tws.event_ts).dt.total_seconds() / 86400
    return allocate_revenue(tws.channel_id, 0.5 ** (delta / HALF_LIFE_DAYS), amount)


def compute_attribution(orders, touches):
    # Pre-split touches by customer for rapidez
    touches_by_c = {cid: df for cid, df in touches.groupby("customer_id")}
    rows = []

    for _, o in orders.iterrows():
        cid, ots, amt, oid = (
            int(o.customer_id),
            o.order_ts,
            float(o.amount),
            int(o.order_id),
        )
        tws = touches_by_c.get(cid, pd.DataFrame(columns=["event_ts", "channel_id"]))
        tws = window_touches_for_order(tws, ots)

        if tws.empty:
            for model in ["last_click", "first_click", "linear", "time_decay"]:
                rows.append((oid, model, -1, 1.0, round(amt, 2)))
            continue

        # last_click
        for ch, w, ar in model_last_click(tws, amt):
            rows.append((oid, "last_click", ch, w, round(amt * w, 2)))
        # first_click
        for ch, w, ar in model_first_click(tws, amt):
            rows.append((oid, "first_click", ch, w, round(amt * w, 2)))
        # linear
        for ch, w, ar in model_linear(tws, amt):
            rows.append((oid, "linear", ch, w, ar))
        # time_decay
        for ch, w, ar in model_time_decay(tws, ots, amt):
            rows.append((oid, "time_decay", ch, w, ar))

    df = pd.DataFrame(
        rows,
        columns=["order_id", "model", "channel_id", "weight", "attributed_revenue"],
    )
    return df


def write_fact_attribution(eng, df):
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM fact_attribution"))
        if df.empty:
            return
        # insert masivo por chunks
        rows = df.to_dict("records")
        conn.execute(
            text("""
            INSERT INTO fact_attribution (order_id, model, channel_id, weight, attributed_revenue)
            VALUES (:order_id, :model, :channel_id, :weight, :attributed_revenue)
        """),
            rows,
        )


def main():
    eng = get_engine()
    orders, touches = load_data(eng)
    print(f"Pedidos: {len(orders)}, Touches: {len(touches)}")
    df_attr = compute_attribution(orders, touches)
    print(f"Filas de atribución: {len(df_attr)}")
    write_fact_attribution(eng, df_attr)
    print("Atribución calculada y escrita en fact_attribution ✔")


if __name__ == "__main__":
    main()
