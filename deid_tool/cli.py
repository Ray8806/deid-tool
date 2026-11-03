import argparse
import csv
import json
import os
import sys

from .core import Deidentifier, auto_column_type, restore_spans, restore_text, scan_text


def _read_names(path):
    if not path:
        return []
    with open(path, encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]


def _parse_columns(items):
    out = {}
    for it in items or []:
        col, _, typ = it.partition("=")
        out[col] = (typ or "NAME").upper()
    return out


def process_csv(src, dst, fn, cols):
    with open(src, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        return
    header = rows[0]
    forced = {}
    for i, h in enumerate(header):
        typ = cols.get(h) or (auto_column_type(h) if AUTO_COLUMNS[0] else None)
        if typ:
            forced[i] = typ
    out = [header] + [[fn(c, forced.get(i)) for i, c in enumerate(r)] for r in rows[1:]]
    with open(dst, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(out)


AUTO_COLUMNS = [True]
pdf_hits = []


def process_file(src, dst, fn, cols, spans_fn=None, detect_fn=None, quiet=False):
    ext = os.path.splitext(src)[1].lower()
    if ext in (".docx", ".pptx", ".xlsx", ".xlsm"):
        if spans_fn is None:
            sys.exit(f"不支援此操作的檔案類型:{ext}")
        from . import office
        fns = {".docx": office.process_docx, ".pptx": office.process_pptx,
               ".xlsx": office.process_xlsx, ".xlsm": office.process_xlsx}
        report = []
        n = (fns[ext](src, dst, spans_fn, cols, fn, AUTO_COLUMNS[0], report) if ext in (".xlsx", ".xlsm")
             else fns[ext](src, dst, spans_fn))
        if report and not quiet:
            print("整欄處理的欄位:", "、".join(f"{h}→{t}" for h, t in dict.fromkeys(report)))
        if not quiet:
            print(f"已處理 {n} 處(圖片、圖表內的文字無法偵測,請人工檢查)")
    elif ext == ".pdf":
        if detect_fn is None:
            sys.exit("PDF 只支援 anonymize / scan(塗黑為不可逆,無法還原)")
        from .pdf import process_pdf
        n, blank = process_pdf(src, dst, detect_fn)
        if not quiet:
            print(f"PDF 塗黑 {n} 處(不論 --mode,PDF 一律塗黑且不可還原)")
        pdf_hits.append(n)
        if blank:
            print(f"警告:{blank} 頁沒有文字層(掃描圖片),無法偵測,請先 OCR 或人工處理")
    elif ext == ".csv":
        process_csv(src, dst, fn, cols)
    else:
        with open(src, encoding="utf-8") as f:
            text = f.read()
        with open(dst, "w", encoding="utf-8") as f:
            f.write(fn(text, None))


def main(argv=None):
    p = argparse.ArgumentParser(prog="deid", description="離線去識別化工具(文字 / CSV / Excel)")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("anonymize", help="去識別化")
    a.add_argument("input")
    a.add_argument("-o", "--output", required=True)
    a.add_argument("--mode", choices=["token", "mask", "hash"], default="token")
    a.add_argument("--map", help="token 模式:輸出對照表 JSON(含原始個資,請妥善保管)")
    a.add_argument("--names", help="已知姓名清單檔(一行一個)")
    a.add_argument("--column", action="append", metavar="欄名=類型",
                   help="整欄視為某類型,如 姓名=NAME(CSV/Excel,可重複)")
    a.add_argument("--key", help="hash 模式的密鑰")
    a.add_argument("--no-auto-columns", action="store_true",
                   help="關閉依欄名自動判斷(預設會把「聯絡人/電話/地址/Email/生日…」等欄整欄處理)")
    a.add_argument("--ner", action="store_true", help="用 CKIP NER 偵測人名(需 ckip-transformers)")

    r = sub.add_parser("restore", help="用對照表還原")
    r.add_argument("input")
    r.add_argument("-o", "--output", required=True)
    r.add_argument("--map", required=True)

    s = sub.add_parser("scan", help="只掃描並列出偵測數量(不輸出內容)")
    s.add_argument("input")
    s.add_argument("--names")

    g = sub.add_parser("gui", help="啟動本機網頁介面")
    g.add_argument("--port", type=int, default=8765)
    g.add_argument("--ner", action="store_true")
    g.add_argument("--no-browser", action="store_true")

    args = p.parse_args(argv)

    if args.cmd == "gui":
        from .gui import serve
        return serve(args.port, args.ner, not args.no_browser)

    if args.cmd == "anonymize":
        if args.mode == "token" and not args.map:
            p.error("token 模式需要 --map 以便日後還原(不想還原請改用 --mode mask/hash)")
        AUTO_COLUMNS[0] = not args.no_auto_columns
        d = Deidentifier(args.mode, _read_names(args.names), args.key, ner=args.ner)
        process_file(args.input, args.output, lambda t, ft: d.anonymize_cell(t, ft),
                     _parse_columns(args.column), spans_fn=d.spans,
                     detect_fn=lambda t: [v for _s, _e, _ty, v in scan_text(t, d.names)])
        if args.map:
            fd = os.open(args.map, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(d.mapping, f, ensure_ascii=False, indent=2)
        if not args.input.lower().endswith(".pdf"):
            print("完成:", json.dumps(d.stats, ensure_ascii=False) if d.stats else "未偵測到個資")
    elif args.cmd == "restore":
        with open(args.map, encoding="utf-8") as f:
            mapping = json.load(f)
        process_file(args.input, args.output, lambda t, _ft: restore_text(t, mapping), {},
                     spans_fn=lambda t: restore_spans(t, mapping))
        print("已還原")
    else:
        stats = {}
        names = _read_names(args.names)

        def count(t, _ft):
            for _s, _e, typ, _v in scan_text(t, names):
                stats[typ] = stats.get(typ, 0) + 1
            return t

        import tempfile
        def count_spans(t):
            count(t, None)
            return []

        with tempfile.TemporaryDirectory() as td:
            process_file(args.input, os.path.join(td, "x" + os.path.splitext(args.input)[1]), count, {},
                         spans_fn=count_spans, quiet=True,
                         detect_fn=lambda t: [v for _s, _e, _ty, v in scan_text(t, names)])
        if pdf_hits:
            print(f"PDF 共偵測到 {pdf_hits[-1]} 處個資(PDF 不分類統計)")
        else:
            print(json.dumps(stats, ensure_ascii=False) if stats else "未偵測到個資")


if __name__ == "__main__":
    main()
