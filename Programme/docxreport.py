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
        if data and not self.ignored_depth:
            self.current.append((data, dict(self.formats[-1])))

    def close(self):
        super().close()
        self._finish()


class DocxReport:
    """Kleiner OOXML-Writer für die programmeigenen Trainingsberichte."""

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
                if fmt.get("bold"):
                    properties.append("<w:b/>")
                if fmt.get("italic"):
                    properties.append("<w:i/>")
                if fmt.get("underline"):
                    properties.append('<w:u w:val="single"/>')
                if fmt.get("font"):
                    font = xml_text(fmt["font"])
                    properties.append(f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}"/>')
                if fmt.get("size"):
                    properties.append(f'<w:sz w:val="{int(fmt["size"])}"/>')
                run_text = []
                for index, line in enumerate(value.split("\n")):
                    if index:
                        run_text.append("<w:br/>")
                    run_text.append(f'<w:t xml:space="preserve">{xml_text(line)}</w:t>')
                runs.append(f'<w:r><w:rPr>{"".join(properties)}</w:rPr>{"".join(run_text)}</w:r>')
            paragraph_properties = [
                '<w:spacing w:line="240" w:lineRule="auto" w:after="20"/>'
            ]
            if tag in {"h1", "h2", "h3"}:
                paragraph_properties.extend([
                    '<w:keepNext/>',
                    '<w:spacing w:line="240" w:lineRule="auto" w:before="100" w:after="30"/>',
                ])
            if tag == "li":
                paragraph_properties.append(
                    f'<w:ind w:left="{360 + max(0, list_depth) * 260}" w:hanging="180"/>'
                )
            self.parts.append(
                f'<w:p><w:pPr>{"".join(paragraph_properties)}</w:pPr>'
                + "".join(runs) + "</w:p>"
            )

    def spacer(self, points=8):
        """Fügt einen kontrollierten vertikalen Abstand ein."""
        twips = max(0, int(float(points) * 20))
        self.parts.append(
            f'<w:p><w:pPr><w:spacing w:after="{twips}"/></w:pPr></w:p>'
        )

    def heading(self, text, level=1, centered=False):
        style = f"Heading{max(1, min(int(level), 2))}"
        if not centered:
            self.paragraph(text, style=style, keep_next=True)
            return
        self.parts.append(
            '<w:p><w:pPr>'
            f'<w:pStyle w:val="{style}"/><w:keepNext/><w:jc w:val="center"/>'
            '</w:pPr><w:r><w:t xml:space="preserve">'
            f'{xml_text(text)}</w:t></w:r></w:p>'
        )

    def page_break(self):
        self.parts.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    def table(self, rows, widths=None, header=False, keep_together=False):
        rows = [[str(value) for value in row] for row in rows]
        if not rows:
            return
        column_count = max(len(row) for row in rows)
        widths = list(widths or [1] * column_count)
        total = float(sum(widths)) or 1.0
        grid = [max(200, int(10000 * width / total)) for width in widths]
        content = [
            '<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/>'
            '<w:tblLayout w:type="fixed"/><w:tblBorders>'
            '<w:top w:val="single" w:sz="6" w:color="AAB8C5"/>'
            '<w:left w:val="single" w:sz="6" w:color="AAB8C5"/>'
            '<w:bottom w:val="single" w:sz="6" w:color="AAB8C5"/>'
            '<w:right w:val="single" w:sz="6" w:color="AAB8C5"/>'
            '<w:insideH w:val="single" w:sz="4" w:color="C8D1DA"/>'
            '<w:insideV w:val="single" w:sz="4" w:color="C8D1DA"/>'
            '</w:tblBorders></w:tblPr>',
            '<w:tblGrid>' + ''.join(f'<w:gridCol w:w="{width}"/>' for width in grid) + '</w:tblGrid>',
        ]
        for row_index, row in enumerate(rows):
            row_properties = ['<w:cantSplit/>']
            if header and row_index == 0:
                row_properties.append('<w:tblHeader/>')
            content.append(f'<w:tr><w:trPr>{"".join(row_properties)}</w:trPr>')
            for column_index in range(column_count):
                value = row[column_index] if column_index < len(row) else ""
                fill = '<w:shd w:fill="17375E"/>' if header and row_index == 0 else ''
                color = '<w:color w:val="FFFFFF"/><w:b/>' if header and row_index == 0 else ''
                width = grid[min(column_index, len(grid) - 1)]
                keep_next = (
                    '<w:keepNext/>'
                    if keep_together and row_index < len(rows) - 1
                    else ''
                )
                content.append(
                    f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{fill}'
                    '<w:vAlign w:val="center"/><w:tcMar>'
                    '<w:top w:w="45" w:type="dxa"/>'
                    '<w:left w:w="100" w:type="dxa"/>'
                    '<w:bottom w:w="45" w:type="dxa"/>'
                    '<w:right w:w="80" w:type="dxa"/>'
                    '</w:tcMar></w:tcPr>'
                    '<w:p><w:pPr><w:spacing w:before="0" w:after="0"/>'
                    f'{keep_next}</w:pPr>'
                    f'<w:r><w:rPr>{color}</w:rPr><w:t xml:space="preserve">'
                    f'{xml_text(value)}</w:t></w:r></w:p></w:tc>'
                )
            content.append('</w:tr>')
        content.append('</w:tbl>')
        self.parts.append(''.join(content))

    def image(
        self, png_data, width_px, height_px, width_inches=7.0, framed=False,
        frame_padding_twips=120,
    ):
        image_index = len(self.images) + 1
        relationship_id = f"rId{image_index + 1}"
        self.images.append((f"image{image_index}.png", bytes(png_data), relationship_id))
        width_emu = int(float(width_inches) * 914400)
        height_emu = int(width_emu * float(height_px) / max(float(width_px), 1.0))
        paragraph = (
            '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
            '<wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'<wp:extent cx="{width_emu}" cy="{height_emu}"/>'
            f'<wp:docPr id="{image_index}" name="Diagramm {image_index}"/>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="Bild"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{relationship_id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
            f'<a:ext cx="{width_emu}" cy="{height_emu}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
            '</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
        )
        if framed:
            self.parts.append(
                '<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>'
                '<w:top w:val="single" w:sz="8" w:color="000000"/>'
                '<w:left w:val="single" w:sz="8" w:color="000000"/>'
                '<w:bottom w:val="single" w:sz="8" w:color="000000"/>'
                '<w:right w:val="single" w:sz="8" w:color="000000"/>'
                '</w:tblBorders><w:tblLayout w:type="fixed"/></w:tblPr>'
                '<w:tblGrid><w:gridCol w:w="10000"/></w:tblGrid>'
                '<w:tr><w:trPr><w:cantSplit/></w:trPr><w:tc><w:tcPr>'
                '<w:tcW w:w="10000" w:type="dxa"/><w:gridSpan w:val="1"/><w:tcMar>'
                f'<w:top w:w="{int(frame_padding_twips)}" w:type="dxa"/>'
                f'<w:left w:w="{int(frame_padding_twips)}" w:type="dxa"/>'
                f'<w:bottom w:w="{int(frame_padding_twips)}" w:type="dxa"/>'
                f'<w:right w:w="{int(frame_padding_twips)}" w:type="dxa"/>'
                '</w:tcMar></w:tcPr>' + paragraph + '</w:tc></w:tr></w:tbl>'
            )
        else:
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
            + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
              '<w:pgMar w:top="900" w:right="900" w:bottom="900" w:left="900" '
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

    @staticmethod
    def styles():
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/>'
                '<w:sz w:val="20"/></w:rPr></w:rPrDefault></w:docDefaults>'
                '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
                '<w:name w:val="Normal"/><w:qFormat/></w:style>'
                '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
                '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
                '<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/></w:pPr>'
                '<w:rPr><w:b/><w:color w:val="17375E"/><w:sz w:val="32"/></w:rPr></w:style>'
                '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
                '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
                '<w:pPr><w:keepNext/><w:spacing w:before="180" w:after="80"/></w:pPr>'
                '<w:rPr><w:b/><w:color w:val="17375E"/><w:sz w:val="26"/></w:rPr></w:style>'
                '</w:styles>')
