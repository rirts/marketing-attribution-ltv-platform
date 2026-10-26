import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
RAW_DIR = os.path.join(ROOT, "data", "raw")
os.makedirs(RAW_DIR, exist_ok=True)

np.random.seed(42)

# 1) Canales
channels = [
    {"channel_name": "Google Ads", "channel_group": "Paid Search"},
    {"channel_name": "Facebook Ads", "channel_group": "Paid Social"},
    {"channel_name": "Instagram", "channel_group": "Paid Social"},
    {"channel_name": "Email", "channel_group": "Owned"},
    {"channel_name": "Direct", "channel_group": "Direct"},
    {"channel_name": "Referral", "channel_group": "Referral"},
]
df_channels = pd.DataFrame(channels)

# 2) Clientes
n_customers = 80
start_date = datetime(2024, 11, 1)
end_date = datetime(2025, 7, 31)

signup_dates = [
    start_date + timedelta(days=int(np.random.uniform(0, (end_date - start_date).days)))
    for _ in range(n_customers)
]
countries = np.random.choice(["MX", "US", "CO"], size=n_customers, p=[0.7, 0.2, 0.1])
df_customers = pd.DataFrame(
    {
        "external_id": [f"C{str(i + 1).zfill(4)}" for i in range(n_customers)],
        "signup_date": [d.date() for d in signup_dates],
        "country": countries,
    }
)

# 3) Órdenes por cliente
orders_rows = []
order_id_seq = 1
for _, row in df_customers.iterrows():
    num_orders = np.random.poisson(1.2)  # ~1-2 órdenes promedio
    last_ts = datetime.combine(row.signup_date, datetime.min.time()) + timedelta(
        days=np.random.randint(0, 7)
    )
    for _ in range(num_orders):
        order_ts = last_ts + timedelta(
            days=np.random.randint(3, 60),
            hours=np.random.randint(0, 24),
            minutes=np.random.randint(0, 60),
        )
        amount = float(np.round(np.random.lognormal(mean=4.2, sigma=0.5), 2))
        orders_rows.append(
            {
                "order_id": order_id_seq,
                "order_ts": order_ts,
                "external_id": row.external_id,
                "amount": amount,
            }
        )
        order_id_seq += 1
        last_ts = order_ts
df_orders = pd.DataFrame(orders_rows)

# 4) Touches previos a cada orden (3-6 por orden)
touches_rows = []
for _, o in df_orders.iterrows():
    n_t = np.random.randint(3, 7)
    base = o.order_ts - timedelta(days=np.random.randint(1, 25))
    session = f"S{int(np.random.randint(1e6))}"
    for i in range(n_t):
        event_ts = base + timedelta(hours=2 * i + np.random.randint(0, 60) / 60)
        ch = df_channels.sample(1).iloc[0]
        touches_rows.append(
            {
                "event_ts": event_ts,
                "external_id": o.external_id,
                "channel_name": ch.channel_name,
                "campaign": f"{ch.channel_name} / {2025 if event_ts.year == 2025 else 2024}",
                "session_id": session,
                "revenue_at_event": 0.0,
            }
        )
df_touches = pd.DataFrame(touches_rows)

# 5) Spend diario por canal
all_dates = pd.date_range(start=start_date.date(), end=end_date.date(), freq="D")
spend_rows = []
for d in all_dates:
    for _, ch in df_channels.iterrows():
        spend = float(np.round(max(0, np.random.normal(loc=200, scale=80)), 2))
        spend_rows.append(
            {
                "spend_date": d,
                "channel_name": ch.channel_name,
                "spend": spend,
            }
        )
df_spend = pd.DataFrame(spend_rows)

# 6) NUEVO: Eventos (views, add_to_cart, purchase)
events_rows = []
# a) Views y AddToCart aleatorios por cliente
for _, c in df_customers.iterrows():
    n_views = np.random.randint(3, 11)
    n_carts = np.random.randint(1, max(2, n_views // 2))
    for _ in range(n_views):
        ts = datetime.combine(c.signup_date, datetime.min.time()) + timedelta(
            days=np.random.randint(0, 45),
            hours=np.random.randint(0, 24),
            minutes=np.random.randint(0, 60),
        )
        ch = df_channels.sample(1).iloc[0]
        events_rows.append(
            {
                "event_ts": ts,
                "external_id": c.external_id,
                "channel_name": ch.channel_name,
                "event_type": "view_product",
                "product_id": None,
                "order_id": None,
            }
        )
    for _ in range(n_carts):
        ts = datetime.combine(c.signup_date, datetime.min.time()) + timedelta(
            days=np.random.randint(0, 45),
            hours=np.random.randint(0, 24),
            minutes=np.random.randint(0, 60),
        )
        ch = df_channels.sample(1).iloc[0]
        events_rows.append(
            {
                "event_ts": ts,
                "external_id": c.external_id,
                "channel_name": ch.channel_name,
                "event_type": "add_to_cart",
                "product_id": None,
                "order_id": None,
            }
        )

# b) Purchases: uno por cada orden existente (vinculado a order_id)
for _, o in df_orders.iterrows():
    ch = df_channels.sample(1).iloc[
        0
    ]  # si quieres, cámbialo por canal del último touch
    events_rows.append(
        {
            "event_ts": o.order_ts,
            "external_id": o.external_id,
            "channel_name": ch.channel_name,
            "event_type": "purchase",
            "product_id": None,
            "order_id": int(o.order_id),
        }
    )

df_events = pd.DataFrame(events_rows)

# ===== Guardar CSVs =====
df_channels.to_csv(os.path.join(RAW_DIR, "channels.csv"), index=False)
df_customers.to_csv(os.path.join(RAW_DIR, "customers.csv"), index=False)
df_orders.to_csv(os.path.join(RAW_DIR, "orders.csv"), index=False)
df_touches.to_csv(os.path.join(RAW_DIR, "touches.csv"), index=False)
df_spend.to_csv(os.path.join(RAW_DIR, "spend.csv"), index=False)
df_events.to_csv(os.path.join(RAW_DIR, "events.csv"), index=False)

print("CSV generados en:", RAW_DIR)
