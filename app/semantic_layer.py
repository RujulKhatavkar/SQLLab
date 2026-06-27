"""Loads the semantic layer and serializes it into grounding context for the LLM."""
import os
import yaml

_PATH = os.path.join(os.path.dirname(__file__), "..", "semantic", "model.yaml")


def load_model(path: str = _PATH) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def as_grounding_text(model: dict) -> str:
    """Render the semantic layer as a compact schema + metric brief for the prompt."""
    lines = [f"DOMAIN: {model['domain']}", f"GRAIN: {model['grain']}", "", "TABLES:"]
    for tname, t in model["tables"].items():
        cert = " [CERTIFIED]" if t.get("certified") else ""
        lines.append(f"  {tname} ({t['type']}){cert}: {t.get('description', '')}")
        for col, desc in t.get("columns", {}).items():
            lines.append(f"      - {col}: {desc}")
    lines.append("")
    lines.append("CERTIFIED METRICS (use these expressions exactly):")
    for mname, m in model["metrics"].items():
        lines.append(f"  {mname} = {m['expression']}  -- {m['description']}")
    g = model.get("governance", {})
    if g.get("pii_columns"):
        lines.append("")
        lines.append(f"PII COLUMNS (never expose raw): {', '.join(g['pii_columns'])}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(as_grounding_text(load_model()))
