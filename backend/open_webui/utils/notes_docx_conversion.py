import base64
import html
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET

from markdown import markdown

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


@dataclass
class DocxConversionResult:
    title: str
    markdown: str
    html: str
    report: dict[str, Any]
    original_attachment: dict[str, Any] | None = None


def _qn(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}"


def _build_relationship_map(docx_zip: zipfile.ZipFile) -> dict[str, str]:
    rels_path = "word/_rels/document.xml.rels"
    if rels_path not in docx_zip.namelist():
        return {}

    root = ET.fromstring(docx_zip.read(rels_path))
    rel_map: dict[str, str] = {}
    for rel in root.findall(_qn(PKG_REL_NS, "Relationship")):
        rid = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rid and target:
            rel_map[rid] = target
    return rel_map


def _extract_footnotes(docx_zip: zipfile.ZipFile) -> dict[str, str]:
    footnotes_path = "word/footnotes.xml"
    if footnotes_path not in docx_zip.namelist():
        return {}

    root = ET.fromstring(docx_zip.read(footnotes_path))
    footnotes: dict[str, str] = {}
    for fn in root.findall(_qn(W_NS, "footnote")):
        fn_id = fn.attrib.get(_qn(W_NS, "id"))
        if not fn_id or fn_id.startswith("-"):
            continue
        text = " ".join(t.text or "" for t in fn.findall(f".//{_qn(W_NS, 't')}")).strip()
        if text:
            footnotes[fn_id] = text
    return footnotes


def _extract_comments(docx_zip: zipfile.ZipFile) -> dict[str, str]:
    comments_path = "word/comments.xml"
    if comments_path not in docx_zip.namelist():
        return {}

    root = ET.fromstring(docx_zip.read(comments_path))
    comments: dict[str, str] = {}
    for comment in root.findall(_qn(W_NS, "comment")):
        cid = comment.attrib.get(_qn(W_NS, "id"))
        text = " ".join(t.text or "" for t in comment.findall(f".//{_qn(W_NS, 't')}")).strip()
        if cid and text:
            comments[cid] = text
    return comments


def _run_to_markdown(run: ET.Element, report: dict[str, Any], rel_map: dict[str, str]) -> str:
    text = "".join((node.text or "") for node in run.findall(_qn(W_NS, "t")))
    if not text:
        text = ""

    run_props = run.find(_qn(W_NS, "rPr"))
    if run_props is not None:
        if run_props.find(_qn(W_NS, "b")) is not None:
            text = f"**{text}**"
        if run_props.find(_qn(W_NS, "i")) is not None:
            text = f"*{text}*"
        if run_props.find(_qn(W_NS, "u")) is not None:
            text = f"<u>{text}</u>"

    drawing = run.find(_qn(W_NS, "drawing"))
    if drawing is not None:
        blip = drawing.find(f".//{{http://schemas.openxmlformats.org/drawingml/2006/main}}blip")
        if blip is not None:
            rid = blip.attrib.get(f"{{{R_NS}}}embed")
            if rid:
                target = rel_map.get(rid, "embedded-image")
                report["mapped"]["images"] += 1
                return f"![Image]({target})"
        report["unsupported_elements"].append("drawing")

    return text


def _parse_table(table: ET.Element, report: dict[str, Any], rel_map: dict[str, str]) -> str:
    rows: list[list[str]] = []
    for tr in table.findall(_qn(W_NS, "tr")):
        row: list[str] = []
        for tc in tr.findall(_qn(W_NS, "tc")):
            cells: list[str] = []
            for p in tc.findall(_qn(W_NS, "p")):
                paragraph = "".join(_run_to_markdown(r, report, rel_map) for r in p.findall(_qn(W_NS, "r"))).strip()
                if paragraph:
                    cells.append(paragraph)
            row.append("<br/>".join(cells) if cells else "")
        if row:
            rows.append(row)

    if not rows:
        return ""

    report["mapped"]["tables"] += 1
    header = rows[0]
    sep = ["---"] * len(header)
    md_rows = [f"| {' | '.join(header)} |", f"| {' | '.join(sep)} |"]
    for row in rows[1:]:
        padded = row + [""] * max(0, len(header) - len(row))
        md_rows.append(f"| {' | '.join(padded[:len(header)])} |")
    return "\n".join(md_rows)


def import_docx(content: bytes, filename: str, store_original_attachment: bool = False) -> DocxConversionResult:
    report: dict[str, Any] = {
        "source": filename,
        "mapped": {
            "styles": 0,
            "tables": 0,
            "images": 0,
            "footnotes": 0,
            "comments": 0,
        },
        "unsupported_elements": [],
        "lossy": False,
    }

    with zipfile.ZipFile(io.BytesIO(content)) as docx_zip:
        if "word/document.xml" not in docx_zip.namelist():
            raise ValueError("Invalid DOCX file: missing word/document.xml")

        rel_map = _build_relationship_map(docx_zip)
        footnotes = _extract_footnotes(docx_zip)
        comments = _extract_comments(docx_zip)

        root = ET.fromstring(docx_zip.read("word/document.xml"))
        body = root.find(_qn(W_NS, "body"))
        if body is None:
            raise ValueError("Invalid DOCX file: missing body")

        blocks: list[str] = []
        encountered_comments: list[str] = []
        encountered_footnotes: list[str] = []

        for child in list(body):
            if child.tag == _qn(W_NS, "p"):
                p_props = child.find(_qn(W_NS, "pPr"))
                prefix = ""
                if p_props is not None:
                    p_style = p_props.find(_qn(W_NS, "pStyle"))
                    if p_style is not None:
                        style_val = p_style.attrib.get(_qn(W_NS, "val"), "")
                        if style_val.startswith("Heading"):
                            level = style_val.replace("Heading", "")
                            if level.isdigit():
                                prefix = "#" * min(6, int(level)) + " "
                                report["mapped"]["styles"] += 1
                        elif style_val in {"Title", "Subtitle"}:
                            prefix = "## " if style_val == "Subtitle" else "# "
                            report["mapped"]["styles"] += 1

                parts: list[str] = []
                for run in child.findall(_qn(W_NS, "r")):
                    parts.append(_run_to_markdown(run, report, rel_map))

                for fn_ref in child.findall(f".//{_qn(W_NS, 'footnoteReference')}"):
                    fn_id = fn_ref.attrib.get(_qn(W_NS, "id"))
                    if fn_id and fn_id in footnotes:
                        encountered_footnotes.append(fn_id)
                        report["mapped"]["footnotes"] += 1
                        parts.append(f"[^{fn_id}]")

                for comment_ref in child.findall(f".//{_qn(W_NS, 'commentReference')}"):
                    cid = comment_ref.attrib.get(_qn(W_NS, "id"))
                    if cid and cid in comments:
                        encountered_comments.append(cid)
                        report["mapped"]["comments"] += 1
                        parts.append(f"[comment:{cid}]")

                text = (prefix + "".join(parts)).strip()
                if text:
                    blocks.append(text)
            elif child.tag == _qn(W_NS, "tbl"):
                table_md = _parse_table(child, report, rel_map)
                if table_md:
                    blocks.append(table_md)
            elif child.tag != _qn(W_NS, "sectPr"):
                report["unsupported_elements"].append(child.tag.split("}")[-1])

        if encountered_footnotes:
            blocks.append("\n## Footnotes")
            for fid in sorted(set(encountered_footnotes), key=lambda x: int(x) if x.isdigit() else x):
                blocks.append(f"[^{fid}]: {footnotes[fid]}")

        if encountered_comments:
            blocks.append("\n## Comments")
            for cid in sorted(set(encountered_comments), key=lambda x: int(x) if x.isdigit() else x):
                blocks.append(f"- [{cid}] {comments[cid]}")

    markdown_content = "\n\n".join(blocks).strip()
    html_content = markdown(markdown_content)

    unsupported = sorted(set(report["unsupported_elements"]))
    report["unsupported_elements"] = unsupported
    report["lossy"] = bool(unsupported)

    attachment = None
    if store_original_attachment:
        attachment = {
            "filename": filename,
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "content_base64": base64.b64encode(content).decode("utf-8"),
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }

    title = re.sub(r"\.docx$", "", filename, flags=re.IGNORECASE) or "Imported Document"
    return DocxConversionResult(
        title=title,
        markdown=markdown_content,
        html=html_content,
        report=report,
        original_attachment=attachment,
    )


def _md_to_docx_xml(title: str, md: str) -> str:
    paragraphs: list[str] = []
    lines = md.splitlines()
    in_table = False

    for line in lines:
        if line.strip().startswith("|") and line.strip().endswith("|"):
            in_table = True
            continue
        if in_table and (set(line.replace("|", "").strip()) == {"-"} or not line.strip()):
            continue
        if in_table and not (line.strip().startswith("|") and line.strip().endswith("|")):
            in_table = False

        if not line.strip():
            paragraphs.append('<w:p/>')
            continue

        heading_level = 0
        while heading_level < len(line) and line[heading_level] == "#":
            heading_level += 1
        text = line[heading_level:].strip() if heading_level and line[heading_level:heading_level + 1] == " " else line
        escaped = html.escape(text)

        ppr = ""
        if 1 <= heading_level <= 6:
            ppr = f'<w:pPr><w:pStyle w:val="Heading{heading_level}"/></w:pPr>'

        paragraphs.append(
            f"<w:p>{ppr}<w:r><w:t xml:space=\"preserve\">{escaped}</w:t></w:r></w:p>"
        )

    body = "".join(paragraphs)
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:r="{R_NS}" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:w10="urn:schemas-microsoft-com:office:word" xmlns:w="{W_NS}" mc:Ignorable="w14 wp14">
  <w:body>{body}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body>
</w:document>'''


def export_note_to_docx(title: str, markdown_content: str) -> tuple[bytes, dict[str, Any]]:
    report = {
        "mapped": {"styles": 0, "tables": 0, "images": 0, "footnotes": 0, "comments": 0},
        "unsupported_elements": [],
        "lossy": False,
    }

    xml = _md_to_docx_xml(title, markdown_content)

    report["mapped"]["styles"] = len(re.findall(r"^#{1,6}\s", markdown_content, flags=re.MULTILINE))
    if re.search(r"\|.*\|", markdown_content):
        report["unsupported_elements"].append("tables")
    if re.search(r"!\[[^\]]*\]\([^\)]+\)", markdown_content):
        report["unsupported_elements"].append("images")
    if re.search(r"\[\^[^\]]+\]", markdown_content):
        report["unsupported_elements"].append("footnotes")

    report["unsupported_elements"] = sorted(set(report["unsupported_elements"]))
    report["lossy"] = bool(report["unsupported_elements"])

    content_types = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="{CONTENT_TYPES_NS}">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''

    rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{PKG_REL_NS}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''

    app_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Open WebUI</Application></Properties>'''

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    core_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>{html.escape(title)}</dc:title><dc:creator>Open WebUI</dc:creator><cp:lastModifiedBy>Open WebUI</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>'''

    bytes_io = io.BytesIO()
    with zipfile.ZipFile(bytes_io, "w", zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types)
        docx.writestr("_rels/.rels", rels)
        docx.writestr("docProps/app.xml", app_xml)
        docx.writestr("docProps/core.xml", core_xml)
        docx.writestr("word/document.xml", xml)

    return bytes_io.getvalue(), report
