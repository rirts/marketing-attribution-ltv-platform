"""Verify persisted attribution conservation and purchase identity after a build."""

from sqlalchemy import text
from common.db import get_engine


def main():
    engine = get_engine()
    checks = {
        "attribution_conservation": """
            SELECT COUNT(*) FROM (
                SELECT o.order_id, models.model
                FROM fact_orders o
                CROSS JOIN (
                    SELECT 'first_click' AS model UNION ALL SELECT 'last_click'
                    UNION ALL SELECT 'linear' UNION ALL SELECT 'time_decay'
                ) models
                LEFT JOIN fact_attribution a
                  ON a.order_id = o.order_id AND a.model = models.model
                GROUP BY o.order_id, o.amount, models.model
                HAVING COUNT(a.attr_id) = 0
                   OR SUM(a.attributed_revenue) <> o.amount
            ) violations
        """,
        "purchase_customer_identity": """
            SELECT COUNT(*) FROM fact_events e
            LEFT JOIN fact_orders o ON e.order_id = o.order_id
            WHERE e.event_type = 'purchase'
              AND (o.order_id IS NULL OR e.customer_id <> o.customer_id)
        """,
        "ltv_domain": """
            SELECT COUNT(*) FROM fact_ltv_cohort
            WHERE revenue < 0 OR horizon_days NOT IN (30, 60, 90, 180)
        """,
    }
    try:
        with engine.connect() as conn:
            if conn.execute(text("SELECT COUNT(*) FROM fact_orders")).scalar_one() == 0:
                raise RuntimeError("Load the source orders before verification")
            for name, query in checks.items():
                violations = conn.execute(text(query)).scalar_one()
                if violations:
                    raise RuntimeError(f"{name}: {violations} violations")
                print(f"PASS {name}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
