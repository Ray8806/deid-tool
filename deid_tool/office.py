"""Word / PowerPoint:逐段落處理,保留原有格式。需 pip install python-docx python-pptx。"""
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def _own_texts(p, p_tag, t_tag):
    """屬於段落 p 本身的文字節點(排除巢狀文字方塊內的段落)。"""
    out = []
    for t in p.iter(t_tag):
        q = t.getparent()
        while q is not None and q.tag != p_tag:
            q = q.getparent()
        if q is p:
            out.append(t)
    return out


def _rewrite(nodes, spans):
    """依 spans 改寫跨多個文字節點的內容:替換文字放進第一個涵蓋的節點(沿用其格式)。"""
    pos, ranges = 0, []
    for n in nodes:
        t = n.text or ""
        ranges.append((pos, pos + len(t)))
        pos += len(t)
    new = [n.text or "" for n in nodes]
    for s, e, repl in sorted(spans, reverse=True):
        first = True
        for i, (a, b) in enumerate(ranges):
            if b <= s or a >= e:
                continue
            lo, hi = max(s, a) - a, min(e, b) - a
            new[i] = new[i][:lo] + (repl if first else "") + new[i][hi:]
            first = False
    for n, t in zip(nodes, new):
        if t != (n.text or ""):
            n.text = t
            n.set(XML_SPACE, "preserve")


def _process_parts(package, p_tag, t_tag, spans_fn):
    count = 0
    for part in package.iter_parts():
        root = getattr(part, "_element", None)
        if root is None:
            continue
        for p in list(root.iter(p_tag)):
            nodes = _own_texts(p, p_tag, t_tag)
            text = "".join(n.text or "" for n in nodes)
            if not text:
                continue
            spans = spans_fn(text)
            if spans:
                _rewrite(nodes, spans)
                count += len(spans)
    return count


def _scrub_authors(package):
    """Word 註解/追蹤修訂的 w:author、w:initials,以及 PPT 註解作者清單。"""
    for part in package.iter_parts():
        root = getattr(part, "_element", None)
        if root is None:
            continue
        for el in root.iter():
            for attr in ("author", "initials", "name"):
                key = W + attr
                if el.tag in (W + "comment", W + "ins", W + "del", W + "moveFrom", W + "moveTo") \
                        and key in el.attrib and attr != "name":
                    el.set(key, "作者" if attr == "author" else "")
            if el.tag.endswith("}cmAuthor"):
                el.set("name", "作者")
                el.set("initials", "")


def strip_thumbnail(path):
    """移除檔案內嵌的預覽縮圖(會顯示第一頁原始內容)及其關聯。"""
    import os
    import re
    import tempfile
    import zipfile
    fd, tmp = tempfile.mkstemp(suffix=os.path.splitext(path)[1])
    os.close(fd)
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w") as zout:
        for info in zin.infolist():
            if info.filename.startswith("docProps/thumbnail"):
                continue
            data = zin.read(info.filename)
            if info.filename == "_rels/.rels":
                data = re.sub(rb"<Relationship\b[^>]*thumbnail[^>]*/>", b"", data)
            zout.writestr(info, data, compress_type=info.compress_type)
    os.replace(tmp, path)


def _scrub_props(cp):
    for f in ("author", "last_modified_by", "title", "subject", "comments", "keywords", "category"):
        try:
            setattr(cp, f, "")
        except Exception:
            pass


def process_docx(src, dst, spans_fn):
    try:
        import docx
    except ImportError:
        raise SystemExit("處理 .docx 需要:pip install python-docx")
    doc = docx.Document(src)
    n = _process_parts(doc.part.package, W + "p", W + "t", spans_fn)
    _scrub_authors(doc.part.package)
    _scrub_props(doc.core_properties)
    doc.save(dst)
    strip_thumbnail(dst)
    return n


def process_pptx(src, dst, spans_fn):
    try:
        import pptx
    except ImportError:
        raise SystemExit("處理 .pptx 需要:pip install python-pptx")
    prs = pptx.Presentation(src)
    n = _process_parts(prs.part.package, A + "p", A + "t", spans_fn)
    _scrub_authors(prs.part.package)
    _scrub_props(prs.core_properties)
    prs.save(dst)
    strip_thumbnail(dst)
    return n


# ---------- Excel(直接改 xlsx 內部 XML,不經 openpyxl:格式/公式/圖片/圖表都保持原樣) ----------
X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_PROPS = {
    "{http://purl.org/dc/elements/1.1/}creator", "{http://purl.org/dc/elements/1.1/}title",
    "{http://purl.org/dc/elements/1.1/}subject", "{http://purl.org/dc/elements/1.1/}description",
    "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}lastModifiedBy",
    "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}keywords",
    "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}Company",
    "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}Manager",
}


def _x_units(root, spans_fn):
    """共享字串 <si>、行內字串 <is>、註解 <text>:每個視為一個『段落』(忽略注音 rPh)。"""
    count = 0
    for tag in (X + "si", X + "is", X + "text"):
        for unit in list(root.iter(tag)):
            nodes = [t for t in unit.iter(X + "t")
                     if not any(a.tag == X + "rPh" for a in t.iterancestors())]
            text = "".join(n.text or "" for n in nodes)
            if text:
                spans = spans_fn(text)
                if spans:
                    _rewrite(nodes, spans)
                    count += len(spans)
    return count


def _drawing_paras(root, spans_fn):
    count = 0
    for p in list(root.iter(A + "p")):
        nodes = _own_texts(p, A + "p", A + "t")
        text = "".join(n.text or "" for n in nodes)
        if text:
            spans = spans_fn(text)
            if spans:
                _rewrite(nodes, spans)
                count += len(spans)
    return count


def _col(ref):
    import re
    return re.match(r"[A-Z]+", ref).group(0)


def _cell_text(c, shared):
    t = c.get("t")
    if t == "s":
        v = c.find(X + "v")
        return shared[int(v.text)] if v is not None and v.text else None
    if t == "inlineStr":
        return "".join(n.text or "" for n in c.iter(X + "t"))
    if t == "str":
        v = c.find(X + "v")
        return v.text if v is not None else None
    return None


def _force_columns(sheet_root, shared, cols, forced_fn, auto=True, report=None):
    """標題列(第一列)欄名在 cols 內的整欄,文字儲存格整格替換成對應類型代號。回傳 (處數, 被替換前引用的共享字串索引集合)。"""
    rows = list(sheet_root.iter(X + "row"))
    if not rows:
        return 0, set()
    forced = {}
    from .core import auto_column_type
    for c in rows[0].iter(X + "c"):
        txt = _cell_text(c, shared)
        typ = cols.get(txt) or (auto_column_type(txt) if auto else None)
        if typ and c.get("r"):
            forced[_col(c.get("r"))] = typ
            if report is not None:
                report.append((txt, typ))
    n, touched = 0, set()
    for row in rows[1:]:
        for c in row.iter(X + "c"):
            typ = forced.get(_col(c.get("r"))) if c.get("r") else None
            if not typ:
                continue
            text = _cell_text(c, shared)
            if text is None and c.get("t") in (None, "n") and c.find(X + "f") is None:
                v = c.find(X + "v")      # 數字儲存格(例如以數字儲存的電話):整格也要處理
                text = v.text if v is not None else None
            if not text:
                continue
            if c.get("t") == "s":
                touched.add(int(c.find(X + "v").text))
            new = forced_fn(text, typ)
            for ch in list(c):
                c.remove(ch)
            c.set("t", "inlineStr")
            from lxml import etree
            t = etree.SubElement(etree.SubElement(c, X + "is"), X + "t")
            t.text = new
            n += 1
    return n, touched


def process_xlsx(src, dst, spans_fn, cols=None, forced_fn=None, auto=True, report=None):
    """cols: {欄名: 類型};該欄整欄替換。其餘儲存格逐字串依規則替換。"""
    import re
    import zipfile
    from lxml import etree
    count = 0
    with zipfile.ZipFile(src) as zin:
        infos = zin.infolist()
        raw = {i.filename: zin.read(i.filename) for i in infos}
    trees = {}
    for name, data in raw.items():
        if re.fullmatch(r"xl/(sharedStrings|comments\d*|comments/[^/]+|worksheets/sheet\d+)\.xml", name) \
                or re.fullmatch(r"xl/drawings/drawing\d+\.xml", name) \
                or name in ("docProps/core.xml", "docProps/app.xml"):
            trees[name] = etree.fromstring(data)
    shared = []
    sst = trees.get("xl/sharedStrings.xml")
    if sst is not None:
        shared = ["".join(t.text or "" for t in si.iter(X + "t")
                          if not any(a.tag == X + "rPh" for a in t.iterancestors()))
                  for si in sst.iter(X + "si")]
    if (cols or auto) and forced_fn:
        touched = set()
        for name, root in trees.items():
            if name.startswith("xl/worksheets/"):
                n, tch = _force_columns(root, shared, cols or {}, forced_fn, auto, report)
                count += n
                touched |= tch
        if sst is not None and touched:
            still = {int(c.find(X + "v").text) for name, root in trees.items()
                     if name.startswith("xl/worksheets/")
                     for c in root.iter(X + "c") if c.get("t") == "s" and c.find(X + "v") is not None}
            orphan = touched - still   # 已不再被引用的共享字串:清空,避免原值殘留在檔案裡
            for idx, si in enumerate(sst.iter(X + "si")):
                if idx in orphan:
                    for ch in list(si):
                        si.remove(ch)
                    etree.SubElement(si, X + "t").text = ""
    for name, root in trees.items():
        if name.startswith("docProps/"):
            for el in root.iter():
                if el.tag in _PROPS:
                    el.text = ""
        elif name.startswith("xl/drawings/"):
            count += _drawing_paras(root, spans_fn)
        else:
            for a in root.iter(X + "author"):   # 註解作者(通常是本人姓名)
                a.text = "作者"
            count += _x_units(root, spans_fn)
    with zipfile.ZipFile(dst, "w") as zout:
        for info in infos:
            data = raw[info.filename]
            if info.filename in trees:
                data = etree.tostring(trees[info.filename], xml_declaration=True, encoding="UTF-8", standalone=True)
            zout.writestr(info, data, compress_type=info.compress_type)
    strip_thumbnail(dst)
    return count
