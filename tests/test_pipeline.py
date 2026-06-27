"""
Offline tests (no API key needed). Run with:  python -m pytest -q
Proves the eval harness PASSES correct SQL and FAILS wrong SQL.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db import run_query, guard, UnsafeQuery  # noqa: E402
from app.semantic_layer import load_model, as_grounding_text  # noqa: E402
from benchmark.run_benchmark import normalize, result_for  # noqa: E402


def test_guard_blocks_writes():
    for bad in ["DROP TABLE dim_date", "DELETE FROM fact_purchase_orders",
                "SELECT 1; DROP TABLE x"]:
        try:
            guard(bad)
            assert False, f"should have blocked: {bad}"
        except UnsafeQuery:
            pass


def test_guard_adds_limit():
    assert "LIMIT" in guard("SELECT 1").upper()


def test_grounding_includes_metrics():
    text = as_grounding_text(load_model())
    assert "total_spend" in text and "SUM(total_cost)" in text


def test_correct_sql_matches_gold():
    gold = ("SELECT SUM(f.total_cost) FROM fact_purchase_orders f "
            "JOIN dim_date d ON f.date_key=d.date_key WHERE d.year=2024")
    same = ("SELECT SUM(total_cost) FROM fact_purchase_orders f "
            "JOIN dim_date d ON f.date_key=d.date_key WHERE d.year=2024")
    g, _ = result_for(gold)
    p, _ = result_for(same)
    assert g == p and g is not None


def test_wrong_sql_fails_gold():
    gold = ("SELECT SUM(f.total_cost) FROM fact_purchase_orders f "
            "JOIN dim_date d ON f.date_key=d.date_key WHERE d.year=2024")
    wrong = ("SELECT SUM(f.total_cost) FROM fact_purchase_orders f "
             "JOIN dim_date d ON f.date_key=d.date_key WHERE d.year=2025")
    g, _ = result_for(gold)
    p, _ = result_for(wrong)
    assert g != p   # different years -> harness must catch it


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
