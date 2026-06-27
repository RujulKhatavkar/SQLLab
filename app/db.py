"""Read-only query execution against the gold warehouse, with a safety guard."""
import os
import re
import sqlite3

_DB = os.path.join(os.path.dirname(__file__), "..", "data", "warehouse.db")
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|pragma|replace|truncate)\b",
    re.IGNORECASE,
)


class UnsafeQuery(Exception):
    pass


def guard(sql: str) -> str:
    """Allow a single read-only SELECT only. Adds a LIMIT if none is present."""
    cleaned = sql.strip().rstrip(";").strip()
    if ";" in cleaned:
        raise UnsafeQuery("Only a single statement is allowed.")
    if not cleaned.lower().startswith(("select", "with")):
        raise UnsafeQuery("Only SELECT/WITH queries are allowed.")
    if _FORBIDDEN.search(cleaned):
        raise UnsafeQuery("Write/DDL keywords are not allowed.")
    if "limit" not in cleaned.lower():
        cleaned += " LIMIT 500"
    return cleaned


def run_query(sql: str, db: str = _DB):
    """Returns (columns, rows). Raises UnsafeQuery or sqlite3.Error on failure."""
    safe = guard(sql)
    conn = sqlite3.connect(db)
    try:
        cur = conn.execute(safe)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        return cols, rows
    finally:
        conn.close()
