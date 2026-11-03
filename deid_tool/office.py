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
    _scrub_props(doc.core_properties)
    doc.save(dst)
    return n


def process_pptx(src, dst, spans_fn):
    try:
        import pptx
    except ImportError:
        raise SystemExit("處理 .pptx 需要:pip install python-pptx")
    prs = pptx.Presentation(src)
    n = _process_parts(prs.part.package, A + "p", A + "t", spans_fn)
    _scrub_props(prs.core_properties)
    prs.save(dst)
    return n
