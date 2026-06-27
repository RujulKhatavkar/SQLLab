"""
Natural-language -> SQL, grounded on the certified semantic layer.

Uses the NVIDIA NIM API (OpenAI-compatible endpoint) for text-to-SQL generation.
Tightening GROUNDING_INSTRUCTIONS and re-running the benchmark is the
accuracy-improvement cycle.
"""
import os
import re

from app.semantic_layer import as_grounding_text

MODEL = os.environ.get("GENBI_MODEL", "meta/llama-3.3-70b-instruct")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Grounding instructions. Edit these, then re-run the benchmark to see accuracy move.
GROUNDING_INSTRUCTIONS = """\
- Target dialect is SQLite. Use only the tables and columns listed.
- When a question maps to a certified metric, use that metric's exact expression.
- Always join the fact table to dimensions by their *_key columns.
- Filter time using dim_date (year, quarter, month), not raw date strings.
- Spend means SUM(total_cost). Rates are percentages already scaled by the metric.
- Return ONE SELECT statement. No comments, no markdown, no explanation.
"""

SYSTEM_TEMPLATE = """You are a GenBI text-to-SQL engine for a governed analytics warehouse.
Convert the user's question into a single, correct SQLite SELECT query.

{grounding}

INSTRUCTIONS:
{instructions}

Respond with ONLY the SQL query, nothing else."""


def _strip_sql(text: str) -> str:
    text = re.sub(r"```sql|```", "", text, flags=re.IGNORECASE).strip()
    return text.rstrip(";").strip()


def build_system_prompt(model: dict, instructions: str = GROUNDING_INSTRUCTIONS) -> str:
    return SYSTEM_TEMPLATE.format(
        grounding=as_grounding_text(model), instructions=instructions
    )


def generate_sql(question: str, model: dict, client=None,
                 instructions: str = GROUNDING_INSTRUCTIONS) -> str:
    """
    Returns a SQL string. `client` is any OpenAI-compatible client; if None one is
    built pointing at NVIDIA NIM (reads NVIDIA_API_KEY from env). Inject a fake
    client in tests to run offline.
    """
    system = build_system_prompt(model, instructions)

    if client is None:
        from openai import OpenAI  # lazy — offline tests don't need the package installed
        client = OpenAI(
            base_url=NVIDIA_BASE_URL,
            api_key=(os.environ.get("NVIDIA_API_KEY") or "").strip(),
        )

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
        temperature=0.2,
        top_p=0.7,
        max_tokens=1024,
        stream=False,
    )
    return _strip_sql(resp.choices[0].message.content or "")
