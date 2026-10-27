"""Read the committed PBIX and compare its imported rows with the rebuilt MySQL data.

This is a read-only artifact check. It does not execute DAX or render Power BI.
"""

from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from numbers import Number
from pathlib import Path
import re
import zipfile

import pandas as pd
from pbixray import PBIXRay
from sqlalchemy import inspect, text

from common.db import get_engine


ROOT = Path(__file__).resolve().parents[1]
PBIX = ROOT / "powerbi" / "Dashboard_P1.pbix"
TABLES = (
    "dim_channel", "dim_customer", "fact_attribution", "fact_events",
    "fact_ltv_cohort", "fact_marketing_spend", "fact_orders", "fact_touches",
)


def equivalent(actual, expected):
    if pd.isna(expected):
        return bool(pd.isna(actual))
    if pd.isna(actual):
        return False
    if isinstance(expected, (datetime, date, pd.Timestamp)):
        # VertiPaq date decoding can be up to 1 ms below an exact source second.
        return abs(pd.Timestamp(actual) - pd.Timestamp(expected)) <= pd.Timedelta(milliseconds=2)
    if isinstance(expected, (Number, Decimal)):
        return abs(Decimal(str(actual)) - Decimal(str(expected))) <= Decimal("0.00000001")
    return actual == expected


def compare_rows(actual, expected, key_columns):
    columns = list(expected.columns)
    if not set(columns).issubset(actual.columns):
        raise AssertionError("PBIX is missing source columns")
    actual = actual.set_index(key_columns, verify_integrity=True).sort_index()
    expected = expected.set_index(key_columns, verify_integrity=True).sort_index()
    if list(actual.index) != list(expected.index):
        raise AssertionError("PBIX source primary keys differ")
    for column in expected.columns:
        for key, expected_value in expected[column].items():
            if not equivalent(actual.at[key, column], expected_value):
                raise AssertionError(f"PBIX differs at primary key {key!r}, column {column}")


def compact(expression):
    return re.sub(r"\s+", "", expression)


def verify_definitions(model):
    queries = model.power_query
    assert len(queries) == 8, "Expected eight source queries"
    for query in queries.itertuples():
        expression = compact(query.Expression)
        table = query.TableName.removeprefix("analytics_portfolio ")
        assert table in TABLES
        assert 'MySQL.Database("localhost","analytics_portfolio_corrected",' in expression
        assert 'Schema="analytics_portfolio_corrected"' in expression
        assert f'Item="{table}"' in expression
        assert "CreateNavigationProperties=false" in expression

    measures = dict(zip(model.dax_measures.Name, model.dax_measures.Expression))
    assert compact(measures["Total Revenue (Selected)"]) == "[AttributedRevenue(Selected)]", \
        "Revenue card must use the attributed share for split-credit models"
    assert "LTV/CAC (sel)" not in measures, "Remove the mismatched cohort/period ratio"
    assert "AVERAGE(" in compact(measures["Avg LTV by Horizon"])
    assert "[SelectedHorizon]" in compact(measures["Avg LTV (sel)"])
    assert "TREATAS(" in compact(measures["Avg LTV (sel)"])
    assert "HASONEVALUE(" in compact(measures["Selected Horizon"])
    assert "ISFILTERED(" in compact(measures["Selected Horizon"])

    pages = {}
    visuals = {}
    with zipfile.ZipFile(PBIX) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            if name.endswith("/page.json"):
                value = json.loads(archive.read(name))
                pages[value["name"]] = value
            elif name.endswith("/visual.json"):
                visuals.setdefault(name.split("/")[3], []).append(json.loads(archive.read(name)))
    assert len(pages) == 3
    monthly_axis = False
    buyer_title = False
    horizon_slicers = 0
    for page_id, page_visuals in visuals.items():
        for definition in page_visuals:
            visual = definition["visual"]
            serialized = json.dumps(visual)
            if visual["visualType"] == "slicer":
                if '"horizon_days"' in serialized:
                    horizon_slicers += 1
                    assert pages[page_id]["displayName"] == "Página 1"
                if '"Property": "model"' in serialized:
                    selection = visual["objects"]["selection"][0]["properties"]
                    assert selection["strictSingleSelect"]["expr"]["Literal"]["Value"] == "true"
            if visual["visualType"] == "lineChart" and '"YearMonth"' in serialized:
                sort = visual["query"]["sortDefinition"]["sort"][0]
                assert sort["field"]["Column"]["Property"] == "YearMonth"
                assert sort["direction"] == "Ascending"
                monthly_axis = True
            if "Cost per Buyer by Channel" in serialized:
                buyer_title = True
            assert "LTV/CAC (sel)" not in serialized
    assert monthly_axis and buyer_title and horizon_slicers == 1


def main():
    engine = get_engine()
    validation = {"pbix_sha256": hashlib.sha256(PBIX.read_bytes()).hexdigest(), "tables": {}}
    try:
        with PBIXRay(str(PBIX)) as model, engine.connect() as connection:
            verify_definitions(model)
            inspector = inspect(connection)
            for table in TABLES:
                expected = pd.read_sql(text(f"SELECT * FROM `{table}`"), connection)
                actual = model.get_table(f"analytics_portfolio {table}")
                keys = inspector.get_pk_constraint(table)["constrained_columns"]
                assert keys and len(expected), f"Missing source keys/data: {table}"
                compare_rows(actual, expected, keys)
                validation["tables"][table] = {"rows": len(expected), "source_values_match": True}
                print(f"PASS PBIX {table}: {len(expected)} rows, all source values match")
        validation["report_definition_checks"] = "passed"
        validation["date_readback_tolerance_ms"] = 2
        validation["dax_execution"] = "not performed; Desktop validation is separate"
        output = ROOT / "artifacts" / "powerbi-validation.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
        print("PASS PBIX connections, corrected revenue alias, LTV measures and monthly axis")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
