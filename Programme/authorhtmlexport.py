"""HTML generators packaged with the author edition."""

import json
from html import escape

from PySide6.QtCore import QIODevice, QSaveFile
from PySide6.QtGui import QColor, QFontInfo, QPalette
from PySide6.QtWidgets import QDialog, QFileDialog, QStyle, QStyleOptionViewItem

from forwardhtmlexport import network_snapshot, render_forward_html, web_input_grid
from reportdescription import report_description_parts


def choose_html_path(parent, title, directory, file_filter, filename):
    dialog = QFileDialog(parent, title, str(directory), file_filter)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    dialog.setDefaultSuffix("htm")
    dialog.selectFile(filename)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.selectedFiles()[0]


def write_html_file(file_path, document):
    target = QSaveFile(str(file_path))
    data = document.encode("utf-8")
    if not target.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError(target.errorString())
    if target.write(data) != len(data):
        error = target.errorString()
        target.cancelWriting()
        raise OSError(error)
    if not target.commit():
        raise OSError(target.errorString())


def training_table_html(table, language, title):
    palette = table.palette()
    roles = QPalette.ColorRole
    style = table.style()
    native_windows = style.objectName().lower() == "windows11"
    # The Windows 11 item view draws its rows over the window color.
    base = html_color(palette.color(roles.Window if native_windows else roles.Base))
    alternate = html_color(palette.color(roles.AlternateBase))
    foreground = html_color(palette.color(roles.Text))
    style_option = QStyleOptionViewItem()
    style_option.initFrom(table)
    grid_rgba = style.styleHint(
        QStyle.StyleHint.SH_Table_GridLineColor, style_option, table
    )
    grid = html_color(QColor.fromRgba(grid_rgba & 0xffffffff))
    header_view = table.horizontalHeader()
    header_palette = header_view.palette()
    button = html_color(header_palette.color(roles.Base if native_windows else roles.Button))
    button_text = html_color(header_palette.color(roles.ButtonText))
    font = QFontInfo(table.font())
    family = json.dumps(font.family(), ensure_ascii=False).replace("<", r"\3c ")
    line_height = table.fontMetrics().height()
    header_height = header_view.height()
    row_height = table.verticalHeader().defaultSectionSize()
    title = escape(title)
    language = escape(language)

    widths = [table.columnWidth(column) for column in range(table.columnCount())]
    headers = []
    for column, width in enumerate(widths):
        header = table.horizontalHeaderItem(column)
        colors = (
            f"color: {html_color(header.foreground().color())}; "
            f"background: {html_color(header.background().color())}; "
            if column else ""
        )
        label = "".join(
            f"<span>{escape(line)}</span>" for line in header.text().split("\n")
        )
        headers.append(
            f'<th scope="col" style="{colors}width: {width}px">{label}</th>'
        )

    rows = []
    for row in range(table.rowCount()):
        cells = []
        for column in range(table.columnCount()):
            item = table.item(row, column)
            label = escape(item.text()) if item is not None else ""
            if column == 0:
                cells.append(f'<th scope="row">{label}</th>')
            else:
                cells.append(f"<td>{label}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")

    return f'''<!doctype html>
<html lang="{language}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{
    margin: 0;
    background: {base};
    color: {foreground};
    font: {font.pixelSize()}px/{line_height}px {family}, monospace;
}}
.table-scroll {{ max-height: 100vh; overflow: auto; }}
table {{ width: {sum(widths)}px; table-layout: fixed; border-collapse: collapse; }}
th, td {{ border: 1px solid {grid}; box-sizing: border-box; padding: 0 3px; }}
thead th {{
    height: {header_height}px;
    background: {button};
    color: {button_text};
}}
thead th span {{
    display: block;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    text-wrap: balance;
}}
thead th:first-child, tbody th {{ font-weight: normal; }}
tbody th, tbody td {{ height: {row_height}px; }}
tbody th {{ text-align: center; }}
tbody td {{ text-align: right; white-space: pre; }}
tbody tr:nth-child(even) {{ background: {alternate}; }}
</style>
</head>
<body>
<div class="table-scroll">
<table aria-label="{title}">
<thead><tr>{"".join(headers)}</tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</div>
</body>
</html>
'''


def html_color(color):
    # Qt and CSS place the alpha channel at opposite ends of a hex color.
    return f"{color.name()}{color.alpha():02x}"


def project_description_html(description, title):
    """Show a recognized input/output pair below the full-width project description."""
    overview, inputs, outputs = report_description_parts(description)
    opening = f'<div class="report-description"><section class="description-card"><h2>{escape(title)}</h2>'
    content = opening + overview + "</section>"
    if inputs and outputs:
        content += (
            '<div class="report-pair description-io">'
            f'<section class="description-card">{inputs}</section>'
            f'<section class="description-card">{outputs}</section></div>'
        )
    return content + "</div>"


PROJECT_REPORT_CSS = """
:root {
    color-scheme: light;
    --ink: #172c44;
    --muted: #415a71;
    --line: #d7e2ec;
    --soft: #eff5fa;
}
* { box-sizing: border-box; }
body { margin: 0; color: var(--ink); background: #fff; font: 16px/1.55 "Segoe UI", system-ui, sans-serif; }
.viewport { max-height: 100vh; overflow: auto; }
.project-report { max-width: 1200px; margin: 0 auto; padding: clamp(20px, 4vw, 48px); overflow-wrap: anywhere; }
.project-report > header { text-align: center; }
h1, h2, h3, p { margin: 0; }
h1 { margin-top: 8px; font-size: clamp(1.95rem, 4.5vw, 3.05rem); line-height: 1.1; letter-spacing: -.035em; }
h2 { font-size: 1.3rem; line-height: 1.3; }
h3 { font-size: 1rem; }
h2, h3 { margin-bottom: 9px; text-align: left !important; }
p + p { margin-top: 10px; }
.eyebrow { color: #21517c; font-size: .78rem; font-weight: 700; letter-spacing: .11em; text-transform: uppercase; }
.report-meta, .report-figure, .description-card, .report-result { min-width: 0; border: 1px solid var(--line); border-radius: 12px; background: #f6f9fc; }
.report-meta { margin: 20px 0 15px; padding: 6px 14px; }
.report-meta table { margin: 0; border: 0; border-radius: 0; background: transparent; }
.report-overview { margin-top: 20px; }
.report-overview > div > table:last-child { margin-bottom: 0; }
.report-description { display: grid; gap: 14px; margin: 0 0 16px; }
.description-card, .report-result { padding: 14px 16px; }
.report-result p + h3 { margin-top: 13px; }
.report-result .note { margin-top: 10px; }
.classification-score { font-variant-numeric: tabular-nums; }
.report-description :is(div, p, span, li, ul, ol, td, th) {
    font: inherit;
    font-family: inherit !important;
    font-size: inherit !important;
    color: inherit !important;
}
.report-description p { white-space: pre-wrap; }
.report-description img { max-width: 100%; height: auto; }
.report-description h1, .report-description h2, .report-description h3 {
    font-family: inherit !important;
    font-size: 1rem !important;
    color: var(--ink) !important;
}
.section { margin-top: 26px; padding-top: 22px; border-top: 1px solid var(--line); }
.report-pair { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 24px; }
.report-figure { display: flex; flex-direction: column; margin: 0; padding: 12px 14px; }
.network-figure { justify-content: center; }
.report-figure img { display: block; width: 100%; height: auto; object-fit: contain; margin: auto 0; }
.network-figure img { margin: 0; }
.report-figure:not(.network-figure) img { max-height: 540px; }
figcaption, .note { color: var(--muted); font-size: .88rem; }
figcaption { margin-top: 9px; }
table {
    width: 100%; border-collapse: separate; border-spacing: 0;
    border: 1px solid var(--line); border-radius: 9px; overflow: hidden;
    margin: 8px 0 14px; background: #fff; font-size: .95rem; font-variant-numeric: tabular-nums;
}
th, td { padding: 8px 10px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--line); }
thead { background: var(--soft); }
tbody tr:last-child :is(th, td) { border-bottom: 0; }
thead th { line-height: 1.35; hyphens: auto; }
.report-facts td:first-child { width: 42%; color: var(--muted); }
.history-table :is(th, td):nth-child(n+4),
.deviation-table :is(th, td):not(:nth-child(2)) { text-align: right; }
td.report-number, .history-table td:nth-child(n+4),
.deviation-table td:not(:nth-child(2)), .training-data-table td:nth-child(3) { white-space: nowrap; }
.table-scroll { max-width: 100%; overflow-x: auto; }
.table-scroll table { min-width: 650px; }
.table-scroll .history-table { min-width: 780px; }
.section p, .section li { white-space: pre-wrap; }

@media (max-width: 650px) {
    .report-pair { grid-template-columns: 1fr; }
}
@media print {
    @page { size: A4; margin: 14mm; }
    .viewport, .table-scroll { max-height: none; overflow: visible; }
    .project-report { padding: 0; print-color-adjust: exact; -webkit-print-color-adjust: exact; }
    .project-report .section { break-before:page; }
    .project-report h1, .project-report h2, .project-report h3 { break-after: avoid; }
    .project-report .report-figure { break-inside: avoid; }
    .table-scroll table, .table-scroll .history-table { min-width: 0; }
}
"""


def project_report_html(language, title, markup):
    return f"""<!DOCTYPE html>
<html lang="{escape(language)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{escape(title)}</title>
<style>
{PROJECT_REPORT_CSS}
</style>
</head>
<body>
<div class="viewport">
<main class="project-report">
{markup}
</main>
</div>
</body>
</html>
"""
