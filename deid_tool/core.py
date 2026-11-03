"""去識別化核心:規則式偵測 + 可還原的代號對照表。只用標準庫,全程離線。"""
import hashlib
import hmac
import re

# ---------- 驗證器(降低誤判) ----------
_ID_LETTERS = "ABCDEFGHJKLMNPQRSTUVXYWZIO"


def valid_tw_id(s):
    """台灣身分證 / 新式居留證(第二碼 1/2,或居留證 A-D/8/9)檢查碼。"""
    if not re.fullmatch(r"[A-Z][12ABCD89]\d{8}", s):
        return False
    n = _ID_LETTERS.index(s[0]) + 10
    digits = [n // 10, n % 10]
    second = s[1]
    digits.append(int(second) if second.isdigit() else ord(second) - ord("A") + 10)
    # 舊式居留證第二碼為英文字母時取個位數
    digits[-1] %= 10 if not second.isdigit() else 10
    digits += [int(c) for c in s[2:]]
    weights = [1, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1]
    return sum(d * w for d, w in zip(digits, weights)) % 10 == 0


def luhn(s):
    nums = [int(c) for c in re.sub(r"\D", "", s)]
    if len(nums) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(nums)):
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


# ---------- 規則 ----------
# (類型, 正規表達式, 驗證器或 None)。若 regex 有 group(1),只替換該群組。
RULES = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), None),
    ("ID", re.compile(r"(?<![A-Za-z0-9])[A-Z][12ABCD89]\d{8}(?!\d)"), valid_tw_id),
    ("CARD", re.compile(r"(?<!\d)\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}(?!\d)"), luhn),
    ("PHONE", re.compile(r"(?<!\d)09\d{2}[-\s]?\d{3}[-\s]?\d{3}(?!\d)"), None),
    ("PHONE", re.compile(r"(?<!\d)\(?0\d{1,2}\)?[-\s]\d{3,4}[-\s]?\d{3,4}(?!\d)"), None),
    ("IP", re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])"), None),
    ("DATE", re.compile(r"民國\s?\d{2,3}\s?年\s?\d{1,2}\s?月\s?\d{1,2}\s?日"), None),
    ("DATE", re.compile(r"(?<!\d)(?:19|20)\d{2}\s?年\s?\d{1,2}\s?月\s?\d{1,2}\s?日"), None),
    ("DATE", re.compile(r"(?<!\d)(?:19|20)\d{2}[-/.]\d{1,2}[-/.]\d{1,2}(?!\d)"), None),
    ("ADDRESS", re.compile(
        r"(?:[台臺]北|新北|桃園|[台臺]中|[台臺]南|高雄|基隆|新竹|嘉義|苗栗|彰化|南投|雲林|屏東|宜蘭|花蓮|[台臺]東|澎湖|金門|連江)[縣市][一-鿿]{1,4}[鄉鎮市區][一-鿿0-9\-之]{1,30}?號"
        r"(?:之\d+)?(?:\d+樓(?:之\d+)?)?"), None),
    ("MRN", re.compile(r"(?:病歷號碼?|病歷編號|MRN)\s*[:：#]?\s*([A-Za-z0-9\-]{4,})"), None),
    ("NAME", re.compile(
        r"(?:姓名|病患|病人|患者|醫師|醫生|護理師|聯絡人|家屬|監護人)\s*[:：]?\s*([一-鿿]{2,4})"), None),
]

TOKEN_RE = re.compile(r"<([A-Z]+)_(\d+)>")


def _span(m):
    return (m.start(1), m.end(1)) if m.re.groups else (m.start(), m.end())


def scan_text(text, names=(), rules=RULES):
    """回傳不重疊的命中清單 [(start, end, type, value)]。"""
    hits = []
    for typ, rx, check in rules:
        for m in rx.finditer(text):
            s, e = _span(m)
            if check and not check(text[s:e]):
                continue
            hits.append((s, e, typ))
    for name in names:
        for m in re.finditer(re.escape(name), text):
            hits.append((m.start(), m.end(), "NAME"))
    # 重疊時保留較長者
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    out, last_end = [], -1
    for s, e, typ in hits:
        if s >= last_end:
            out.append((s, e, typ, text[s:e]))
            last_end = e
    return out


class Deidentifier:
    """mode: token(可還原)/ mask(遮蔽)/ hash(HMAC 假名化,需 key)。"""

    def __init__(self, mode="token", names=(), key=None, ner=False):
        if mode not in ("token", "mask", "hash"):
            raise ValueError("mode 必須是 token / mask / hash")
        if mode == "hash" and not key:
            raise ValueError("hash 模式需要 --key")
        self.mode, self.names, self.key, self.ner = mode, list(names), key, ner
        self.mapping = {}        # token -> 原值
        self._reverse = {}       # (type, 原值) -> token
        self._counters = {}
        self.stats = {}

    def _replace(self, typ, value):
        self.stats[typ] = self.stats.get(typ, 0) + 1
        if self.mode == "mask":
            return "*" * len(value)
        if self.mode == "hash":
            h = hmac.new(self.key.encode(), value.encode(), hashlib.sha256).hexdigest()[:8]
            return f"<{typ}_{h}>"
        k = (typ, value)
        if k not in self._reverse:
            self._counters[typ] = self._counters.get(typ, 0) + 1
            tok = f"<{typ}_{self._counters[typ]}>"
            self._reverse[k] = tok
            self.mapping[tok] = value
        return self._reverse[k]

    def spans(self, text):
        """回傳 [(start, end, 替換文字)],供需要保留格式的檔案(docx/pptx)使用。"""
        names = self.names
        if self.ner:
            from .ner import ner_names
            names = names + ner_names(text)
        return [(s, e, self._replace(typ, val)) for s, e, typ, val in scan_text(text, names)]

    def anonymize_text(self, text):
        names = self.names
        if self.ner:
            from .ner import ner_names
            names = names + ner_names(text)
        hits = scan_text(text, names)
        parts, pos = [], 0
        for s, e, typ, val in hits:
            parts.append(text[pos:s])
            parts.append(self._replace(typ, val))
            pos = e
        parts.append(text[pos:])
        return "".join(parts)

    def anonymize_cell(self, value, forced_type=None):
        if not value:
            return value
        if forced_type:
            return self._replace(forced_type, value)
        return self.anonymize_text(value)


def restore_text(text, mapping):
    return TOKEN_RE.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)


def restore_spans(text, mapping):
    return [(m.start(), m.end(), mapping[m.group(0)]) for m in TOKEN_RE.finditer(text) if m.group(0) in mapping]
