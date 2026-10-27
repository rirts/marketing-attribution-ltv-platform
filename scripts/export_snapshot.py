"""Build and restore-test a portable demo snapshot in the MySQL CI service."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from sqlalchemy import create_engine, inspect, text
from common.db import get_engine

SOURCE_DB = "analytics_portfolio"
TARGET_DB = "analytics_portfolio_corrected"
TABLES = (
    "dim_channel",
    "dim_customer",
    "fact_orders",
    "fact_touches",
    "fact_marketing_spend",
    "fact_events",
    "fact_attribution",
    "fact_ltv_cohort",
)
OUTPUT = Path(__file__).resolve().parents[1] / "artifacts"


def docker_client(program, arguments, *, stdin=None, stdout=None):
    container = os.environ["MYSQL_CONTAINER_ID"]
    command = ["docker", "exec"]
    if stdin is not None:
        command.append("-i")
    command.extend([
        container,
        "sh", "-c",
        'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec "$@"',
        "mysql-client", program, "--user=root", *arguments,
    ])
    subprocess.run(command, stdin=stdin, stdout=stdout, check=True)


def fingerprint(engine):
    results = {}
    schema = inspect(engine)
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.connect() as conn:
        for table in TABLES:
            keys = schema.get_pk_constraint(table)["constrained_columns"]
            if not keys:
                raise RuntimeError(f"Missing primary key: {table}")
            order = ", ".join(quote(key) for key in keys)
            rows = conn.execute(
                text(f"SELECT * FROM {quote(table)} ORDER BY {order}")
            ).all()
            serialized = json.dumps(
                [list(row) for row in rows],
                default=str, ensure_ascii=False, allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
            results[table] = {
                "rows": len(rows),
                "sha256": hashlib.sha256(serialized).hexdigest(),
            }
    return results


def main():
    OUTPUT.mkdir(exist_ok=True)
    snapshot = OUTPUT / "marketing_corregido.sql"
    source = get_engine()
    restored = None
    try:
        if source.url.database != SOURCE_DB:
            raise RuntimeError("This exporter only supports the isolated demo CI database")
        before = fingerprint(source)
        # A fresh destination and no DROP/DELETE/TRUNCATE statements preserve any
        # existing analytics_portfolio database on the importing computer.
        snapshot.write_text(
            "-- Datos de ejemplo generados por el pipeline Python corregido.\n"
            "-- Carga unica en una base nueva: analytics_portfolio_corrected.\n"
            "CREATE DATABASE analytics_portfolio_corrected "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
            "USE analytics_portfolio_corrected;\n",
            encoding="utf-8",
        )
        with snapshot.open("ab") as output:
            docker_client("mysqldump", [
                "--single-transaction", "--skip-lock-tables", "--no-tablespaces",
                "--set-gtid-purged=OFF", "--column-statistics=0",
                "--default-character-set=utf8mb4",
                "--skip-add-drop-table", "--skip-add-locks", "--skip-disable-keys",
                "--skip-comments", "--skip-dump-date", "--order-by-primary",
                "--complete-insert", "--skip-extended-insert",
                SOURCE_DB, *TABLES,
            ], stdout=output)
        contents = snapshot.read_text(encoding="utf-8")
        if re.search(r"(?im)^\s*(DROP|DELETE|TRUNCATE)\b", contents):
            raise RuntimeError("Snapshot contains a destructive statement")
        uses = re.findall(r"(?im)^\s*USE\s+([^;]+);", contents)
        if uses != [TARGET_DB]:
            raise RuntimeError(f"Unexpected snapshot destination: {uses}")
        with snapshot.open("rb") as input_file:
            docker_client("mysql", ["--default-character-set=utf8mb4"], stdin=input_file)
        restored = create_engine(source.url.set(database=TARGET_DB))
        after = fingerprint(restored)
        if before != after:
            raise RuntimeError("Snapshot restore changed table contents")
        if fingerprint(source) != before:
            raise RuntimeError("Snapshot restoration changed the source database")
        with restored.connect() as conn:
            metrics = {
                "customers": conn.execute(text("SELECT COUNT(*) FROM dim_customer")).scalar_one(),
                "orders": conn.execute(text("SELECT COUNT(*) FROM fact_orders")).scalar_one(),
                "order_revenue": str(conn.execute(text("SELECT SUM(amount) FROM fact_orders")).scalar_one()),
                "ltv_rows": conn.execute(text("SELECT COUNT(*) FROM fact_ltv_cohort")).scalar_one(),
                "ltv_zero_revenue_rows": conn.execute(text(
                    "SELECT COUNT(*) FROM fact_ltv_cohort WHERE revenue = 0"
                )).scalar_one(),
                "server_version": conn.execute(text("SELECT VERSION()")).scalar_one(),
            }
        manifest = {
            "source_commit": os.getenv("GITHUB_SHA"),
            "source_database": SOURCE_DB,
            "target_database": TARGET_DB,
            "restore_test": "passed",
            "source_preserved": True,
            "snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
            "tables": after,
            "metrics": metrics,
        }
        (OUTPUT / "snapshot-validation.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"restore_test": "passed", "tables": len(after), **metrics}))
    finally:
        source.dispose()
        if restored is not None:
            restored.dispose()


if __name__ == "__main__":
    main()
