"""Shared, lazy database connection configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL


def get_engine():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    url = URL.create(
        "mysql+pymysql",
        username=os.getenv("MYSQL_USER", "demo_user"),
        password=os.getenv("MYSQL_PASSWORD", "demo_pass"),
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=os.getenv("MYSQL_DB", "analytics_portfolio"),
    )
    return create_engine(url, pool_pre_ping=True)
