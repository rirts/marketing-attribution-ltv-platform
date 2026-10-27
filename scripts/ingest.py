import os
import pandas as pd
from sqlalchemy import text
from common.db import get_engine

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
RAW_DIR = os.path.join(ROOT, "data", "raw")


def main():
    eng = get_engine()

    # 0) Truncar tablas en orden seguro por FKs
    print("Limpiando tablas...")
    with eng.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for tbl in [
            "fact_attribution",
            "fact_ltv_cohort",
            "fact_events",
            "fact_marketing_spend",
            "fact_orders",
            "fact_touches",
            "dim_customer",
            "dim_channel",
        ]:
            conn.execute(text(f"TRUNCATE TABLE {tbl}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))

    # 1) Cargar CSVs
    print("Leyendo CSVs...")
    channels = pd.read_csv(os.path.join(RAW_DIR, "channels.csv"))
    customers = pd.read_csv(os.path.join(RAW_DIR, "customers.csv"))
    orders = pd.read_csv(os.path.join(RAW_DIR, "orders.csv"), parse_dates=["order_ts"])
    touches = pd.read_csv(
        os.path.join(RAW_DIR, "touches.csv"), parse_dates=["event_ts"]
    )
    spend = pd.read_csv(os.path.join(RAW_DIR, "spend.csv"), parse_dates=["spend_date"])
    events = pd.read_csv(os.path.join(RAW_DIR, "events.csv"), parse_dates=["event_ts"])

    # 2) Insertar dimensiones
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO dim_channel (channel_id, channel_name, channel_group) VALUES (-1, 'Unattributed', 'Unattributed')"
            )
        )

    print("Insertando dim_channel...")
    with eng.begin() as conn:
        for _, r in channels.iterrows():
            conn.execute(
                text("""
                INSERT INTO dim_channel (channel_name, channel_group)
                VALUES (:name, :grp)
            """),
                {"name": r.channel_name, "grp": r.get("channel_group")},
            )

    print("Insertando dim_customer...")
    with eng.begin() as conn:
        for _, r in customers.iterrows():
            conn.execute(
                text("""
                INSERT INTO dim_customer (external_id, signup_date, country)
                VALUES (:ext, :sd, :cty)
            """),
                {"ext": r.external_id, "sd": str(r.signup_date), "cty": r.country},
            )

    # 3) Mapas de IDs
    with eng.begin() as conn:
        ch_map = dict(
            conn.execute(text("SELECT channel_name, channel_id FROM dim_channel")).all()
        )
        cust_map = dict(
            conn.execute(
                text("SELECT external_id, customer_id FROM dim_customer")
            ).all()
        )

    # 4) Insertar fact_touches
    print("Insertando fact_touches...")
    with eng.begin() as conn:
        for _, r in touches.iterrows():
            conn.execute(
                text("""
                INSERT INTO fact_touches (event_ts, customer_id, channel_id, campaign, session_id, revenue_at_event)
                VALUES (:ts, :cid, :chid, :cmp, :sid, :rev)
            """),
                {
                    "ts": r.event_ts.to_pydatetime(),
                    "cid": cust_map.get(r.external_id),
                    "chid": ch_map[r.channel_name],
                    "cmp": r.get("campaign"),
                    "sid": r.get("session_id"),
                    "rev": float(r.get("revenue_at_event", 0.0) or 0.0),
                },
            )

    # 5) Insertar fact_orders
    print("Insertando fact_orders...")
    with eng.begin() as conn:
        for _, r in orders.iterrows():
            conn.execute(
                text("""
                INSERT INTO fact_orders (order_id, order_ts, customer_id, amount)
                VALUES (:oid, :ts, :cid, :amt)
            """),
                {
                    "oid": int(r.order_id),
                    "ts": r.order_ts.to_pydatetime(),
                    "cid": cust_map[r.external_id],
                    "amt": float(r.amount),
                },
            )

    # 6) Insertar fact_marketing_spend
    print("Insertando fact_marketing_spend...")
    with eng.begin() as conn:
        for _, r in spend.iterrows():
            conn.execute(
                text("""
                INSERT INTO fact_marketing_spend (spend_date, channel_id, spend)
                VALUES (:dt, :chid, :sp)
            """),
                {
                    "dt": r.spend_date.date(),
                    "chid": ch_map[r.channel_name],
                    "sp": float(r.spend),
                },
            )

    # 7) NUEVO: Insertar fact_events
    print("Insertando fact_events...")
    with eng.begin() as conn:
        for _, r in events.iterrows():
            conn.execute(
                text("""
                INSERT INTO fact_events (event_ts, customer_id, channel_id, event_type, product_id, order_id)
                VALUES (:ts, :cid, :chid, :etype, :pid, :oid)
            """),
                {
                    "ts": r.event_ts.to_pydatetime(),
                    "cid": cust_map[r.external_id],
                    "chid": ch_map[r.channel_name],
                    "etype": r.event_type,
                    "pid": None
                    if pd.isna(r.get("product_id"))
                    else int(r.get("product_id")),
                    "oid": None
                    if pd.isna(r.get("order_id"))
                    else int(r.get("order_id")),
                },
            )

    print("Ingesta completada ✔")


if __name__ == "__main__":
    main()
