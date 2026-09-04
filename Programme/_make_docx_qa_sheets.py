from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def make_sheets(source, output, per_sheet=16):
    output.mkdir(exist_ok=True)
    pages = sorted(source.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[1]))
    thumb_w, thumb_h = 300, 424
    label_h = 24
    cols, rows = 4, 4
    for start in range(0, len(pages), per_sheet):
        canvas = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), "#d8d8d8")
        draw = ImageDraw.Draw(canvas)
        for offset, path in enumerate(pages[start:start + per_sheet]):
            image = Image.open(path).convert("RGB")
            image.thumbnail((thumb_w - 8, thumb_h - 8))
            col, row = offset % cols, offset // cols
            x = col * thumb_w + (thumb_w - image.width) // 2
            y = row * (thumb_h + label_h) + label_h
            canvas.paste(image, (x, y))
            draw.text((col * thumb_w + 5, row * (thumb_h + label_h) + 4), path.stem, fill="black")
        canvas.save(output / f"sheet-{start // per_sheet + 1:02d}.jpg", quality=90)


root = Path(r"C:\Neuronales Netz\Dokumente")
make_sheets(root / "_qa_sps_xml_de", root / "_qa_sps_xml_de_sheets")
make_sheets(root / "_qa_sps_xml_en", root / "_qa_sps_xml_en_sheets")
