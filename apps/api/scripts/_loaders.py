import json
from pathlib import Path


def load_rows(path: str) -> list:
    """Read a .json (list, or {"records": [...]}) or .jsonl file."""
    text = Path(path).read_text(encoding="utf-8")
    if path.endswith(".jsonl"):
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("records") or data.get("listings") or data.get("items")
    if not isinstance(data, list):
        raise SystemExit("The file must contain a JSON list (or an object with a 'records' list).")
    return data
