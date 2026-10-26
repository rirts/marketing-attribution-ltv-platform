import os
import pandas as pd
from sqlalchemy import text
from common.db import get_engine

HORIZONS = [30, 60, 90, 180]


def load_customers_orders(eng):
    q_cust = "SELECT customer_id, signup_date FROM dim_customer;"
    q_ord = "SELECT order_id, customer_id, order_ts, amount FROM fact_orders;"

    cust = pd.read_sql(q_cust, eng, parse_dates=["signup_date"])
    orders = pd.read_sql(q_ord, eng, parse_dates=["order_ts"])
    return cust, orders


def compute_ltv(cust, orders, as_of_date=None):
    """Observed cumulative revenue per acquired customer at fully observed horizons.

    Zero-purchase customers are included. Immature horizons are absent (unknown),
    rather than silently treated as zero. The observation end is explicit or the
    latest source observation, never an invented future date.
    """
    columns = ["cohort_month", "customer_id", "horizon_days", "revenue"]
    if cust.empty:
        return pd.DataFrame(columns=columns)
    if as_of_date is None:
        as_of_date = os.getenv("ANALYTICS_AS_OF_DATE")
    if as_of_date is None:
        dates = [cust.signup_date.max()]
        if not orders.empty:
            dates.append(orders.order_ts.max())
        as_of_date = max(d for d in dates if pd.notna(d))
    cutoff = pd.Timestamp(as_of_date)
    if cutoff == cutoff.normalize():
        cutoff += pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    c = cust.copy()
    c["signup_date"] = pd.to_datetime(c.signup_date)
    c["cohort_month"] = c.signup_date.dt.to_period("M").dt.to_timestamp()
    o = orders.copy()
    if not o.empty:
        o["order_ts"] = pd.to_datetime(o.order_ts)
        o = o[o.order_ts <= cutoff].merge(
            c[["customer_id", "signup_date"]], on="customer_id", validate="many_to_one"
        )
        o["age"] = (o.order_ts - o.signup_date).dt.total_seconds() / 86400
    rows = []
    for h in HORIZONS:
        eligible = c[c.signup_date + pd.to_timedelta(h, unit="D") <= cutoff][
            ["cohort_month", "customer_id"]
        ].copy()
        totals = (
            o[(o.age >= 0) & (o.age <= h)].groupby("customer_id").amount.sum()
            if not o.empty
            else pd.Series(dtype=float)
        )
        eligible["revenue"] = eligible.customer_id.map(totals).fillna(0.0)
        eligible["horizon_days"] = h
        rows.append(eligible)
    return pd.concat(rows, ignore_index=True)[columns]


def write_fact_ltv(eng, df):
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM fact_ltv_cohort"))
        if df.empty:
            return
        rows = df.to_dict("records")
        conn.execute(
            text("""
            INSERT INTO fact_ltv_cohort (cohort_month, customer_id, horizon_days, revenue)
            VALUES (:cohort_month, :customer_id, :horizon_days, :revenue)
        """),
            rows,
        )


def main():
    eng = get_engine()
    cust, orders = load_customers_orders(eng)
    print(f"Clientes: {len(cust)}, Órdenes: {len(orders)}")
    df_ltv = compute_ltv(cust, orders)
    print(f"Filas LTV: {len(df_ltv)}")
    write_fact_ltv(eng, df_ltv)
    print("LTV calculado y escrito en fact_ltv_cohort ✔")


if __name__ == "__main__":
    main()
