"""Initialize the configured demo database and rebuild derived tables."""

import re
from common.db import get_engine
from sqlalchemy import create_engine
from pathlib import Path


def main():
    engine = get_engine()
    name = engine.url.database
    if not re.fullmatch(r"[A-Za-z0-9_]+", name or ""):
        raise ValueError("MYSQL_DB must be a simple database identifier")
    server = create_engine(engine.url.set(database=None))
    with server.begin() as conn:
        conn.exec_driver_sql(
            f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4"
        )
    ddl = (Path(__file__).resolve().parents[1] / "sql/ddl.sql").read_text()
    with engine.begin() as conn:
        for statement in ddl.split(";"):
            if statement.strip() and not statement.strip().upper().startswith("USE "):
                conn.exec_driver_sql(statement)
    from scripts import ingest, attribution, ltv

    ingest.main()
    attribution.main()
    ltv.main()


if __name__ == "__main__":
    main()
