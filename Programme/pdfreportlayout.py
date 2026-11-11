"""Vector frames for tables and panels in the paginated project report."""

from dataclasses import dataclass
from math import floor

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen, QTextCursor, QTextFormat


_MARKER = "neuronn-pdf-frame-"
_FRAME_COLOR = "#d4e2ed"


@dataclass(frozen=True)
class PdfFrame:
    rect: QRectF
    shaded: bool
    separators: tuple[float, ...]


def pdf_frame_marker(kind, *, keep_together=False, keep_with_next=False):
    suffix = "-next" if keep_with_next else ("-keep" if keep_together else "")
    return f'<p style="margin:0;font-size:1px"><a name="{_MARKER}{kind}{suffix}">&nbsp;</a></p>'


def _marked_tables(document):
    block = document.begin()
    while block.isValid():
        iterator = block.begin()
        marker = None
        while not iterator.atEnd():
            marker = next((name for name in iterator.fragment().charFormat().anchorNames()
                           if name.startswith(_MARKER)), None)
            if marker is not None:
                break
            iterator += 1
        if marker is not None:
            following = block.next()
            while following.isValid():
                table = QTextCursor(following).currentTable()
                if table is not None:
                    kind, _, policy = marker[len(_MARKER):].partition("-")
                    yield block, table, kind, policy
                    break
                if following.text().strip():
                    break
                following = following.next()
        block = block.next()


def _table_rect(layout, table):
    padding = table.format().cellPadding()
    # The Qt layout reports the content origin, but includes padding in the size.
    return layout.frameBoundingRect(table).translated(-padding, -padding)


def _row_bounds(layout, table, row):
    padding = table.format().cellPadding()
    cells = [table.cellAt(row, column) for column in range(table.columns())]
    top = min(layout.blockBoundingRect(cell.firstCursorPosition().block()).top() for cell in cells)
    bottom = max(layout.blockBoundingRect(cell.lastCursorPosition().block()).bottom() for cell in cells)
    return top - padding, bottom + padding


def prepare_pdf_frames(document, page_width, page_height):
    layout = document.documentLayout()
    tables = list(_marked_tables(document))
    for index, (marker, table, _, policy) in enumerate(tables):
        if not policy:
            continue
        start = layout.blockBoundingRect(marker).top()
        end = _table_rect(layout, table).bottom()
        if policy == "next" and index + 1 < len(tables):
            next_end = _table_rect(layout, tables[index + 1][1]).bottom()
            if next_end - start <= page_height:
                end = next_end
        if start % page_height > 2 and floor(start / page_height) != floor((end - .01) / page_height):
            cursor = QTextCursor(marker)
            block_format = cursor.blockFormat()
            block_format.setPageBreakPolicy(QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore)
            cursor.setBlockFormat(block_format)
            document.pageCount()

    pages = [[] for _ in range(document.pageCount())]
    for _, table, kind, _ in tables:
        outer = _table_rect(layout, table)
        rows = [_row_bounds(layout, table, row) for row in range(table.rows())] if kind in {"grid", "meta"} else []
        rectangles = [outer]
        if kind == "pair":
            padding = table.format().cellPadding()
            rectangles = []
            for column in (0, table.columns() - 1):
                content = layout.blockBoundingRect(table.cellAt(0, column).firstCursorPosition().block())
                rectangles.append(QRectF(content.left() - padding, outer.top(),
                                         content.width() + 2 * padding, outer.height()))
        for rect in rectangles:
            first = max(0, floor(rect.top() / page_height))
            last = min(len(pages) - 1, floor((rect.bottom() - .01) / page_height))
            for index in range(first, last + 1):
                page_top = index * page_height
                page_bottom = page_top + page_height
                top = max(rect.top(), page_top + .45)
                bottom = min(rect.bottom(), page_bottom - .45)
                if rows and index < last:
                    ends = [end for start, end in rows if start < page_bottom and end > top]
                    if not ends:
                        continue
                    bottom = min(bottom, max(ends))
                left = max(rect.left(), .45)
                right = min(rect.right(), page_width - .45)
                if right <= left or bottom <= top:
                    continue
                separators = tuple(start for start, _ in rows[1:] if top + 1 < start < bottom - 1)
                pages[index].append(PdfFrame(QRectF(left, top, right - left, bottom - top),
                                             kind != "grid", separators))
    return pages


def draw_pdf_frames(painter, frames, *, background):
    painter.save()
    if background:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#f6f9fc"))
        for frame in frames:
            if frame.shaded:
                painter.drawRoundedRect(frame.rect, 4, 4)
    else:
        for frame in frames:
            # Hide the tiny corners of Qt's rectangular header fill.
            if not frame.shaded:
                outer = QPainterPath()
                outer.addRect(frame.rect)
                rounded = QPainterPath()
                rounded.addRoundedRect(frame.rect, 4, 4)
                painter.fillPath(outer.subtracted(rounded), QColor("white"))

            painter.setPen(QPen(QColor(_FRAME_COLOR), .55))
            for y in frame.separators:
                painter.drawLine(QLineF(frame.rect.left(), y, frame.rect.right(), y))
            painter.setPen(QPen(QColor(_FRAME_COLOR), .7))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(frame.rect, 4, 4)
    painter.restore()

