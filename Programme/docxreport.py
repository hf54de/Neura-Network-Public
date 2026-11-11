# -------------------------------------------------------------------------------------------------
# Datei: docxreport.py
# Zweck: Erzeugt Projektberichte im Word-Format und unterstützt den PDF-Export.
# Letzte Änderung: 03.08.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def xml_text(value):
    return escape(str(value), quote=True)


class _DescriptionHtmlParser(HTMLParser):
    """Kleine HTML-zu-OOXML-Hilfe für die formatierte Projektbeschreibung."""

    BLOCKS = {"p", "div", "h1", "h2", "h3", "li"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.current = []
        self.current_tag = "p"
        self.current_list_depth = 0
        self.formats = [{"bold": False, "italic": False, "underline": False}]
        self.list_depth = 0
        self.ignored_depth = 0

    def _finish(self):
        if self.current and any(text.strip() for text, _fmt in self.current):
            self.blocks.append(
                (self.current, self.current_tag, self.current_list_depth)
            )
            self.current = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"head", "style", "script", "title", "meta"}:
            self.ignored_depth += 1
            return
        if self.ignored_depth:
            return
        if tag in self.BLOCKS:
            self._finish()
            self.current_tag = tag
            self.current_list_depth = self.list_depth
        if tag in {"ul", "ol"}:
            self.list_depth += 1
        state = dict(self.formats[-1])
        if tag in {"b", "strong", "h1", "h2", "h3"}:
            state["bold"] = True
        if tag in {"i", "em"}:
            state["italic"] = True
        if tag == "u":
            state["underline"] = True
        if tag == "h1":
            state["size"] = 32
        elif tag == "h2":
            state["size"] = 27
        elif tag == "h3":
            state["size"] = 23
        for name, value in attrs:
            if name == "style":
                for declaration in value.split(";"):
                    key, _, raw = declaration.partition(":")
                    key, raw = key.strip().lower(), raw.strip()
                    if key == "font-family" and raw:
                        state["font"] = raw.strip("'\"").split(",")[0]
                    elif key == "font-size" and raw.endswith("pt"):
                        try:
                            state["size"] = int(round(float(raw[:-2]) * 2))
                        except ValueError:
                            pass
                    elif key == "font-weight":
                        try:
                            state["bold"] = int(raw) >= 600
                        except ValueError:
                            state["bold"] = raw.lower() in {"bold", "bolder"}
                    elif key == "font-style":
                        state["italic"] = raw.lower() == "italic"
                    elif key == "text-decoration":
                        state["underline"] = "underline" in raw.lower()
        if tag != "br":
            self.formats.append(state)
        if tag == "li":
            self.current.append(("• ", state))
        elif tag == "br":
            self.current.append(("\n", state))

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"head", "style", "script", "title", "meta"}:
            self.ignored_depth = max(0, self.ignored_depth - 1)
            return
        if self.ignored_depth:
            return
        if tag in self.BLOCKS:
            self._finish()
        if tag in {"ul", "ol"}:
            self.list_depth = max(0, self.list_depth - 1)
        if tag != "br" and len(self.formats) > 1:
            self.formats.pop()

    def handle_data(self, data):
        if data and not self.ignored_depth and (data.strip() or "\n" not in data):
            self.current.append((data, dict(self.formats[-1])))

    def close(self):
        super().close()
        self._finish()


class DocxReport:
    """Kleiner OOXML-Writer für die programmeigenen Trainingsberichte."""

    PAGE_WIDTH = 11906
    MARGIN = 907
    CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
    PANEL_GAP = 200
    PANEL_PADDING = 100
    FRAME_COLOR = "D4E2ED"
    PANEL_FILL = "F6F9FC"
    HEADER_FILL = "EFF5FA"

    def __init__(self, title):
        self.title = str(title)
        self.parts = []
        self.images = []

    def paragraph(
        self, text="", bold=False, style=None, keep_next=False, centered=False
    ):
        properties = []
        if style:
            properties.append(f'<w:pStyle w:val="{style}"/>')
        if keep_next:
            properties.append('<w:keepNext/>')
        if centered:
            properties.append('<w:jc w:val="center"/>')
        runs = []
        for index, line in enumerate(str(text).splitlines() or [""]):
            if index:
                runs.append('<w:r><w:br/></w:r>')
            run_properties = '<w:rPr><w:b/></w:rPr>' if bold else ''
            runs.append(
                f'<w:r>{run_properties}<w:t xml:space="preserve">'
                f'{xml_text(line)}</w:t></w:r>'
            )
        self.parts.append(
            f'<w:p><w:pPr>{"".join(properties)}</w:pPr>{"".join(runs)}</w:p>'
        )

    def formatted_html(self, html):
        """Übernimmt die gebräuchlichen Textformatierungen der Beschreibung."""
        parser = _DescriptionHtmlParser()
        parser.feed(str(html or ""))
        parser.close()
        for block, tag, list_depth in parser.blocks:
            runs = []
            for value, fmt in block:
                properties = []
                if fmt.get("font"):
                    font = xml_text(fmt["font"])
                    properties.append(f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}"/>')
                if fmt.get("bold"):
                    properties.append("<w:b/>")
                if fmt.get("italic"):
                    properties.append("<w:i/>")
                if fmt.get("underline"):
                    properties.append('<w:u w:val="single"/>')
                if fmt.get("size"):
                    properties.append(f'<w:sz w:val="{int(fmt["size"])}"/>')
                run_text = []
                for index, line in enumerate(value.split("\n")):
                    if index:
                        run_text.append("<w:br/>")
                    run_text.append(f'<w:t xml:space="preserve">{xml_text(line)}</w:t>')
                runs.append(f'<w:r><w:rPr>{"".join(properties)}</w:rPr>{"".join(run_text)}</w:r>')
            if tag in {"h1", "h2", "h3"}:
                paragraph_properties = [
                    '<w:keepNext/>',
                    '<w:spacing w:line="240" w:lineRule="auto" w:before="100" w:after="30"/>',
                ]
            else:
                paragraph_properties = [
                    '<w:spacing w:line="240" w:lineRule="auto" w:after="20"/>'
                ]
            if tag == "li":
                paragraph_properties.append(
                    f'<w:ind w:left="{360 + max(0, list_depth) * 260}" w:hanging="180"/>'
                )
            self.parts.append(
                f'<w:p><w:pPr>{"".join(paragraph_properties)}</w:pPr>'
                + "".join(runs) + "</w:p>"
            )

    def spacer(self, points=5, *, keep_next=False):
        """Keep adjacent Word tables distinct without a full empty text line."""
        twips = round(points * 20)
        keep = '<w:keepNext/>' if keep_next else ''
        self.parts.append(
            f'<w:p><w:pPr>{keep}<w:spacing w:before="0" w:after="0" '
            f'w:line="{twips}" w:lineRule="exact"/></w:pPr></w:p>'
        )

    def heading(self, text, level=1):
        self.paragraph(text, style=f"Heading{level}", keep_next=True)

    def _borders(self, element, *, horizontal=False):
        edges = ["top", "left", "bottom", "right"]
        if horizontal:
            edges.append("insideH")
        return f'<w:{element}>' + ''.join(
            f'<w:{edge} w:val="single" w:sz="4" w:color="{self.FRAME_COLOR}"/>'
            for edge in edges
        ) + f'</w:{element}>'

    @classmethod
    def panel_column_width(cls, columns):
        return (cls.CONTENT_WIDTH - (columns - 1) * cls.PANEL_GAP) // columns

    @classmethod
    def panel_image_width(cls, columns=1):
        return (cls.panel_column_width(columns) - 2 * cls.PANEL_PADDING) / 1440

    def panels(self, *render_columns, keep_together=False, keep_with_next=False):
        """Build a Word table with one or two separately framed editable cells."""
        width = self.panel_column_width(len(render_columns))
        gap = self.PANEL_GAP
        grid = [width, gap, width] if len(render_columns) == 2 else [width]
        row_properties = '<w:trPr><w:cantSplit/></w:trPr>' if keep_together else ''
        self.parts.extend([
            '<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/>'
            '<w:jc w:val="center"/><w:tblLayout w:type="fixed"/></w:tblPr>',
            '<w:tblGrid>' + ''.join(f'<w:gridCol w:w="{col}"/>' for col in grid) + '</w:tblGrid>',
            '<w:tr>' + row_properties,
        ])
        for index, render in enumerate(render_columns):
            if index:
                self.parts.append(
                    f'<w:tc><w:tcPr><w:tcW w:w="{gap}" w:type="dxa"/></w:tcPr>'
                    '<w:p/></w:tc>'
                )
            self.parts.append(
                f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>'
                + self._borders("tcBorders")
                + f'<w:shd w:val="clear" w:fill="{self.PANEL_FILL}"/><w:tcMar>'
                + ''.join(f'<w:{edge} w:w="{self.PANEL_PADDING}" w:type="dxa"/>'
                          for edge in ("top", "left", "bottom", "right"))
                + '</w:tcMar><w:vAlign w:val="top"/></w:tcPr>'
            )
            render()
            self.parts.append('</w:tc>')
        self.parts.append('</w:tr></w:tbl>')
        self.spacer(keep_next=keep_with_next)

    def table(self, rows, widths=None, header=False, keep_together=False, *, font_points=None, shaded=False):
        rows = [[str(value) for value in row] for row in rows]
        if not rows:
            return
        column_count = max(len(row) for row in rows)
        widths = list(widths or [1] * column_count)
        total = float(sum(widths)) or 1.0
        grid = [round(self.CONTENT_WIDTH * width / total) for width in widths]
        grid[-1] += self.CONTENT_WIDTH - sum(grid)
        size = f'<w:sz w:val="{round(font_points * 2)}"/>' if font_points is not None else ""
        content = [
            '<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:jc w:val="center"/>'
            + self._borders("tblBorders", horizontal=True)
            + '<w:tblLayout w:type="fixed"/></w:tblPr>',
            '<w:tblGrid>' + ''.join(f'<w:gridCol w:w="{width}"/>' for width in grid) + '</w:tblGrid>',
        ]
        for row_index, row in enumerate(rows):
            row_properties = ['<w:cantSplit/>']
            if header and row_index == 0:
                row_properties.append('<w:tblHeader/>')
            content.append(f'<w:tr><w:trPr>{"".join(row_properties)}</w:trPr>')
            for column_index in range(column_count):
                value = row[column_index] if column_index < len(row) else ""
                is_header = header and row_index == 0
                fill_color = self.HEADER_FILL if is_header else self.PANEL_FILL if shaded else None
                fill = f'<w:shd w:val="clear" w:fill="{fill_color}"/>' if fill_color else ''
                bold = '<w:b/>' if is_header else ''
                width = grid[min(column_index, len(grid) - 1)]
                keep_next = (
                    '<w:keepNext/>'
                    if keep_together and row_index < len(rows) - 1
                    else ''
                )
                cell_text = '</w:t><w:br/><w:t xml:space="preserve">'.join(
                    xml_text(line) for line in value.split("\n")
                )
                content.append(
                    f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{fill}'
                    '<w:vAlign w:val="center"/><w:tcMar>'
                    '<w:top w:w="45" w:type="dxa"/>'
                    '<w:left w:w="100" w:type="dxa"/>'
                    '<w:bottom w:w="45" w:type="dxa"/>'
                    '<w:right w:w="80" w:type="dxa"/>'
                    '</w:tcMar></w:tcPr>'
                    f'<w:p><w:pPr>{keep_next}<w:spacing w:before="0" w:after="0"/></w:pPr>'
                    f'<w:r><w:rPr>{bold}{size}</w:rPr><w:t xml:space="preserve">'
                    f'{cell_text}</w:t></w:r></w:p></w:tc>'
                )
            content.append('</w:tr>')
        content.append('</w:tbl>')
        self.parts.append(''.join(content))
        self.spacer()

    def image(
        self, png_data, width_px, height_px, *, width_inches, alt_text,
    ):
        image_index = len(self.images) + 1
        relationship_id = f"rId{image_index + 1}"
        self.images.append((f"image{image_index}.png", bytes(png_data), relationship_id))
        width_emu = int(float(width_inches) * 914400)
        height_emu = int(width_emu * float(height_px) / max(float(width_px), 1.0))
        paragraph = (
            '<w:p><w:pPr><w:spacing w:before="0" w:after="0"/><w:jc w:val="center"/></w:pPr>'
            '<w:r><w:drawing>'
            '<wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'<wp:extent cx="{width_emu}" cy="{height_emu}"/>'
            f'<wp:docPr id="{image_index}" name="Diagramm {image_index}" descr="{xml_text(alt_text)}"/>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="Bild"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{relationship_id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
            f'<a:ext cx="{width_emu}" cy="{height_emu}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
            '</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
        )
        self.parts.append(paragraph)

    def save(self, file_path):
        file_path = Path(file_path)
        document_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><w:body>'
            + ''.join(self.parts)
            + f'<w:sectPr><w:pgSz w:w="{self.PAGE_WIDTH}" w:h="16838"/>'
              f'<w:pgMar w:top="{self.MARGIN}" w:right="{self.MARGIN}" '
              f'w:bottom="{self.MARGIN}" w:left="{self.MARGIN}" '
              'w:header="400" w:footer="400" w:gutter="0"/></w:sectPr>'
              '</w:body></w:document>'
        )
        relationships = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
        ]
        for name, _data, relationship_id in self.images:
            relationships.append(
                f'<Relationship Id="{relationship_id}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                f'Target="media/{name}"/>'
            )
        relationships.append('</Relationships>')
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        with ZipFile(file_path, 'w', ZIP_DEFLATED) as archive:
            archive.writestr('[Content_Types].xml', self.content_types())
            archive.writestr('_rels/.rels', self.root_relationships())
            archive.writestr('docProps/core.xml', self.core_properties(timestamp))
            archive.writestr('word/document.xml', document_xml)
            archive.writestr('word/styles.xml', self.styles())
            archive.writestr('word/_rels/document.xml.rels', ''.join(relationships))
            for name, data, _relationship_id in self.images:
                archive.writestr(f'word/media/{name}', data)

    @staticmethod
    def content_types():
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Default Extension="png" ContentType="image/png"/>'
                '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
                '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
                '</Types>')

    @staticmethod
    def root_relationships():
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
                '</Relationships>')

    def core_properties(self, timestamp):
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                f'<dc:title>{xml_text(self.title)}</dc:title><dc:creator>NeuronNetz</dc:creator>'
                f'<dcterms:created xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:created>'
                '</cp:coreProperties>')

    @classmethod
    def styles(cls):
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI"/>'
            '<w:color w:val="172C44"/><w:sz w:val="20"/></w:rPr></w:rPrDefault>'
            '<w:pPrDefault><w:pPr><w:spacing w:after="60"/></w:pPr></w:pPrDefault></w:docDefaults>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
            '<w:name w:val="Normal"/><w:qFormat/></w:style>'
            '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
            '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:keepNext/><w:spacing w:after="220"/></w:pPr>'
            '<w:rPr><w:b/><w:sz w:val="48"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="ReportLabel"><w:name w:val="Report Label"/>'
            '<w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="60"/></w:pPr>'
            '<w:rPr><w:b/><w:color w:val="21517C"/><w:sz w:val="18"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
            '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:keepNext/><w:pBdr>'
            f'<w:top w:val="single" w:sz="4" w:space="6" w:color="{cls.FRAME_COLOR}"/>'
            '</w:pBdr><w:spacing w:before="220" w:after="100"/><w:outlineLvl w:val="0"/></w:pPr>'
            '<w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
            '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:keepNext/><w:spacing w:before="60" w:after="70"/><w:outlineLvl w:val="1"/></w:pPr>'
            '<w:rPr><w:b/><w:sz w:val="22"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="ReportCaption"><w:name w:val="Report Caption"/>'
            '<w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="60" w:after="0"/></w:pPr>'
            '<w:rPr><w:color w:val="415A71"/><w:sz w:val="18"/></w:rPr></w:style>'
            '</w:styles>'
        )
