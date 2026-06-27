"""GenBI-Lab API: natural-language analytics over the governed warehouse."""
import os
import re

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.db import run_query, UnsafeQuery
from app.semantic_layer import load_model
from app.text_to_sql import generate_sql

app = FastAPI(title="GenBI-Lab")
MODEL = load_model()
HERE = os.path.dirname(__file__)
FRONTEND = os.path.join(HERE, "..", "frontend")

_SQL_FUNCS = {"sum", "avg", "count", "distinct", "round", "min", "max"}
_DATE_KEYWORDS = {"date", "quarter", "month", "year", "full_date"}


def sql_identifiers(sql: str) -> set:
    return set(re.findall(r"[a-z_]+", sql.lower()))


def metric_columns(expr: str) -> set:
    """Column tokens in a metric expression, minus SQL function keywords."""
    return {t for t in re.findall(r"[a-z_]+", expr.lower()) if t not in _SQL_FUNCS}


def detect_chart_hint(columns: list, rows: list) -> str:
    """Infer the best visualization type from column names and data."""
    col_lower = [c.lower() for c in columns]

    # timeseries: any column name contains a date/time keyword
    if any(any(kw in c for kw in _DATE_KEYWORDS) for c in col_lower):
        return "timeseries"

    # bar: exactly one categorical (string) column + one or more numeric columns
    if rows:
        numeric_cols, categorical_cols = [], []
        for i in range(len(columns)):
            vals = [r[i] for r in rows if r[i] is not None]
            if vals and all(isinstance(v, (int, float)) for v in vals):
                numeric_cols.append(i)
            else:
                categorical_cols.append(i)
        if len(categorical_cols) == 1 and numeric_cols:
            return "bar"

    return "table"


def _compute_kpis() -> dict:
    """Pre-compute all certified metric values for the KPI dashboard."""
    kpis = {}
    for name, meta in MODEL["metrics"].items():
        try:
            sql = f"SELECT {meta['expression']} FROM fact_purchase_orders"
            _, rows = run_query(sql)
            kpis[name] = rows[0][0] if rows and rows[0] else None
        except Exception:  # noqa: BLE001
            kpis[name] = None
    return kpis


class Ask(BaseModel):
    question: str


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))


@app.get("/semantic")
def semantic():
    """Expose the certified semantic layer (schema + metrics) and live KPI values."""
    return {
        "domain": MODEL["domain"],
        "tables": {t: list(v.get("columns", {})) for t, v in MODEL["tables"].items()},
        "metrics": {m: v["expression"] for m, v in MODEL["metrics"].items()},
        "kpis": _compute_kpis(),
    }


@app.post("/ask")
def ask(body: Ask):
    if not (os.environ.get("NVIDIA_API_KEY") or "").strip():
        return {"error": "Set NVIDIA_API_KEY to enable natural-language queries."}
    try:
        sql = generate_sql(body.question, MODEL)
    except Exception as e:  # noqa: BLE001
        return {"error": f"Could not generate SQL: {e}"}

    try:
        cols, rows = run_query(sql)
    except UnsafeQuery as e:
        return {"sql": sql, "error": f"Query rejected by safety guard: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"sql": sql, "error": f"Execution error: {e}"}

    # Certified metrics used: every measured column must appear in the SQL.
    used = [m for m, v in MODEL["metrics"].items()
            if metric_columns(v["expression"]) <= sql_identifiers(sql)]

    chart_hint = detect_chart_hint(cols, rows)

    return {
        "sql": sql,
        "columns": cols,
        "rows": [list(r) for r in rows],
        "metrics_used": sorted(set(used)),
        "chart_hint": chart_hint,
    }
