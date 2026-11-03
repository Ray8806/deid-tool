import os
import shutil
import tempfile
import unittest

from deid_tool import Deidentifier
from deid_tool.core import restore_spans


class FileTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.td)

    def p(self, name):
        return os.path.join(self.td, name)

    def test_docx_split_runs_roundtrip(self):
        try:
            import docx as D
            from deid_tool.office import process_docx
        except ImportError:
            self.skipTest("python-docx 未安裝")
        d = D.Document()
        d.core_properties.author = "王小明"
        para = d.add_paragraph("身分證 A1234")
        para.add_run("56789").bold = True
        para.add_run(",電話 0912-345-678")
        d.save(self.p("in.docx"))
        de = Deidentifier("token")
        process_docx(self.p("in.docx"), self.p("out.docx"), de.spans)
        out = D.Document(self.p("out.docx"))
        self.assertEqual(out.paragraphs[0].text, "身分證 <ID_1>,電話 <PHONE_1>")
        self.assertEqual(out.core_properties.author, "")
        process_docx(self.p("out.docx"), self.p("back.docx"), lambda t: restore_spans(t, de.mapping))
        self.assertEqual(D.Document(self.p("back.docx")).paragraphs[0].text, "身分證 A123456789,電話 0912-345-678")

    def test_pptx(self):
        try:
            import pptx
            from deid_tool.office import process_pptx
        except ImportError:
            self.skipTest("python-pptx 未安裝")
        pr = pptx.Presentation()
        sl = pr.slides.add_slide(pr.slide_layouts[5])
        sl.shapes.title.text = "病人:王小明"
        sl.notes_slide.notes_text_frame.text = "身分證 A123456789"
        pr.save(self.p("in.pptx"))
        process_pptx(self.p("in.pptx"), self.p("out.pptx"), Deidentifier("mask").spans)
        out = pptx.Presentation(self.p("out.pptx")).slides[0]
        self.assertNotIn("王小明", out.shapes.title.text)
        self.assertNotIn("A123456789", out.notes_slide.notes_text_frame.text)

    def test_pdf_text_layer_removed(self):
        try:
            import pymupdf
            from deid_tool.pdf import process_pdf
            from deid_tool.core import scan_text
        except ImportError:
            self.skipTest("pymupdf 未安裝")
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 100), "ID A123456789 tel 0912-345-678", fontsize=12)
        doc.save(self.p("in.pdf"))
        n, _ = process_pdf(self.p("in.pdf"), self.p("out.pdf"),
                           lambda t: [v for _s, _e, _ty, v in scan_text(t)])
        self.assertEqual(n, 2)
        text = pymupdf.open(self.p("out.pdf"))[0].get_text()
        self.assertNotIn("A123456789", text)
        self.assertNotIn("0912", text)


if __name__ == "__main__":
    unittest.main()


class XlsxTests(unittest.TestCase):
    def test_xlsx_roundtrip_and_leaks(self):
        try:
            import openpyxl
            from openpyxl.comments import Comment
            from deid_tool.office import process_xlsx
        except ImportError:
            self.skipTest("openpyxl 未安裝")
        import tempfile, zipfile, os
        td = tempfile.mkdtemp()
        f = lambda n: os.path.join(td, n)
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(["姓名", "身分證", "金額"])
        ws.append(["王小明", "A123456789", 100])
        ws["C3"] = "=C2*2"
        ws["B2"].comment = Comment("聯絡人 陳大文", "王小明")
        wb.properties.creator = "王小明"
        wb.save(f("in.xlsx"))
        d = Deidentifier("token")
        process_xlsx(f("in.xlsx"), f("out.xlsx"), d.spans, {"姓名": "NAME"}, d.anonymize_cell)
        out = openpyxl.load_workbook(f("out.xlsx")).active
        self.assertEqual(out["A2"].value, "<NAME_1>")
        self.assertEqual(out["B2"].value, "<ID_1>")
        self.assertEqual(out["C2"].value, 100)          # 數字保持數字
        self.assertEqual(out["C3"].value, "=C2*2")      # 公式不動
        z = zipfile.ZipFile(f("out.xlsx"))
        blob = b"".join(z.read(n) for n in z.namelist())
        for pii in ("王小明", "A123456789", "陳大文"):
            self.assertNotIn(pii.encode(), blob)        # 檔案任何角落都不殘留
        process_xlsx(f("out.xlsx"), f("back.xlsx"), lambda t: restore_spans(t, d.mapping))
        back = openpyxl.load_workbook(f("back.xlsx")).active
        self.assertEqual((back["A2"].value, back["B2"].value), ("王小明", "A123456789"))


class ThumbnailTest(unittest.TestCase):
    def test_docx_thumbnail_removed_and_still_opens(self):
        try:
            import docx
            from deid_tool.office import process_docx
        except ImportError:
            self.skipTest("python-docx 未安裝")
        import tempfile, zipfile, os
        td = tempfile.mkdtemp()
        docx.Document().save(os.path.join(td, "a.docx"))
        process_docx(os.path.join(td, "a.docx"), os.path.join(td, "b.docx"), Deidentifier("mask").spans)
        names = zipfile.ZipFile(os.path.join(td, "b.docx")).namelist()
        self.assertFalse([n for n in names if "thumbnail" in n])
        docx.Document(os.path.join(td, "b.docx"))      # 仍可正常開啟


class AutoColumnTests(unittest.TestCase):
    def test_auto_columns_incl_numeric_phone(self):
        try:
            import openpyxl
            from deid_tool.office import process_xlsx
        except ImportError:
            self.skipTest("openpyxl 未安裝")
        import tempfile, os, zipfile
        td = tempfile.mkdtemp(); f = lambda n: os.path.join(td, n)
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(["據點", "聯絡人", "連絡電話", "發票地址"])
        ws.append(["甲公司", "陳小華", 912345678, "台北市中山北路五段575號"])
        wb.save(f("a.xlsx"))
        d = Deidentifier("token")
        process_xlsx(f("a.xlsx"), f("b.xlsx"), d.spans, None, d.anonymize_cell, True)
        row = [c.value for c in openpyxl.load_workbook(f("b.xlsx")).active[2]]
        self.assertEqual(row, ["甲公司", "<NAME_1>", "<PHONE_1>", "<ADDRESS_1>"])
        z = zipfile.ZipFile(f("b.xlsx"))
        blob = b"".join(z.read(n) for n in z.namelist())
        for pii in ("陳小華", "912345678", "中山北路"):
            self.assertNotIn(pii.encode(), blob)
        process_xlsx(f("a.xlsx"), f("c.xlsx"), d.spans, None, d.anonymize_cell, False)   # 關閉自動
        self.assertEqual(openpyxl.load_workbook(f("c.xlsx")).active["B2"].value, "陳小華")
