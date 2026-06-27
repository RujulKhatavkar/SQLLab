"""
Runs the grounding benchmark and reports execution accuracy.

For each question we execute the model's generated SQL and the gold SQL, then
compare result sets (order-insensitive, value-normalized). Pass = sets match.

Usage:
    python -m benchmark.run_benchmark            # uses the real NVIDIA NIM API
    python -m benchmark.run_benchmark --mock     # offline smoke test (gold SQL)
"""
import os
import sys
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db import run_query, UnsafeQuery  # noqa: E402
from app.semantic_layer import load_model  # noqa: E402
from app.text_to_sql import generate_sql  # noqa: E402

QS = os.path.join(os.path.dirname(__file__), "questions.yaml")


def normalize(rows):
    """Round floats and sort so result sets compare order-insensitively."""
    out = [tuple(round(v, 2) if isinstance(v, float) else v for v in r) for r in rows]
    return sorted(out, key=lambda t: tuple(str(x) for x in t))


def result_for(sql):
    try:
        _, rows = run_query(sql)
        return normalize(rows), None
    except (UnsafeQuery, Exception) as e:  # noqa: BLE001
        return None, str(e)


class MockClient:
    """Returns the gold SQL so the harness can be validated without an API key.
    Mimics the OpenAI-compatible client shape:
        client.chat.completions.create(...).choices[0].message.content
    """
    def __init__(self, gold_map):
        self.gold_map = gold_map
        self.chat = self
        self.completions = self

    def create(self, *, model, messages, **kwargs):
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        sql = self.gold_map[user_msg]
        msg = type("Msg", (), {"content": sql})()
        choice = type("Choice", (), {"message": msg})()
        return type("Resp", (), {"choices": [choice]})()


def main(mock=False):
    model = load_model()
    items = yaml.safe_load(open(QS))
    client = MockClient({i["question"]: i["gold_sql"] for i in items}) if mock else None

    passed = 0
    print(f"{'id':<4} {'result':<6} question")
    print("-" * 60)
    for it in items:
        gold_rows, gold_err = result_for(it["gold_sql"])
        try:
            pred_sql = generate_sql(it["question"], model, client=client)
            pred_rows, pred_err = result_for(pred_sql)
        except Exception as e:  # noqa: BLE001
            pred_rows, pred_err = None, str(e)

        ok = pred_err is None and pred_rows == gold_rows
        passed += ok
        print(f"{it['id']:<4} {'PASS' if ok else 'FAIL':<6} {it['question']}")
        if not ok:
            print(f"      err={pred_err}  gold_err={gold_err}")

    n = len(items)
    print("-" * 60)
    print(f"Execution accuracy: {passed}/{n} = {100 * passed / n:.1f}%")


if __name__ == "__main__":
    main(mock="--mock" in sys.argv)
