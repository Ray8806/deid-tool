import argparse
import csv
import json
import os
import sys

from .core import Deidentifier, restore_text, scan_text


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


def _load_xlsx():
    try:
        import openpyxl
        return openpyxl
    except ImportError:
        sys.exit("處理 .xlsx 需要 openpyxl:pip install openpyxl")


def process_csv(src, dst, fn, cols):
    with open(src, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        return
    header = rows[0]
    forced = {i: cols[h] for i, h in enumerate(header) if h in cols}
    out = [header] + [[fn(c, forced.get(i)) for i, c in enumerate(r)] for r in rows[1:]]
    with open(dst, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(out)


def process_xlsx(src, dst, fn, cols):
    wb = _load_xlsx().load_workbook(src)
    for ws in wb.worksheets:
        header = [c.value for c in ws[1]] if ws.max_row else []
        forced = {i: cols[h] for i, h in enumerate(header) if h in cols}
        for row in ws.iter_rows(min_row=2):
            for i, cell in enumerate(row):
                if cell.value is not None:
                    cell.value = fn(str(cell.value), forced.get(i))
    wb.save(dst)


def process_file(src, dst, fn, cols):
    ext = os.path.splitext(src)[1].lower()
    if ext == ".csv":
        process_csv(src, dst, fn, cols)
    elif ext in (".xlsx", ".xlsm"):
        process_xlsx(src, dst, fn, cols)
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

    r = sub.add_parser("restore", help="用對照表還原")
    r.add_argument("input")
    r.add_argument("-o", "--output", required=True)
    r.add_argument("--map", required=True)

    s = sub.add_parser("scan", help="只掃描並列出偵測數量(不輸出內容)")
    s.add_argument("input")
    s.add_argument("--names")

    args = p.parse_args(argv)

    if args.cmd == "anonymize":
        if args.mode == "token" and not args.map:
            p.error("token 模式需要 --map 以便日後還原(不想還原請改用 --mode mask/hash)")
        d = Deidentifier(args.mode, _read_names(args.names), args.key)
        process_file(args.input, args.output, lambda t, ft: d.anonymize_cell(t, ft),
                     _parse_columns(args.column))
        if args.map:
            fd = os.open(args.map, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(d.mapping, f, ensure_ascii=False, indent=2)
        print("完成:", json.dumps(d.stats, ensure_ascii=False) or "未偵測到個資")
    elif args.cmd == "restore":
        with open(args.map, encoding="utf-8") as f:
            mapping = json.load(f)
        process_file(args.input, args.output, lambda t, _ft: restore_text(t, mapping), {})
        print("已還原")
    else:
        stats = {}
        names = _read_names(args.names)

        def count(t, _ft):
            for _s, _e, typ, _v in scan_text(t, names):
                stats[typ] = stats.get(typ, 0) + 1
            return t

        import tempfile
        with tempfile.TemporaryDirectory() as td:
            process_file(args.input, os.path.join(td, "x" + os.path.splitext(args.input)[1]), count, {})
        print(json.dumps(stats, ensure_ascii=False) or "未偵測到個資")


if __name__ == "__main__":
    main()
