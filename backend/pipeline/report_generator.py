"""
Report Generator for QueryCraft
Exports query results as CSV, Excel, or PDF — all in-memory, no disk writes.
"""
import csv
import io
from typing import Dict, List, Tuple

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

# PDF: try WeasyPrint first (requires GTK on Windows), fall back to reportlab
_PDF_BACKEND = None
try:
    import weasyprint
    _PDF_BACKEND = "weasyprint"
except Exception:
    pass

if _PDF_BACKEND is None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Preformatted
        )
        _PDF_BACKEND = "reportlab"
    except ImportError:
        pass


# ── MIME types ────────────────────────────────────────────────────────────────
MIME_CSV   = "text/csv"
MIME_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_PDF   = "application/pdf"


# ── CSV ───────────────────────────────────────────────────────────────────────
def export_csv(columns: List[str], rows: List[Dict]) -> bytes:
    """
    Export results as UTF-8 CSV bytes.

    Args:
        columns: Column names (header row)
        rows:    List of row dicts

    Returns:
        UTF-8 encoded CSV bytes
    """
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore",
                            lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


# ── Excel ─────────────────────────────────────────────────────────────────────
def export_excel(columns: List[str], rows: List[Dict]) -> bytes:
    """
    Export results as .xlsx bytes.

    Args:
        columns: Column names
        rows:    List of row dicts

    Returns:
        .xlsx file bytes
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "QueryCraft Results"

    # Header style
    header_font  = Font(bold=True, color="FFFFFF")
    header_fill  = PatternFill(fill_type="solid", fgColor="1F4E79")
    header_align = Alignment(horizontal="center", vertical="center")

    # Write header row
    for col_idx, col_name in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font  = header_font
        cell.fill  = header_fill
        cell.alignment = header_align

    # Write data rows
    for row_idx, row in enumerate(rows, start=2):
        for col_idx, col_name in enumerate(columns, start=1):
            value = row.get(col_name)
            ws.cell(row=row_idx, column=col_idx, value=value)

    # Auto-size columns (cap at 50 chars)
    for col_cells in ws.columns:
        max_len = max(
            (len(str(c.value)) if c.value is not None else 0) for c in col_cells
        )
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 54)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


# ── PDF ───────────────────────────────────────────────────────────────────────
def export_pdf(columns: List[str], rows: List[Dict],
               query_text: str = "", sql: str = "") -> bytes:
    """
    Export results as PDF bytes.

    Uses WeasyPrint if GTK is available, otherwise falls back to reportlab.

    Args:
        columns:    Column names
        rows:       List of row dicts
        query_text: Original user query (shown in report header)
        sql:        Generated SQL (shown in report)

    Returns:
        PDF file bytes
    """
    if _PDF_BACKEND == "weasyprint":
        return _pdf_weasyprint(columns, rows, query_text, sql)
    elif _PDF_BACKEND == "reportlab":
        return _pdf_reportlab(columns, rows, query_text, sql)
    else:
        raise RuntimeError("No PDF backend available. Install reportlab: pip install reportlab")


def _pdf_weasyprint(columns, rows, query_text, sql) -> bytes:
    """Generate PDF using WeasyPrint (HTML → PDF)."""
    # Build HTML table rows
    header_cells = "".join(f"<th>{c}</th>" for c in columns)
    data_rows = ""
    for row in rows:
        cells = "".join(f"<td>{row.get(c, '')}</td>" for c in columns)
        data_rows += f"<tr>{cells}</tr>\n"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 11px; margin: 20px; }}
  h1   {{ color: #1F4E79; font-size: 18px; }}
  h3   {{ color: #333; font-size: 13px; margin-top: 16px; }}
  pre  {{ background: #f4f4f4; padding: 8px; border-radius: 4px;
          font-size: 10px; white-space: pre-wrap; word-break: break-all; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
  th   {{ background: #1F4E79; color: white; padding: 6px 8px; text-align: left; }}
  td   {{ border: 1px solid #ddd; padding: 5px 8px; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
</style>
</head>
<body>
  <h1>QueryCraft Report</h1>
  <h3>Query</h3>
  <p>{query_text}</p>
  <h3>Generated SQL</h3>
  <pre>{sql}</pre>
  <h3>Results ({len(rows)} rows)</h3>
  <table>
    <thead><tr>{header_cells}</tr></thead>
    <tbody>{data_rows}</tbody>
  </table>
</body>
</html>"""

    return weasyprint.HTML(string=html).write_pdf()


def _pdf_reportlab(columns, rows, query_text, sql) -> bytes:
    """Generate PDF using reportlab (pure Python, no GTK needed)."""
    buf = io.BytesIO()

    # Use landscape if many columns
    pagesize = landscape(A4) if len(columns) > 6 else A4
    doc = SimpleDocTemplate(buf, pagesize=pagesize,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Heading1"],
                                 textColor=colors.HexColor("#1F4E79"), fontSize=16)
    h3_style    = ParagraphStyle("h3", parent=styles["Heading3"],
                                 textColor=colors.HexColor("#333333"), fontSize=11)
    body_style  = styles["BodyText"]
    code_style  = ParagraphStyle("code", parent=styles["Code"],
                                 fontSize=8, leading=10,
                                 backColor=colors.HexColor("#F4F4F4"))

    story = []

    # Title
    story.append(Paragraph("QueryCraft Report", title_style))
    story.append(Spacer(1, 0.3*cm))

    # Query text
    if query_text:
        story.append(Paragraph("Query", h3_style))
        story.append(Paragraph(query_text, body_style))
        story.append(Spacer(1, 0.2*cm))

    # SQL block
    if sql:
        story.append(Paragraph("Generated SQL", h3_style))
        story.append(Preformatted(sql, code_style))
        story.append(Spacer(1, 0.3*cm))

    # Results table
    story.append(Paragraph(f"Results ({len(rows)} rows)", h3_style))
    story.append(Spacer(1, 0.2*cm))

    if rows:
        # Build table data: header + rows (cap at 500 rows in PDF)
        display_rows = rows[:500]
        table_data = [columns]
        for row in display_rows:
            table_data.append([str(row.get(c, "")) for c in columns])

        # Column widths — distribute evenly
        page_w = pagesize[0] - 3*cm
        col_w  = page_w / len(columns)
        col_widths = [col_w] * len(columns)

        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            # Header
            ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, 0), 8),
            ("ALIGN",       (0, 0), (-1, 0), "CENTER"),
            # Data rows
            ("FONTSIZE",    (0, 1), (-1, -1), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F9F9F9")]),
            ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#DDDDDD")),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",  (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)

        if len(rows) > 500:
            story.append(Spacer(1, 0.2*cm))
            story.append(Paragraph(
                f"Note: PDF shows first 500 of {len(rows)} rows. "
                "Download CSV or Excel for full dataset.",
                body_style
            ))
    else:
        story.append(Paragraph("No results returned.", body_style))

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ── Entry point ───────────────────────────────────────────────────────────────
def generate_report(format: str, columns: List[str], rows: List[Dict],
                    query_text: str = "", sql: str = "") -> Tuple[bytes, str]:
    """
    Generate a report in the requested format.

    Args:
        format:     "csv", "excel", or "pdf"
        columns:    Column names
        rows:       List of row dicts
        query_text: Original user query
        sql:        Generated SQL

    Returns:
        (file_bytes, mime_type)

    Raises:
        ValueError: If format is unsupported
    """
    fmt = format.lower().strip()

    if fmt == "csv":
        return export_csv(columns, rows), MIME_CSV

    elif fmt in ("excel", "xlsx"):
        return export_excel(columns, rows), MIME_EXCEL

    elif fmt == "pdf":
        return export_pdf(columns, rows, query_text, sql), MIME_PDF

    else:
        raise ValueError(f"Unsupported format: '{format}'. Use 'csv', 'excel', or 'pdf'.")


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing Report Generator...")
    print(f"PDF backend: {_PDF_BACKEND}")
    print("=" * 80)

    # Sample data
    COLUMNS = ["cpu_num", "avg_busy_time", "system_name"]
    ROWS = [
        {"cpu_num": 0, "avg_busy_time": 1234567, "system_name": r"\KRONOS"},
        {"cpu_num": 1, "avg_busy_time": 987654,  "system_name": r"\KRONOS"},
        {"cpu_num": 2, "avg_busy_time": 1111111, "system_name": r"\KRONOS"},
    ]
    QUERY = "Show average CPU busy time per CPU"
    SQL   = "SELECT cpu_num, AVG(cpu_busy_time) AS avg_busy_time, system_name FROM macht413.cpu GROUP BY cpu_num, system_name LIMIT 10000"

    passed = 0
    total  = 3

    # ── CSV ──────────────────────────────────────────────────────────────────
    print("\n[Test 1] CSV Export")
    csv_bytes, mime = generate_report("csv", COLUMNS, ROWS)
    csv_text = csv_bytes.decode("utf-8")
    lines = csv_text.strip().split("\n")

    assert mime == MIME_CSV,                    f"Wrong MIME: {mime}"
    assert lines[0] == "cpu_num,avg_busy_time,system_name", f"Bad header: {lines[0]}"
    assert len(lines) == 4,                     f"Expected 4 lines, got {len(lines)}"
    assert "1234567" in csv_text,               "Missing data value"
    print(f"  MIME: {mime}")
    print(f"  Lines: {len(lines)} (header + {len(lines)-1} rows)")
    print(f"  Header: {lines[0]}")
    print("  ✓ PASSED")
    passed += 1

    # ── Excel ─────────────────────────────────────────────────────────────────
    print("\n[Test 2] Excel Export")
    xl_bytes, mime = generate_report("excel", COLUMNS, ROWS)

    assert mime == MIME_EXCEL,      f"Wrong MIME: {mime}"
    assert len(xl_bytes) > 0,       "Empty bytes"
    assert xl_bytes[:4] == b"PK\x03\x04", "Not a valid .xlsx (missing ZIP header)"

    # Verify content by re-reading with openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(xl_bytes))
    ws = wb.active
    assert ws.cell(1, 1).value == "cpu_num",    "Header cell wrong"
    assert ws.cell(2, 1).value == 0,            "Data cell wrong"
    assert ws.cell(1, 1).font.bold,             "Header not bold"

    print(f"  MIME: {mime}")
    print(f"  Size: {len(xl_bytes):,} bytes")
    print(f"  Rows in sheet: {ws.max_row} (header + {ws.max_row - 1} data)")
    print("  ✓ PASSED")
    passed += 1

    # ── PDF ───────────────────────────────────────────────────────────────────
    print("\n[Test 3] PDF Export")
    pdf_bytes, mime = generate_report("pdf", COLUMNS, ROWS, QUERY, SQL)

    assert mime == MIME_PDF,            f"Wrong MIME: {mime}"
    assert len(pdf_bytes) > 0,          "Empty bytes"
    assert pdf_bytes[:4] == b"%PDF",    f"Not a valid PDF (got {pdf_bytes[:4]})"

    print(f"  MIME: {mime}")
    print(f"  Backend: {_PDF_BACKEND}")
    print(f"  Size: {len(pdf_bytes):,} bytes")
    print("  ✓ PASSED")
    passed += 1

    # ── Bad format ────────────────────────────────────────────────────────────
    print("\n[Test 4] Unsupported Format")
    try:
        generate_report("docx", COLUMNS, ROWS)
        print("  ✗ Should have raised ValueError")
    except ValueError as e:
        print(f"  Correctly raised ValueError: {e}")
        print("  ✓ PASSED")

    print("\n" + "=" * 80)
    print(f"✓ {passed}/{total} export tests passed!")
    print("=" * 80)
