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
