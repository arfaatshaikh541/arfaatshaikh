"""Write the JSON Schemas of the data contracts to data/contracts/ (so data suppliers can validate files before uploading).
    uv run python scripts/export_schemas.py [--check]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.data_contracts import DirectoryListingInput, KnowledgeRecordInput  # noqa: E402
from app.services.manifest import manifest_path  # noqa: E402

TARGET = manifest_path().parent / "contracts"


def schemas() -> dict[str, dict]:
    return {"knowledge-record.schema.json": KnowledgeRecordInput.model_json_schema(), "directory-listing.schema.json": DirectoryListingInput.model_json_schema()}


if __name__ == "__main__":
    TARGET.mkdir(exist_ok=True)
    stale = False
    for name, schema in schemas().items():
        text = json.dumps(schema, indent=1, ensure_ascii=False) + "\n"
        path = TARGET / name
        if "--check" in sys.argv:
            stale |= not path.exists() or path.read_text(encoding="utf-8") != text
        else:
            path.write_text(text, encoding="utf-8")
    raise SystemExit(1 if stale else 0)
