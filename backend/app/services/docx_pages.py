"""DOCX pagination from stored boundaries, without pretending to render Word layout."""
from __future__ import annotations

import io
import posixpath
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


@dataclass(slots=True)
class DocxBlock:
    page: int
    text: str
    paragraph_number: int | None
    location: str
    is_cell: bool = False


def _enabled(node: ET.Element | None) -> bool:
    return node is not None and node.get(W + "val", "true").lower() not in {"false", "0", "off"}


def _paragraphs(parent: ET.Element, location: str = "", tables: list[int] | None = None) -> Iterator[tuple[ET.Element, str]]:
    tables = tables if tables is not None else [0]
    for child in parent:
        if child.tag == W + "p":
            yield child, location
        elif child.tag == W + "tbl":
            tables[0] += 1
            table = tables[0]
            for row, tr in enumerate(child.findall(W + "tr"), 1):
                for column, tc in enumerate(tr.findall(W + "tc"), 1):
                    address = f"{location + ' / ' if location else ''}Table {table} / Row {row} / Cell {column}"
                    yield from _paragraphs(tc, address, tables)
        elif child.tag in {W + "sdt", W + "sdtContent", W + "customXml", W + "ins"}:
            yield from _paragraphs(child, location, tables)


def _inline_nodes(node: ET.Element) -> Iterator[ET.Element]:
    for child in node:
        if child.tag in {W + "pPr", W + "rPr", W + "del", W + "drawing", W + "pict"}:
            continue
        yield child
        yield from _inline_nodes(child)


def read_docx(payload: bytes) -> tuple[list[DocxBlock], int]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        body = ET.fromstring(archive.read("word/document.xml")).find(W + "body")
        if body is None:
            return [], 0
        styles: dict[str, ET.Element] = {}
        default_style = ""
        if "word/styles.xml" in archive.namelist():
            for style in ET.fromstring(archive.read("word/styles.xml")).findall(W + "style"):
                styles[style.get(W + "styleId", "")] = style
                if style.get(W + "type") == "paragraph" and _enabled_attribute(style, "default"):
                    default_style = style.get(W + "styleId", "")

        def paragraph_property(paragraph: ET.Element, name: str) -> ET.Element | None:
            direct = paragraph.find(f"{W}pPr/{W}{name}")
            if direct is not None:
                return direct
            style_node = paragraph.find(f"{W}pPr/{W}pStyle")
            key = style_node.get(W + "val", "") if style_node is not None else default_style
            visited: set[str] = set()
            while key in styles and key not in visited:
                visited.add(key)
                style = styles[key]
                value = style.find(f"{W}pPr/{W}{name}")
                if value is not None:
                    return value
                base = style.find(W + "basedOn")
                key = base.get(W + "val", "") if base is not None else ""
            return None

        paragraphs = list(_paragraphs(body))
        sections = [p.find(f"{W}pPr/{W}sectPr") for p, location in paragraphs if not location]
        sections = [s for s in sections if s is not None]
        final_section = body.find(W + "sectPr")
        sections.append(final_section if final_section is not None else ET.Element(W + "sectPr"))
        blocks: list[DocxBlock] = []
        page = 1
        last_page = 1
        section = 0
        page_sections = {1: 0}
        section_first_pages = {0: 1}
        paragraph_counts: dict[int, int] = {}
        occupied: set[int] = set()
        hard_boundary_pending = False
        row_starts: dict[str, tuple[int, bool]] = {}
        previous_cell = ""

        def advance(hard: bool = True) -> None:
            nonlocal page, last_page, hard_boundary_pending
            page += 1
            last_page = max(last_page, page)
            page_sections[page] = section
            hard_boundary_pending = hard

        for paragraph, location in paragraphs:
            if location and location != previous_cell:
                # Cells in a row begin together; a long first cell must not
                # move the next cell's opening text to its own final page.
                row = location.rsplit(" / Cell ", 1)[0]
                page, hard_boundary_pending = row_starts.setdefault(row, (last_page, hard_boundary_pending))
            elif not location and previous_cell:
                page = last_page
                hard_boundary_pending = page not in occupied
            previous_cell = location
            parts: list[str] = []
            outline = paragraph_property(paragraph, "outlineLvl")
            heading = outline is not None and outline.get(W + "val", "9") in {str(i) for i in range(9)}

            def flush() -> None:
                text = "".join(parts).strip()
                parts.clear()
                if not text:
                    return
                number = None
                if not location:
                    number = paragraph_counts.get(page, 0) + 1
                    paragraph_counts[page] = number
                address = location or f"{'Heading / ' if heading else ''}Paragraph {number}"
                blocks.append(DocxBlock(page, text, number, address, bool(location)))
                occupied.add(page)

            if _enabled(paragraph_property(paragraph, "pageBreakBefore")) and page in occupied:
                advance()
            for node in _inline_nodes(paragraph):
                if node.tag == W + "br" and node.get(W + "type") == "page":
                    flush()
                    advance()
                elif node.tag == W + "lastRenderedPageBreak":
                    flush()
                    if hard_boundary_pending:
                        hard_boundary_pending = False
                    else:
                        advance(hard=False)
                elif node.tag == W + "t" and node.text:
                    parts.append(node.text)
                    if node.text.strip():
                        hard_boundary_pending = False
                elif node.tag == W + "tab":
                    parts.append("\t")
                elif node.tag in {W + "br", W + "cr"}:
                    parts.append("\n")
            flush()
            if not location and paragraph.find(f"{W}pPr/{W}sectPr") is not None:
                section += 1
                # sectPr describes its own section; the following section's
                # properties determine the break at this boundary.
                start = sections[section].find(W + "type")
                kind = start.get(W + "val", "nextPage") if start is not None else "nextPage"
                if kind not in {"continuous", "nextColumn"}:
                    advance()
                    if kind in {"evenPage", "oddPage"} and page % 2 != int(kind == "oddPage"):
                        advance()
                section_first_pages[section] = page

        _add_headers_footers(archive, sections, page_sections, section_first_pages, blocks)
        return blocks, last_page


def _enabled_attribute(node: ET.Element, name: str) -> bool:
    return node.get(W + name, "false").lower() not in {"false", "0", "off"}


def _add_headers_footers(
    archive: zipfile.ZipFile, sections: list[ET.Element], page_sections: dict[int, int],
    first_pages: dict[int, int], blocks: list[DocxBlock],
) -> None:
    """Only referenced headers/footers belong to pages; they aren't body paragraphs."""
    rel_path = "word/_rels/document.xml.rels"
    if rel_path not in archive.namelist():
        return
    targets = {
        rel.get("Id"): posixpath.normpath(posixpath.join("word", rel.get("Target", ""))).lstrip("/")
        for rel in ET.fromstring(archive.read(rel_path))
        if rel.get("TargetMode") != "External"
    }
    even_odd = False
    if "word/settings.xml" in archive.namelist():
        even_odd = _enabled(ET.fromstring(archive.read("word/settings.xml")).find(W + "evenAndOddHeaders"))
    inherited: dict[tuple[str, str], str] = {}
    references: list[dict[tuple[str, str], str]] = []
    for properties in sections:
        for kind in ("header", "footer"):
            for ref in properties.findall(W + kind + "Reference"):
                target = targets.get(ref.get(R + "id"))
                if target:
                    inherited[(kind, ref.get(W + "type", "default"))] = target
        references.append(dict(inherited))
    for page, section in page_sections.items():
        variant = ("first" if page == first_pages[section] and _enabled(sections[section].find(W + "titlePg"))
                   else "even" if even_odd and page % 2 == 0 else "default")
        for kind in ("header", "footer"):
            target = references[section].get((kind, variant))
            if not target or target not in archive.namelist():
                continue
            for paragraph, location in _paragraphs(ET.fromstring(archive.read(target))):
                text = "".join(n.text or "" for n in _inline_nodes(paragraph) if n.tag == W + "t").strip()
                if text:
                    blocks.append(DocxBlock(page, text, None, f"{kind.title()} {location}".strip(), bool(location)))
