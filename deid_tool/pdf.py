"""PDF:找出個資後做真正的塗黑(移除底層文字,而非只蓋黑框)。需 pip install pymupdf。
僅適用有文字層的 PDF;掃描檔(圖片)需先 OCR,否則無法偵測。"""


def process_pdf(src, dst, detect_fn):
    """detect_fn(text) -> [要塗黑的字串...]。回傳 (塗黑處數, 無文字層的頁數)。"""
    try:
        import pymupdf
    except ImportError:
        raise SystemExit("處理 .pdf 需要:pip install pymupdf")
    doc = pymupdf.open(src)
    count = blank = 0
    for page in doc:
        text = page.get_text()
        if not text.strip():
            if page.get_images():
                blank += 1
            continue
        flat = text.replace("\n", "")
        targets = set(detect_fn(text)) | set(detect_fn(flat))
        for t in sorted(targets, key=len, reverse=True):
            for rect in page.search_for(t):
                page.add_redact_annot(rect, fill=(0, 0, 0))
                count += 1
        page.apply_redactions()
    doc.set_metadata({})
    doc.save(dst, garbage=4, deflate=True)
    doc.close()
    return count, blank
