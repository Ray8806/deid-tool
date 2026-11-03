import unittest

from deid_tool import Deidentifier
from deid_tool.core import restore_text, valid_tw_id

SAMPLE = ("姓名:王小明,身分證 A123456789,手機 0912-345-678,"
          "Email wang@example.com,住 台北市大安區和平東路二段106號3樓,"
          "就診日 民國113年5月6日,病歷號 MRN-00123。再聯絡 A123456789。")


class T(unittest.TestCase):
    def test_id_checksum(self):
        self.assertTrue(valid_tw_id("A123456789"))
        self.assertFalse(valid_tw_id("A123456780"))

    def test_roundtrip(self):
        d = Deidentifier("token")
        out = d.anonymize_text(SAMPLE)
        for raw in ("王小明", "A123456789", "0912-345-678", "wang@example.com",
                    "和平東路", "民國113年5月6日", "00123"):
            self.assertNotIn(raw, out)
        self.assertEqual(out.count("<ID_1>"), 2)  # 同值同代號
        self.assertEqual(restore_text(out, d.mapping), SAMPLE)

    def test_bad_id_not_masked(self):
        d = Deidentifier("token")
        self.assertIn("A123456780", d.anonymize_text("編號 A123456780"))

    def test_mask_and_hash(self):
        self.assertNotIn("A123456789", Deidentifier("mask").anonymize_text(SAMPLE))
        h = Deidentifier("hash", key="k")
        self.assertEqual(h.anonymize_text("A123456789"), h.anonymize_text("A123456789"))

    def test_names_list(self):
        d = Deidentifier("token", names=["陳大文"])
        self.assertNotIn("陳大文", d.anonymize_text("陳大文今天回診"))


if __name__ == "__main__":
    unittest.main()


class GuiTest(unittest.TestCase):
    def test_api_roundtrip(self):
        import json, threading, urllib.request
        from http.server import ThreadingHTTPServer
        from deid_tool.gui import make_handler
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(False))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_port}"

        def post(path, body):
            r = urllib.request.urlopen(urllib.request.Request(base + path, json.dumps(body).encode()))
            return json.load(r)

        a = post("/api/anonymize", {"text": SAMPLE, "mode": "token"})
        self.assertNotIn("A123456789", a["text"])
        b = post("/api/restore", {"text": a["text"], "mapping": a["mapping"]})
        self.assertEqual(b["text"], SAMPLE)
        req = urllib.request.Request(base + "/", headers={"Host": "evil.com"})
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(req)
        srv.shutdown()


class AddrTest(unittest.TestCase):
    def test_floor_included(self):
        out = Deidentifier("token").anonymize_text("住台北市大安區和平東路二段106號3樓之2。")
        self.assertEqual(out, "住<ADDRESS_1>。")


class RealWorldFormats(unittest.TestCase):
    def anon(self, t):
        return Deidentifier("token").anonymize_text(t)

    def test_address_without_district_and_with_floor(self):
        for a in ("台北市中山北路五段575號", "台北市民生東路三段129號", "台北市士林區中山北路五段575號3樓",
                  "106台北市大安區和平東路二段106號5F", "高雄市前鎮區中山二路5號2樓"):
            self.assertEqual(self.anon(a), "<ADDRESS_1>", a)

    def test_phone_formats(self):
        for ph in ("(02)2716-5666", "02-2716-5666", "(02) 2716-5666 #905", "02-27165666 分機123",
                   "+886-912-345-678", "0912345678", "0912-345-678"):
            self.assertEqual(self.anon(ph), "<PHONE_1>", ph)

    def test_company_tax_id_untouched(self):
        self.assertEqual(self.anon("統一編號 12345678"), "統一編號 12345678")

    def test_auto_column_type(self):
        from deid_tool.core import auto_column_type as t
        self.assertEqual([t(h) for h in ("聯絡人", "連絡電話", "發票地址", "Email", "出生日", "聯絡人電話", "據點抬頭", "統一編號")],
                         ["NAME", "PHONE", "ADDRESS", "EMAIL", "DATE", "PHONE", None, None])


class ManualTerms(unittest.TestCase):
    def test_terms_with_type(self):
        d = Deidentifier("token", names=["陳大文", ("昨天的會議室A", "OTHER")])
        out = d.anonymize_text("陳大文說昨天的會議室A很吵")
        self.assertEqual(out, "<NAME_1>說<OTHER_1>很吵")
