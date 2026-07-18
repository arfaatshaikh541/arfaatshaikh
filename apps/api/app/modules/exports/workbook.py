"""XLSX and CSV generation for lead exports.

**Formula-injection protection** (the architecture's explicit "safe
formula handling" / "CSV formula-injection protection" requirements):
every business-derived string (names, addresses, notes, ...) is scraped
or human-entered data the app has never validated as formula-safe. Both
openpyxl and every spreadsheet application that opens a CSV treat a cell
value beginning with `=`, `+`, `-`, or `@` as a formula to evaluate, not
literal text - a business legitimately named "-1+1" or a note starting
with "=" would otherwise become an executable formula the moment the file
is opened. `sanitize_cell_value` neutralizes this by prefixing a leading
apostrophe (the standard Excel/OWASP-recommended defense: it forces text
interpretation and is never itself displayed), applied uniformly to every
string cell in both the XLSX and CSV writers below - there is exactly one
sanitization function so the two formats can never drift out of sync.

**Streaming, not in-memory, for XLSX** (`Workbook(write_only=True)`): the
architecture calls out "background export for large files" as its own
requirement. openpyxl's normal mode holds every cell in memory as Python
objects; write-only mode streams rows straight to the zip archive as they
are appended, so memory stays bounded by one row at a time regardless of
how many leads an export covers.
"""

import csv
import io
from collections.abc import Iterable
from datetime import UTC, datetime

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.modules.exports.data import COLUMNS, HYPERLINK_COLUMNS, ExportRow
from app.modules.leads.models import LEAD_STATUSES
from app.modules.leads.scoring import OPPORTUNITY_RECOMMENDATIONS

_DANGEROUS_LEADING_CHARS = ("=", "+", "-", "@", "\t", "\r")

HEADER_FILL = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
WRAP_COLUMNS = frozenset(
    {"Address", "Score Explanation", "Notes", "Detected Opportunities", "Recommended Service"}
)

# Approximate character widths - wide enough to be usable without a
# manual resize, capped so no single column dominates the sheet.
_COLUMN_WIDTHS = {
    "Business Name": 28,
    "Category": 16,
    "Subcategory": 16,
    "Country": 14,
    "Region": 14,
    "City": 14,
    "Area": 14,
    "Address": 32,
    "Public Phone": 16,
    "Public Email": 24,
    "Website": 28,
    "Google Maps URL": 28,
    "Rating": 8,
    "Review Count": 12,
    "Opening Hours": 20,
    "WhatsApp URL": 28,
    "Facebook URL": 28,
    "Instagram URL": 28,
    "LinkedIn Company URL": 28,
    "Detected Opportunities": 32,
    "Recommended Service": 26,
    "Lead Score": 10,
    "Score Explanation": 45,
    "Confidence": 10,
    "Source": 12,
    "Source URL": 28,
    "Date Collected": 18,
    "Verification Status": 16,
    "Assigned User": 20,
    "Lead Status": 14,
    "Notes": 40,
}


def sanitize_cell_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    if value.startswith(_DANGEROUS_LEADING_CHARS):
        return "'" + value
    return value


def _excel_safe(value: object) -> object:
    """openpyxl rejects tz-aware datetimes outright (Excel's own date
    type has no timezone concept) - every timestamp in this schema is
    stored tz-aware (`DateTime(timezone=True)`), so every datetime cell
    needs converting to naive UTC before it can be written."""
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _write_only_cell(ws: Worksheet, column: str, value: object) -> object:
    value = _excel_safe(sanitize_cell_value(value))
    if value is None:
        return None
    cell = WriteOnlyCell(ws, value=value)
    if column in WRAP_COLUMNS:
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    if column in HYPERLINK_COLUMNS and isinstance(value, str) and not value.startswith("'"):
        cell.hyperlink = value
        cell.style = "Hyperlink"
    return cell


def _write_leads_sheet(wb: Workbook, rows: Iterable[ExportRow]) -> None:
    ws = wb.create_sheet(title="Leads")
    # Write-only worksheets only serialize freeze_panes/pane state if it
    # is set before any row is appended - setting it afterwards (as would
    # be natural in normal, non-streaming openpyxl mode) is silently
    # dropped on save.
    ws.freeze_panes = "A2"
    header_row = []
    for column in COLUMNS:
        cell = WriteOnlyCell(ws, value=column)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        header_row.append(cell)
    ws.append(header_row)

    row_count = 0
    for row in rows:
        ws.append([_write_only_cell(ws, column, row.values.get(column)) for column in COLUMNS])
        row_count += 1

    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{row_count + 1}"
    for index, column in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(index)].width = _COLUMN_WIDTHS.get(column, 18)


def _write_campaign_summary_sheet(
    wb: Workbook, campaign_counts: dict, campaigns_by_id: dict
) -> None:
    ws = wb.create_sheet(title="Campaign Summary")
    ws.freeze_panes = "A2"
    header = ["Campaign Name", "Status", "Result Limit", "Leads In This Export"]
    header_cells = []
    for value in header:
        cell = WriteOnlyCell(ws, value=value)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        header_cells.append(cell)
    ws.append(header_cells)
    for campaign_id, count in campaign_counts.items():
        campaign = campaigns_by_id.get(campaign_id)
        ws.append(
            [
                campaign.name if campaign else "(unknown campaign)",
                campaign.status if campaign else None,
                campaign.result_limit if campaign else None,
                count,
            ]
        )
    for index, width in enumerate([32, 16, 14, 20], start=1):
        ws.column_dimensions[get_column_letter(index)].width = width


def _write_scoring_rules_sheet(wb: Workbook) -> None:
    """Static, but real: the exact rule table `leads.scoring` uses to map
    a detected opportunity to a recommended service, and the full lead
    status vocabulary - so a recipient can see *why* a lead scored/was
    recommended the way it did without reading the source code."""
    ws = wb.create_sheet(title="Scoring Rules")
    ws.freeze_panes = "A2"
    header_cells = []
    for value in ["Opportunity Type", "Maps To Recommended Service(s)"]:
        cell = WriteOnlyCell(ws, value=value)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        header_cells.append(cell)
    ws.append(header_cells)
    for opportunity_type, recommendation_types in OPPORTUNITY_RECOMMENDATIONS.items():
        ws.append(
            [
                opportunity_type.replace("_", " ").title(),
                ", ".join(r.replace("_", " ").title() for r in recommendation_types),
            ]
        )
    ws.append([])
    lead_status_header = WriteOnlyCell(ws, value="Lead Status Values")
    lead_status_header.font = HEADER_FONT
    lead_status_header.fill = HEADER_FILL
    ws.append([lead_status_header])
    for status in LEAD_STATUSES:
        ws.append([status.replace("_", " ").title()])
    ws.column_dimensions[get_column_letter(1)].width = 32
    ws.column_dimensions[get_column_letter(2)].width = 40


def _write_errors_sheet(wb: Workbook, errors: list[tuple[str | None, str]]) -> None:
    ws = wb.create_sheet(title="Errors")
    ws.freeze_panes = "A2"
    header_cells = []
    for value in ["Lead ID", "Error"]:
        cell = WriteOnlyCell(ws, value=value)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        header_cells.append(cell)
    ws.append(header_cells)
    for lead_id, message in errors:
        ws.append([lead_id or "", sanitize_cell_value(message)])
    ws.column_dimensions[get_column_letter(1)].width = 38
    ws.column_dimensions[get_column_letter(2)].width = 60


def build_xlsx(
    rows: list[ExportRow],
    errors: list[tuple[str | None, str]],
    *,
    campaigns_by_id: dict,
) -> bytes:
    campaign_counts: dict = {}
    for row in rows:
        if row.campaign_id is None:
            continue
        campaign_counts[row.campaign_id] = campaign_counts.get(row.campaign_id, 0) + 1

    wb = Workbook(write_only=True)
    _write_leads_sheet(wb, rows)
    _write_campaign_summary_sheet(wb, campaign_counts, campaigns_by_id)
    _write_scoring_rules_sheet(wb)
    _write_errors_sheet(wb, errors)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def build_csv(rows: list[ExportRow]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    for row in rows:
        writer.writerow(
            [_csv_format(sanitize_cell_value(row.values.get(column))) for column in COLUMNS]
        )
    return buffer.getvalue().encode("utf-8-sig")


def _csv_format(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
