"""CSV parsing shared by the API's upload/preview step and the worker's
actual per-row import task, so the two can never disagree about how a
raw CSV row becomes a `record` dict for `businesses.repositories.
upsert_business_from_discovery`.

`MAPPABLE_FIELDS` deliberately excludes `email` - `Business.email` is
enrichment-owned only (see `app.modules.businesses` module docstring,
ADR-0011); a CSV import is a discovery-shaped source and must follow the
exact same rule a connector already does, not carve out an exception
just because the data arrived as a file instead of an API response.
"""

import csv
import io

from app.modules.csv_import.models import MAPPABLE_FIELDS

MAX_PREVIEW_ROWS = 5
_NUMERIC_FIELDS = frozenset({"rating", "review_count"})


class CsvParseError(Exception):
    """The file itself is not readable as CSV (bad encoding, no header
    row) - distinct from a single bad row, which is a per-row error."""


def read_headers_and_rows(file_bytes: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Returns (headers, all_data_rows_as_dicts). Raises CsvParseError if
    the file has no header row or isn't decodable as UTF-8 (with a BOM
    tolerated, matching what `exports.workbook.build_csv` itself writes -
    see ADR-0015 - so a GRIDKEEP-exported CSV can be re-imported)."""
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvParseError("File is not valid UTF-8 text.") from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise CsvParseError("File has no header row.")
    headers = [h for h in reader.fieldnames if h]
    rows = list(reader)
    return headers, rows


def apply_mapping(row: dict[str, str], column_mapping: dict[str, str]) -> dict[str, object]:
    """`column_mapping` is {business_field: csv_header}. Returns a
    `record`-shaped dict with only the fields the caller actually mapped
    - an unmapped field is simply absent, never guessed at, matching
    `upsert_business_from_discovery`'s own "only writes fields present in
    `record`" contract."""
    record: dict[str, object] = {}
    for field, header in column_mapping.items():
        if field not in MAPPABLE_FIELDS:
            continue
        raw_value = row.get(header)
        if raw_value is None:
            continue
        value = raw_value.strip()
        if not value:
            continue
        if field in _NUMERIC_FIELDS:
            try:
                record[field] = float(value) if field == "rating" else int(float(value))
            except ValueError:
                # A field that doesn't parse is left out, not fabricated
                # as 0 or guessed at - the row itself may still be valid
                # (see build_record_or_raise: only a missing/empty `name`
                # fails the whole row).
                continue
        else:
            record[field] = value
    return record


def build_record_or_raise(
    row: dict[str, str], column_mapping: dict[str, str], *, row_number: int
) -> dict[str, object]:
    record = apply_mapping(row, column_mapping)
    if not record.get("name"):
        raise CsvParseError(f"Row {row_number}: no business name (required field is empty).")
    return record
