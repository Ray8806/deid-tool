// 與 deid_tool/core.py 規則一致的瀏覽器版核心(也可在 Node 使用)。修改規則時兩邊要同步。
(function (root) {
  const LETTERS = "ABCDEFGHJKLMNPQRSTUVXYWZIO";
  function validTwId(s) {
    if (!/^[A-Z][12ABCD89]\d{8}$/.test(s)) return false;
    const n = LETTERS.indexOf(s[0]) + 10;
    const sec = /\d/.test(s[1]) ? +s[1] : (s.charCodeAt(1) - 65 + 10) % 10;
    const d = [Math.floor(n / 10), n % 10, sec, ...s.slice(2).split("").map(Number)];
    const w = [1, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1];
    return d.reduce((a, x, i) => a + x * w[i], 0) % 10 === 0;
  }
  function luhn(s) {
    const nums = s.replace(/\D/g, "").split("").map(Number);
    if (nums.length < 13) return false;
    let t = 0;
    nums.reverse().forEach((d, i) => { if (i % 2) { d = d > 4 ? d * 2 - 9 : d * 2; } t += d; });
    return t % 10 === 0;
  }
  // [類型, regex, 是否取 group1, 驗證器]
  const RULES = [
    ["EMAIL", /[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}/dg, false, null],
    ["ID", /(?<![A-Za-z0-9])[A-Z][12ABCD89]\d{8}(?!\d)/dg, false, validTwId],
    ["CARD", /(?<!\d)\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}(?!\d)/dg, false, luhn],
    ["PHONE", /(?<![\d+])(?:\+?886[-\s]?9|09)\d{2}[-\s]?\d{3}[-\s]?\d{3}(?!\d)/dg, false, null],
    ["PHONE", /(?<!\d)(?:\(0\d{1,2}\)|0\d{1,2}[-\s])\s?\d{3,4}[-\s]?\d{3,4}(?!\d)(?:\s?(?:#|分機|ext\.?|轉)\s?\d{1,6})?/dg, false, null],
    ["IP", /(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])/dg, false, null],
    ["DATE", /民國\s?\d{2,3}\s?年\s?\d{1,2}\s?月\s?\d{1,2}\s?日/dg, false, null],
    ["DATE", /(?<!\d)(?:19|20)\d{2}\s?年\s?\d{1,2}\s?月\s?\d{1,2}\s?日/dg, false, null],
    ["DATE", /(?<!\d)(?:19|20)\d{2}[-/.]\d{1,2}[-/.]\d{1,2}(?!\d)/dg, false, null],
    ["ADDRESS", /(?<!\d)(?:\d{3}(?:\d{2,3})?\s?)?(?:[台臺]北|新北|桃園|[台臺]中|[台臺]南|高雄|基隆|新竹|嘉義|苗栗|彰化|南投|雲林|屏東|宜蘭|花蓮|[台臺]東|澎湖|金門|連江)[縣市](?:[一-鿿]{1,4}[鄉鎮市區])?[一-鿿0-9\-之]{1,30}?號(?:之\d+)?(?:[,，\s]?\d+(?:樓|[Ff])(?:之\d+)?)?(?:[,，\s]?\d+室)?/dg, false, null],
    ["ADDRESS", /(?<![一-鿿0-9])[一-鿿]{2,3}(?:路|街|大道)(?:[一-鿿0-9]{1,3}段)?(?:\d+巷)?(?:\d+弄)?\d+號(?:之\d+)?(?:[,，\s]?\d+(?:樓|[Ff])(?:之\d+)?)?(?:[,，\s]?\d+室)?/dg, false, null],
    ["MRN", /(?:病歷號碼?|病歷編號|MRN)\s*[:：#]?\s*([A-Za-z0-9\-]{4,})/dg, true, null],
    ["NAME", /(?:姓名|病患|病人|患者|醫師|醫生|護理師|聯絡人|家屬|監護人)\s*[:：]?\s*([一-鿿]{2,4})/dg, true, null],
  ];
  const AUTO = [
    ["PHONE", ["電話", "手機", "傳真", "phone", "mobile", "fax"]],
    ["ADDRESS", ["地址", "住址", "通訊處", "address"]],
    ["EMAIL", ["信箱", "email", "e-mail", "電子郵件"]],
    ["ID", ["身分證", "身份證", "居留證", "護照"]],
    ["DATE", ["生日", "出生"]],
    ["NAME", ["姓名", "名字", "聯絡人", "負責人", "收件人", "收貨人", "承辦人", "申請人", "代表人", "窗口", "病人", "患者"]],
  ];
  function autoColumnType(header) {   // 依欄位標題判斷整欄類型
    const h = String(header || "").toLowerCase();
    for (const [typ, keys] of AUTO) if (keys.some((k) => h.includes(k))) return typ;
    return null;
  }
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  function scanText(text, names = []) {
    const hits = [];
    for (const [typ, rx, grp, check] of RULES) {
      rx.lastIndex = 0;
      for (const m of text.matchAll(rx)) {
        const [s, e] = grp ? m.indices[1] : m.indices[0];
        if (check && !check(text.slice(s, e))) continue;
        hits.push([s, e, typ]);
      }
    }
    for (const item of names) {   // 字串 = 姓名;{text, type} = 手動指定的詞
      const n = typeof item === "string" ? item : item.text, typ = typeof item === "string" ? "NAME" : item.type;
      if (!n) continue;
      for (const m of text.matchAll(new RegExp(esc(n), "g"))) hits.push([m.index, m.index + n.length, typ]);
    }
    hits.sort((a, b) => a[0] - b[0] || (b[1] - b[0]) - (a[1] - a[0]));
    const out = []; let last = -1;
    for (const [s, e, typ] of hits) if (s >= last) { out.push([s, e, typ, text.slice(s, e)]); last = e; }
    return out;
  }

  async function hmac8(key, value) {
    const enc = new TextEncoder();
    const k = await crypto.subtle.importKey("raw", enc.encode(key), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
    const sig = new Uint8Array(await crypto.subtle.sign("HMAC", k, enc.encode(value)));
    return Array.from(sig).map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 8);
  }

  class Deidentifier {
    constructor(mode = "token", names = [], key = "") {
      if (mode === "hash" && !key) throw new Error("hash 模式需要密鑰");
      Object.assign(this, { mode, names, key, mapping: {}, stats: {}, rev: new Map(), counters: {} });
    }
    async _replace(typ, value) {
      this.stats[typ] = (this.stats[typ] || 0) + 1;
      if (this.mode === "mask") return "*".repeat([...value].length);
      if (this.mode === "hash") return `<${typ}_${await hmac8(this.key, value)}>`;
      const k = typ + "\u0000" + value;
      if (!this.rev.has(k)) {
        this.counters[typ] = (this.counters[typ] || 0) + 1;
        const tok = `<${typ}_${this.counters[typ]}>`;
        this.rev.set(k, tok); this.mapping[tok] = value;
      }
      return this.rev.get(k);
    }
    async spans(text) {   // 供 Office 檔案使用:[[start, end, 替換文字], ...]
      const out = [];
      for (const [s, e, typ, val] of scanText(text, this.names)) out.push([s, e, await this._replace(typ, val)]);
      return out;
    }
    async anonymize(text) {
      let out = "", pos = 0;
      for (const [s, e, typ, val] of scanText(text, this.names)) {
        out += text.slice(pos, s) + (await this._replace(typ, val)); pos = e;
      }
      return out + text.slice(pos);
    }
  }
  const restore = (text, mapping) => text.replace(/<([A-Z]+)_(\d+)>/g, (m) => (m in mapping ? mapping[m] : m));

  const restoreSpans = (text, mapping) =>
    [...text.matchAll(/<([A-Z]+)_(\d+)>/g)].filter((m) => m[0] in mapping).map((m) => [m.index, m.index + m[0].length, mapping[m[0]]]);
  const api = { Deidentifier, scanText, restore, restoreSpans, validTwId, luhn, autoColumnType };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.Deid = api;
})(typeof self !== "undefined" ? self : globalThis);
