"""Read a default LinkedIn resume from its PDF structure tree.

LinkedIn's Apache FOP export is a tagged PDF. The sidebar and the body are
separate table cells, sidebar blocks start at H1 elements, and each role or
school is its own nested table. Sections are read from those nodes directly.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import IndirectObject

from src.exception import ResumeError
from src.model import LinkedInDocument
from src.util.utils import is_bullet, squash

_SIDEBAR = {"contact", "top skills", "languages", "certifications", "honors-awards"}
_BODY_LABELS = {"summary", "experience", "education"}
_LINE_TAGS = {"/H1", "/P", "/Span", "/Link"}


def read_resume(path: Path) -> LinkedInDocument:
    """Return each LinkedIn section without joining the two columns."""
    try:
        reader = PdfReader(str(path))
        root = reader.trailer["/Root"]["/StructTreeRoot"].get_object()
    except Exception as exc:
        raise ResumeError("Unable to read the LinkedIn resume structure.") from exc

    page_ids = {
        page.indirect_reference.idnum: index for index, page in enumerate(reader.pages)
    }
    chars = _chars_by_mcid(path)
    left, right = _column_cells(root, chars, page_ids)
    sidebar = _sidebar_sections(left, chars, page_ids)
    name, summary, experience, education = _body_sections(right, chars, page_ids)
    document = LinkedInDocument(
        name=name,
        summary_lines=summary,
        experience=experience,
        education=education,
        contact_lines=sidebar.get("contact", []),
        skill_lines=sidebar.get("top skills", []),
        language_lines=sidebar.get("languages", []),
        certification_lines=sidebar.get("certifications", []),
        honor_lines=sidebar.get("honors-awards", []),
    )
    if not document.name and not document.experience and not document.education:
        raise ResumeError("Unable to read the LinkedIn resume structure.")
    return document


def _chars_by_mcid(path: Path) -> dict[tuple[int, int], list[dict]]:
    import pdfplumber

    indexed: dict[tuple[int, int], list[dict]] = {}
    with pdfplumber.open(str(path)) as pdf:
        for page_index, page in enumerate(pdf.pages):
            for char in page.chars:
                mcid = char.get("mcid")
                if mcid is None or char.get("tag") == "Artifact":
                    continue
                indexed.setdefault((page_index, int(mcid)), []).append(char)
    return indexed


def _column_cells(root, chars, page_ids) -> tuple[object, object]:
    for table in _tables(root):
        cells = _direct_cells(table)
        if len(cells) < 2:
            continue
        headings = [_text(node, chars, page_ids).casefold() for node in _h1_nodes(cells[0])]
        if "contact" in headings:
            return cells[0], cells[1]
    raise ResumeError("Unable to read the LinkedIn resume structure.")


def _sidebar_sections(cell, chars, page_ids) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    heading = ""
    pending: list[object] = []

    def flush() -> None:
        if heading in _SIDEBAR and pending:
            # Contact keeps each visual line so a wrapped URL can be rejoined.
            # Every other sidebar paragraph is one item.
            sections[heading] = _paragraphs(pending, chars, page_ids, join=heading != "contact")

    for kind, node in _events(cell):
        if kind == "h1":
            flush()
            pending = []
            heading = _text(node, chars, page_ids).casefold()
            continue
        if kind == "text":
            pending.append(node)
    flush()
    return sections


def _paragraphs(nodes: list[object], chars, page_ids, *, join: bool) -> list[str]:
    lines: list[str] = []
    for node in nodes:
        visual = _lines_for([node], chars, page_ids)
        if not visual:
            continue
        if join:
            lines.append(squash(" ".join(visual)))
        else:
            lines.extend(visual)
    return lines


def _body_sections(cell, chars, page_ids):
    name = ""
    label = ""
    summary: list[str] = []
    experience: list[list[str]] = []
    education: list[list[str]] = []
    right_edge = _column_edge(cell, chars, page_ids)
    for kind, node in _events(cell):
        if kind == "h1" and not name:
            name = _text(node, chars, page_ids)
            continue
        if kind == "text":
            text = _text(node, chars, page_ids)
            if text.casefold() in _BODY_LABELS:
                label = text.casefold()
                continue
            if label == "summary" and text:
                summary.extend(_lines_for([node], chars, page_ids))
            continue
        if kind == "entry" and label == "experience":
            experience.append(_experience_lines([node], chars, page_ids, right_edge))
        elif kind == "entry" and label == "education":
            education.append(_lines_for([node], chars, page_ids))
    return name, summary, experience, education


def _events(node):
    role = _role(node)
    if role == "/Table" and not _contains_table(node):
        yield "entry", node
        return
    if role == "/H1":
        yield "h1", node
        return
    if role in _LINE_TAGS:
        yield "text", node
        return
    for child in _struct_children(node):
        yield from _events(child)


def _lines_for(nodes: list[object], chars, page_ids) -> list[str]:
    found: list[dict] = []
    for node in nodes:
        for key in _mcids(node, None, page_ids):
            found.extend(chars.get(key, []))
    return _visual_lines(found)


def _column_edge(cell, chars, page_ids) -> float:
    edge = 0.0
    for key in _mcids(cell, None, page_ids):
        for char in chars.get(key, []):
            edge = max(edge, float(char["x1"]))
    return edge


def _experience_lines(nodes: list[object], chars, page_ids, right_edge: float) -> list[str]:
    """Join a wrapped bullet. A new bullet stays its own line.

    LinkedIn breaks a bullet where the next word no longer fits in the
    body column. That continuation often starts with a capital or '('.
    """
    found: list[dict] = []
    for node in nodes:
        for key in _mcids(node, None, page_ids):
            found.extend(chars.get(key, []))
    space = _space_width(found)
    logical: list[list] = []
    for group in _line_groups(found):
        text = _group_text(group)
        if not text or text.casefold() == "logo":
            continue
        x1 = max(float(char["x1"]) for char in group)
        word = _first_word_width(group)
        overflow = bool(logical) and not is_bullet(text) and logical[-1][1] + space + word > right_edge
        if overflow:
            logical[-1][0] = f"{logical[-1][0]} {text}"
            logical[-1][1] = x1
        else:
            logical.append([text, x1])
    return [item[0] for item in logical]


def _space_width(chars: list[dict]) -> float:
    widths = [
        float(char["x1"]) - float(char["x0"])
        for char in chars
        if str(char.get("text", "")).replace("\u00a0", " ") == " "
    ]
    if not widths:
        return 3.0
    widths.sort()
    return widths[len(widths) // 2]


def _first_word_width(group: list[dict]) -> float:
    word: list[dict] = []
    for char in sorted(group, key=lambda item: item["x0"]):
        value = str(char.get("text", "")).replace("\u00a0", " ").replace("\u200b", "")
        if value == " " and word:
            break
        if not value or value == " ":
            continue
        word.append(char)
    if not word:
        return 0.0
    return max(float(char["x1"]) for char in word) - min(float(char["x0"]) for char in word)


def _text(node, chars, page_ids) -> str:
    lines = _lines_for([node], chars, page_ids)
    return lines[0] if lines else ""


def _line_groups(chars: list[dict]) -> list[list[dict]]:
    ordered = sorted(chars, key=lambda char: (char.get("page_number", 1), char["top"], char["x0"]))
    groups: list[list[dict]] = []
    current: list[dict] = []
    anchor: float | None = None
    page = None
    for char in ordered:
        char_page = char.get("page_number", 1)
        top = float(char["top"])
        if anchor is None or char_page != page or abs(top - anchor) > 1.5:
            if current:
                groups.append(current)
            current = [char]
            anchor = top
            page = char_page
        else:
            current.append(char)
    if current:
        groups.append(current)
    return groups


def _group_text(group: list[dict]) -> str:
    ordered = sorted(group, key=lambda char: char["x0"])
    return squash(
        "".join(str(char.get("text", "")) for char in ordered).replace("\u00a0", " ").replace("\u200b", "")
    )


def _visual_lines(chars: list[dict]) -> list[str]:
    lines: list[str] = []
    for group in _line_groups(chars):
        text = _group_text(group)
        if text and text.casefold() != "logo":
            lines.append(text)
    return lines


def _mcids(node, inherited_page: int | None, page_ids) -> list[tuple[int, int]]:
    node = _resolve(node)
    if not hasattr(node, "get"):
        return []
    page = _page_index(node, page_ids)
    if page is None:
        page = inherited_page
    kids = node.get("/K")
    if kids is None:
        return []
    if not isinstance(kids, list):
        kids = [kids]
    found: list[tuple[int, int]] = []
    for kid in kids:
        kid = _resolve(kid)
        if isinstance(kid, int):
            if page is not None:
                found.append((page, kid))
            continue
        if not hasattr(kid, "get"):
            continue
        kid_page = _page_index(kid, page_ids)
        if kid_page is None:
            kid_page = page
        mcid = kid.get("/MCID")
        if mcid is not None and kid_page is not None:
            found.append((kid_page, int(mcid)))
            continue
        if kid.get("/S") or kid.get("/K") is not None:
            found.extend(_mcids(kid, kid_page, page_ids))
    return found


def _tables(node) -> list[object]:
    node = _resolve(node)
    found: list[object] = []
    if _role(node) == "/Table":
        found.append(node)
    for child in _struct_children(node):
        found.extend(_tables(child))
    return found


def _direct_cells(table) -> list[object]:
    cells: list[object] = []

    def walk(node) -> None:
        for child in _struct_children(node):
            role = _role(child)
            if role == "/Table":
                continue
            if role == "/TD":
                cells.append(child)
                continue
            walk(child)

    walk(table)
    return cells


def _h1_nodes(node) -> list[object]:
    if _role(node) == "/H1":
        return [node]
    found: list[object] = []
    for child in _struct_children(node):
        if _role(child) == "/Table":
            continue
        found.extend(_h1_nodes(child))
    return found


def _contains_table(node) -> bool:
    return any(_role(child) == "/Table" or _contains_table(child) for child in _struct_children(node))


def _struct_children(node) -> list[object]:
    node = _resolve(node)
    if not hasattr(node, "get"):
        return []
    kids = node.get("/K")
    if kids is None:
        return []
    if not isinstance(kids, list):
        kids = [kids]
    children: list[object] = []
    for kid in kids:
        kid = _resolve(kid)
        if hasattr(kid, "get") and kid.get("/S"):
            children.append(kid)
    return children


def _page_index(node, page_ids) -> int | None:
    if not hasattr(node, "get"):
        return None
    page = node.get("/Pg")
    if page is None:
        return None
    page = _resolve(page)
    reference = getattr(page, "indirect_reference", None)
    if reference is None:
        return None
    return page_ids.get(reference.idnum)


def _role(node) -> str:
    node = _resolve(node)
    if not hasattr(node, "get"):
        return ""
    return str(node.get("/S") or "")


def _resolve(obj):
    if isinstance(obj, IndirectObject):
        return obj.get_object()
    return obj
