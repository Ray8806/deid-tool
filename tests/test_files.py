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
