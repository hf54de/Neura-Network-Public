"""Rich-text description sections shared by the project report layouts."""

import re
from html import escape

from PySide6.QtGui import QTextCursor, QTextDocument, QTextDocumentFragment


def report_description_parts(description):
    """Normalize project rich text and split a recognizable closing input/output pair."""
    document = QTextDocument()
    document.setHtml(description)

    def body(markup, plain_text):
        match = re.search(r"<body\b([^>]*)>(.*?)</body>", markup, re.DOTALL)
        return f"<div{match[1]}>{match[2]}</div>" if match else escape(plain_text)

    def fragment(start, end):
        if end <= start:
            return ""
        cursor = QTextCursor(document)
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        selected = QTextDocumentFragment(cursor)
        # Qt treats these markers as the import boundary of a whole document.
        markup = selected.toHtml().replace("<!--StartFragment-->", "").replace("<!--EndFragment-->", "")
        return body(markup, selected.toPlainText())

    headings = []
    block = document.begin()
    while block.isValid():
        level = block.blockFormat().headingLevel()
        if level and QTextCursor(block).currentFrame() == document.rootFrame():
            name = " ".join(block.text().lower().split()).rstrip(":")
            headings.append((name, level, block.position()))
        block = block.next()

    inputs = {"eingangsgrößen", "eingänge", "inputs", "input variables", "inputs (input quantities)"}
    outputs = {"ausgangsgrößen", "ausgänge", "outputs", "output variables", "outputs (output quantities)"}
    # Keep an unfamiliar outline in its original reading order.
    if len(headings) >= 2:
        input_heading, output_heading = headings[-2:]
        if input_heading[0] in inputs and output_heading[0] in outputs and input_heading[1] == output_heading[1]:
            input_start, output_start = input_heading[2], output_heading[2]
            return (
                fragment(0, input_start - 1),
                fragment(input_start, output_start - 1),
                fragment(output_start, document.characterCount() - 1),
            )
    return body(document.toHtml(), document.toPlainText()), "", ""
