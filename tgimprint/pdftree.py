"""Finishing the engine's structure tree, so the claim it earns is true.

    finish(pdf) -> None     every repair below, on an open pikepdf.Pdf

Chromium's tree is good and not quite PDF/UA-1. veraPDF 1.30.3 failed every
export of 0.2.1 that carried the identifier (measured 2026-11-01 with Edge
156), on three things pdfcheck did not look at:

- Strong and Em are PDF 2.0 element types and the file has no RoleMap, so
  they are "non-standard and unmapped" (ISO 14289-1 7.1). They map to Span.
- A picture left out of the tree on purpose is drawn outside any marked
  content, and so is neither tagged nor an Artifact (7.1). The drawing is
  wrapped in /Artifact BMC ... EMC. Only drawing: a piece of text outside
  marked content is real content that lost its tag, and hiding it would be
  the worst thing this module could do, so it stays and the checker fails it.
- LI holds Lbl and a bare NonStruct. The text goes into an LBody.

Each one is measured from the file rather than assumed, so a later Edge
that writes them properly passes through here untouched.

Nothing here touches wx or prints.
"""

import pikepdf

from . import pdfcheck

STANDARD_TYPES = pdfcheck.STANDARD_TYPES

#: What the PDF 2.0 types Chromium uses are closest to in PDF 1.7.
KNOWN_ROLES = {"/Strong": "/Span", "/Em": "/Span", "/Sub": "/Span", "/Title": "/H1",
               "/Aside": "/Note", "/FENote": "/Note", "/DocumentFragment": "/Div"}

PATH_START = frozenset(("m", "re"))
PATH_PAINT = frozenset(("S", "s", "f", "F", "f*", "B", "B*", "b", "b*"))


def _used_types(pdf):
    found = set()
    seen = set()

    def visit(obj):
        if isinstance(obj, pikepdf.Array):
            for item in obj:
                visit(item)
        elif isinstance(obj, pikepdf.Dictionary):
            key = obj.objgen
            if key != (0, 0):
                if key in seen:
                    return
                seen.add(key)
            if str(obj.get("/Type", "")) in ("/MCR", "/OBJR"):
                return
            kind = obj.get("/S")
            if kind is not None:
                found.add(str(kind))
            if "/K" in obj:
                visit(obj.K)

    visit(pdf.Root.StructTreeRoot.get("/K"))
    return found


def map_roles(pdf):
    """A RoleMap entry for every non-standard type the tree uses. Returns
    the types it mapped."""
    tree = pdf.Root.StructTreeRoot
    role_map = tree.get("/RoleMap")
    if not isinstance(role_map, pikepdf.Dictionary):
        role_map = pikepdf.Dictionary()
    existing = {str(key) for key in role_map.keys()}
    mapped = []
    for kind in sorted(_used_types(pdf)):
        if kind in STANDARD_TYPES or kind in existing:
            continue
        role_map[kind] = pikepdf.Name(KNOWN_ROLES.get(kind, "/Span"))
        mapped.append(kind)
    if mapped:
        tree.RoleMap = role_map
    return mapped


def wrap_list_bodies(pdf):
    """Every LI child that is not an Lbl or an LBody moves into an LBody.
    The children stay the same objects, so the parent tree still points at
    them. Returns the number of list items changed."""
    changed = 0
    for elem in pdfcheck.walk_tree(pdf):
        if elem.kind != "/LI":
            continue
        kids = elem.obj.get("/K")
        if kids is None:
            continue
        items = list(kids) if isinstance(kids, pikepdf.Array) else [kids]
        labels = []
        loose = []
        for kid in items:
            kind = str(kid.get("/S", "")) if isinstance(kid, pikepdf.Dictionary) else ""
            (labels if kind in ("/Lbl", "/LBody") else loose).append(kid)
        if not loose:
            continue
        body = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.StructElem, S=pikepdf.Name.LBody, P=elem.obj,
            K=pikepdf.Array(loose)))
        page = elem.obj.get("/Pg")
        if page is not None:
            body.Pg = page
        for kid in loose:
            if isinstance(kid, pikepdf.Dictionary) and str(kid.get("/Type", "")) not in ("/MCR", "/OBJR"):
                kid.P = body
        elem.obj.K = pikepdf.Array(labels + [body])
        changed += 1
    return changed


def _is_plain_drawing(xobject):
    """An image, or a form with no marked content of its own."""
    if not isinstance(xobject, pikepdf.Stream):
        return False
    subtype = str(xobject.get("/Subtype", ""))
    if subtype == "/Image":
        return True
    if subtype != "/Form":
        return False
    try:
        data = xobject.read_bytes()
    except Exception:
        return False
    return b"BDC" not in data and b"BMC" not in data and b"BT" not in data


def wrap_artifacts(pdf, page):
    """Wrap drawing outside any marked content on one page as an Artifact.
    Rewrites the page's content, so it is only called on a page the
    checker's scan found something on: reading an instruction back into
    Python costs forty microseconds and Chromium writes one per glyph."""
    instructions = list(pikepdf.parse_content_stream(page))
    resources = page.obj.get("/Resources", pikepdf.Dictionary())
    xobjects = resources.get("/XObject", pikepdf.Dictionary())
    open_tag = pikepdf.ContentStreamInstruction([pikepdf.Name.Artifact], pikepdf.Operator("BMC"))
    close_tag = pikepdf.ContentStreamInstruction([], pikepdf.Operator("EMC"))
    out = []
    depth = 0
    path_at = None
    changed = 0
    for instruction in instructions:
        operator = str(instruction.operator)
        if operator in ("BDC", "BMC"):
            depth += 1
        elif operator == "EMC":
            depth = max(0, depth - 1)
        elif depth == 0:
            if operator in PATH_START and path_at is None:
                path_at = len(out)
            elif operator in PATH_PAINT and path_at is not None:
                out.insert(path_at, open_tag)
                out.append(instruction)
                out.append(close_tag)
                path_at = None
                changed += 1
                continue
            elif operator == "n":
                path_at = None
            elif operator == "sh":
                out.extend((open_tag, instruction, close_tag))
                changed += 1
                continue
            elif operator == "Do":
                xobject = xobjects.get(str(instruction.operands[0]))
                if _is_plain_drawing(xobject):
                    out.extend((open_tag, instruction, close_tag))
                    changed += 1
                    continue
        out.append(instruction)
    if changed:
        page.Contents = pdf.make_stream(pikepdf.unparse_content_stream(out))
    return changed


def finish(pdf):
    """Every repair, on the open file. A file with no tree is left alone:
    the export refuses that file, and it is not for this module to pretend
    otherwise."""
    if "/StructTreeRoot" not in pdf.Root:
        return
    map_roles(pdf)
    wrap_list_bodies(pdf)
    index = pdfcheck.TextIndex(pdf)
    for number, page in enumerate(pdf.pages):
        if index.page(number)["unmarked"]:
            wrap_artifacts(pdf, page)
