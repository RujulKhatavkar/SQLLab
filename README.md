# GenBI-Lab

**Governed conversational analytics.** Ask a procurement/supply-chain warehouse a
question in plain English; GenBI-Lab translates it to SQL *grounded on a certified
semantic layer*, runs it read-only against a gold star-schema model, and returns the
answer **plus the SQL and the certified metrics it used** — so results are explainable
and trustworthy, not a black box.

This is a from-scratch, local re-creation of the pattern behind tools like Databricks
Genie and Microsoft Copilot for BI: the hard part isn't calling an LLM, it's building
the trusted data foundation and the grounding/evaluation loop that make its answers
correct.

```
            ┌──────────────┐     grounding (schema + certified metrics)
  question →│ semantic     │──────────────────────────────┐
            │ layer (YAML) │                               ▼
            └──────────────┘                      ┌──────────────────┐
                                                  │ text-to-SQL      │
  gold star schema  ◄── read-only guard ── SQL ◄──│ (Gemini API)  │
  (SQLite)                                        └──────────────────┘
        │                                                  ▲
        ▼                                                  │
   answer + SQL + metric badges            benchmark harness scores
                                           execution accuracy on a gold set
```

## What's inside

| Piece | File | What it demonstrates |
|---|---|---|
| Gold star schema | `data/seed.py` | Fact + 4 dimensions, deterministic sample data |
| Semantic layer | `semantic/model.yaml` | Certified data assets, governed KPI definitions, PII flags |
| Grounding | `app/semantic_layer.py` | Serializes the catalog into LLM context |
| Text-to-SQL | `app/text_to_sql.py` | NL→SQL with tunable grounding instructions |
| Safety | `app/db.py` | SELECT-only guard, single-statement, auto-LIMIT |
| Benchmark | `benchmark/` | Gold Q&A set + execution-accuracy scoring |
| Console | `app/main.py`, `frontend/` | Conversational BI UI that shows the SQL trail |

## Quickstart

```bash
pip install -r requirements.txt
python data/seed.py                       # build the warehouse
python -m pytest -q                       # offline tests (no API key)
python -m benchmark.run_benchmark --mock  # validate the eval harness offline

export GEMINI_API_KEY=AIza...
python -m benchmark.run_benchmark         # score real NL→SQL accuracy
uvicorn app.main:app --reload             # open http://localhost:8000
```

## The grounding loop

`GROUNDING_INSTRUCTIONS` in `app/text_to_sql.py` is the knob. Tighten the instructions
or add metric definitions to the semantic layer, re-run `benchmark.run_benchmark`, and
watch execution accuracy move. That edit-measure-repeat cycle — improving grounding and
accuracy against a benchmark — is the core of building a reliable GenBI system.

## Notes

- The warehouse domain is procurement/supply chain (spend, on-time delivery, lead time,
  defect rate) but the pattern is domain-agnostic — swap `seed.py` + `model.yaml`.
- All queries are read-only and validated before execution.
- Sample data is synthetic and generated with a fixed seed.
