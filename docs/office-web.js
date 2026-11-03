// 瀏覽器內處理 Word / PowerPoint / Excel(OOXML):逐段落替換並保留格式,清除作者與縮圖。
// 與 deid_tool/office.py 的邏輯一致。需先載入 jszip.min.js。
(function (root) {
  const NS = {
    w: "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    a: "http://schemas.openxmlformats.org/drawingml/2006/main",
    x: "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
  };
  const XML_NS = "http://www.w3.org/XML/1998/namespace";
  const MIME = {
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  };
  const PROPS = new Set(["creator", "title", "subject", "description", "lastModifiedBy", "keywords", "Company", "Manager"]);

  const all = (el, ns, name) => Array.from(el.getElementsByTagNameNS(ns, name));
  const hasAncestor = (el, ns, name) => {
    for (let q = el.parentNode; q && q.nodeType === 1; q = q.parentNode) if (q.namespaceURI === ns && q.localName === name) return true;
    return false;
  };
  function ownTexts(unit, ns, tName, uName) {
    return all(unit, ns, tName).filter((t) => {
      let q = t.parentNode;
      while (q && !(q.namespaceURI === ns && q.localName === uName)) q = q.parentNode;
      return q === unit;
    });
  }
  function rewrite(nodes, spans) {
    let pos = 0;
    const ranges = nodes.map((n) => { const l = (n.textContent || "").length; const r = [pos, pos + l]; pos += l; return r; });
    const next = nodes.map((n) => n.textContent || "");
    for (const [s, e, repl] of [...spans].sort((p, q) => q[0] - p[0])) {
      let first = true;
      ranges.forEach(([a, b], i) => {
        if (b <= s || a >= e) return;
        const lo = Math.max(s, a) - a, hi = Math.min(e, b) - a;
        next[i] = next[i].slice(0, lo) + (first ? repl : "") + next[i].slice(hi);
        first = false;
      });
    }
    nodes.forEach((n, i) => {
      if (next[i] !== (n.textContent || "")) { n.textContent = next[i]; n.setAttributeNS(XML_NS, "xml:space", "preserve"); }
    });
  }
  async function units(doc, ns, uName, tName, spansFn, skipRPh) {
    let count = 0;
    for (const u of all(doc.documentElement, ns, uName)) {
      let nodes = ownTexts(u, ns, tName, uName);
      if (skipRPh) nodes = nodes.filter((t) => !hasAncestor(t, ns, "rPh"));
      const text = nodes.map((n) => n.textContent || "").join("");
      if (!text) continue;
      const spans = await spansFn(text);
      if (spans.length) { rewrite(nodes, spans); count += spans.length; }
    }
    return count;
  }

  const parse = (xml) => {
    const d = new DOMParser().parseFromString(xml, "application/xml");
    if (d.getElementsByTagName("parsererror").length) throw new Error("無法解析檔案內容");
    return d;
  };
  const ser = (doc) => {
    const o = new XMLSerializer().serializeToString(doc);
    return o.startsWith("<?xml") ? o : '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + o;
  };
  const colOf = (ref) => ref.match(/^[A-Z]+/)[0];
  function cellText(c, shared) {
    const t = c.getAttribute("t");
    const v = all(c, NS.x, "v")[0];
    if (t === "s") return v ? shared[+v.textContent] : null;
    if (t === "inlineStr") return all(c, NS.x, "t").map((n) => n.textContent || "").join("");
    if (t === "str") return v ? v.textContent : null;
    return null;
  }
  // 標題列(第一列)欄名在 cols 內的整欄,文字儲存格整格換成 forcedFn(原文) 的結果
  async function forceColumns(zip, names, cols, forcedFn, auto, report) {
    const sstName = "xl/sharedStrings.xml";
    let sstDoc = null, shared = [];
    if (zip.file(sstName)) {
      sstDoc = parse(await zip.file(sstName).async("string"));
      shared = all(sstDoc.documentElement, NS.x, "si").map((si) =>
        all(si, NS.x, "t").filter((t) => !hasAncestor(t, NS.x, "rPh")).map((t) => t.textContent || "").join(""));
    }
    const sheets = names.filter((n) => /^xl\/worksheets\/sheet\d+\.xml$/.test(n));
    const docs = {}, touched = new Set();
    let count = 0;
    for (const n of sheets) {
      const doc = parse(await zip.file(n).async("string"));
      docs[n] = doc;
      const rows = all(doc.documentElement, NS.x, "row");
      if (!rows.length) continue;
      const forced = new Map();
      for (const c of all(rows[0], NS.x, "c")) {
        const r = c.getAttribute("r"); if (!r) continue;
        const h = cellText(c, shared);
        const typ = (cols && cols.get(h)) || (auto ? root.Deid.autoColumnType(h) : null);
        if (typ) { forced.set(colOf(r), typ); report.push([h, typ]); }
      }
      for (const row of rows.slice(1)) {
        for (const c of all(row, NS.x, "c")) {
          const r = c.getAttribute("r");
          if (!r || !forced.has(colOf(r))) continue;
          let text = cellText(c, shared);
          if (text === null && [null, "n"].includes(c.getAttribute("t")) && !all(c, NS.x, "f").length) {
            const v = all(c, NS.x, "v")[0]; text = v ? v.textContent : null;   // 數字儲存格也處理
          }
          if (!text) continue;
          if (c.getAttribute("t") === "s") touched.add(+all(c, NS.x, "v")[0].textContent);
          const nw = await forcedFn(text, forced.get(colOf(r)));
          while (c.firstChild) c.removeChild(c.firstChild);
          c.setAttribute("t", "inlineStr");
          const is = doc.createElementNS(NS.x, "is"), t = doc.createElementNS(NS.x, "t");
          t.textContent = nw; is.appendChild(t); c.appendChild(is);
          count++;
        }
      }
    }
    const still = new Set();
    for (const n of sheets) for (const c of all(docs[n].documentElement, NS.x, "c")) {
      if (c.getAttribute("t") === "s") { const v = all(c, NS.x, "v")[0]; if (v) still.add(+v.textContent); }
    }
    const orphan = new Set([...touched].filter((i) => !still.has(i)));   // 不再被引用:清空,避免原值殘留
    if (sstDoc && orphan.size) {
      all(sstDoc.documentElement, NS.x, "si").forEach((si, i) => {
        if (!orphan.has(i)) return;
        while (si.firstChild) si.removeChild(si.firstChild);
        const t = sstDoc.createElementNS(NS.x, "t"); t.textContent = ""; si.appendChild(t);
      });
      zip.file(sstName, ser(sstDoc));
    }
    for (const n of sheets) zip.file(n, ser(docs[n]));
    return count;
  }

  async function processOffice(buf, ext, spansFn, opts = {}) {
    ext = ext.toLowerCase().replace(".", "");
    if (!MIME[ext]) throw new Error("不支援的檔案類型:" + ext);
    const zip = await JSZip.loadAsync(buf);
    const names = Object.keys(zip.files).filter((n) => !zip.files[n].dir);
    let count = 0;
    if (ext === "xlsx" && opts.forcedFn && ((opts.cols && opts.cols.size) || opts.auto)) {
      count += await forceColumns(zip, names, opts.cols, opts.forcedFn, !!opts.auto, opts.report || []);
    }
    for (const name of names) {
      let kind = null;
      if (ext === "docx" && /^word\/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml$/.test(name)) kind = "w";
      else if (ext === "pptx" && /^ppt\/(slides\/slide\d+|notesSlides\/notesSlide\d+)\.xml$/.test(name)) kind = "a";
      else if (ext === "xlsx" && /^xl\/(sharedStrings|comments\d*|comments\/[^/]+|worksheets\/sheet\d+)\.xml$/.test(name)) kind = "x";
      else if (ext === "xlsx" && /^xl\/drawings\/drawing\d+\.xml$/.test(name)) kind = "a";
      else if (name === "docProps/core.xml" || name === "docProps/app.xml") kind = "props";
      else if (name === "ppt/commentAuthors.xml") kind = "pptauth";
      if (!kind) continue;

      const xml = await zip.file(name).async("string");
      const doc = new DOMParser().parseFromString(xml, "application/xml");
      if (doc.getElementsByTagName("parsererror").length) throw new Error("無法解析 " + name);

      if (kind === "w") {
        count += await units(doc, NS.w, "p", "t", spansFn, false);
        for (const el of doc.getElementsByTagNameNS(NS.w, "*")) {   // 註解/修訂作者
          if (["comment", "ins", "del", "moveFrom", "moveTo"].includes(el.localName)) {
            if (el.hasAttributeNS(NS.w, "author")) el.setAttributeNS(NS.w, "w:author", "作者");
            if (el.hasAttributeNS(NS.w, "initials")) el.setAttributeNS(NS.w, "w:initials", "");
          }
        }
      } else if (kind === "a") {
        count += await units(doc, NS.a, "p", "t", spansFn, false);
      } else if (kind === "x") {
        for (const u of ["si", "is", "text"]) count += await units(doc, NS.x, u, "t", spansFn, true);
        for (const a of all(doc.documentElement, NS.x, "author")) a.textContent = "作者";
      } else if (kind === "props") {
        for (const el of doc.getElementsByTagName("*")) if (PROPS.has(el.localName)) el.textContent = "";
      } else if (kind === "pptauth") {
        for (const el of doc.getElementsByTagName("*")) if (el.localName === "cmAuthor") { el.setAttribute("name", "作者"); el.setAttribute("initials", ""); }
      }
      let out = new XMLSerializer().serializeToString(doc);
      if (!out.startsWith("<?xml")) out = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + out;
      zip.file(name, out);
    }
    // 移除預覽縮圖(會顯示第一頁原始內容)與其關聯
    for (const n of names) if (n.startsWith("docProps/thumbnail")) zip.remove(n);
    if (zip.file("_rels/.rels")) {
      const rels = await zip.file("_rels/.rels").async("string");
      zip.file("_rels/.rels", rels.replace(/<Relationship\b[^>]*thumbnail[^>]*\/>/g, ""));
    }
    const blob = await zip.generateAsync({ type: "blob", mimeType: MIME[ext], compression: "DEFLATE" });
    return { blob, count };
  }
  root.OfficeWeb = { processOffice, MIME };
})(typeof self !== "undefined" ? self : globalThis);
