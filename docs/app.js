const $ = (id) => document.getElementById(id);
const LABELS = { NAME: "姓名", ID: "身分證", PHONE: "電話", EMAIL: "Email", ADDRESS: "地址", DATE: "日期", CARD: "信用卡", IP: "IP", MRN: "病歷號" };
const EXAMPLES = {
  medical: { mode: "token", names: "",
    text: "病人:王小明\n身分證:B101000006  手機:0912-345-678\nEmail:wang@example.com\n住址:台北市大安區和平東路二段106號3樓\n就診日:民國113年5月6日  病歷號:MRN-00123\n主訴:持續頭痛三天。聯絡人 陳大文(家屬)。\n\n(以上皆為虛構範例)" },
  chat: { mode: "token", names: "林雅婷",
    text: "客服:您好,請問怎麼稱呼?\n客戶:我是林雅婷,上週的訂單還沒收到。\n客服:請提供手機號碼,我幫您查詢。\n客戶:0933-111-222,Email 是 yating.lin@example.com。\n客服:查到了,會寄到新北市板橋區文化路一段188號,謝謝林雅婷。\n\n(以上皆為虛構範例)" },
  csv: { mode: "hash", names: "張偉哲\n李美玲\n黃志豪",
    text: "姓名,身分證,電話,生日,地址\n張偉哲,F101000000,0955-123-456,1988-03-21,台中市西屯區文心路三段100號\n李美玲,H101000002,02-2345-6789,1992-11-05,高雄市前鎮區中山二路5號2樓\n黃志豪,K101000004,0966-888-777,1979-07-30,新竹市東區光復路二段1號\n\n(以上皆為虛構範例)" },
  mail: { mode: "mask", names: "",
    text: "王經理您好:\n\n附件為本月請款資料,請匯款至帳戶,並以信用卡 4111 1111 1111 1111 作為備用付款。\n如有問題請聯絡聯絡人 周怡君,電話 (02) 2765-4321,或來信 service@example.com。\n來源 IP:192.168.1.25,簽約日 2024年5月6日。\n\n(以上皆為虛構範例)" },
};
const MODE_HINT = {
  token: "token:把個資換成 <NAME_1> 這類代號,並產生對照表,之後可以還原。",
  mask: "mask:直接用 * 蓋掉,不產生對照表,無法還原。",
  hash: "hash:用你的密鑰把同一個值轉成固定代號,跨檔案可對應同一人,但無法還原。",
};
let mode = "token";
let pending = null;   // 已載入的 Office 檔 {name, ext, buf}
let result = null;    // 處理後檔案 {name, blob}
const OFFICE = { docx: "Word 文件", pptx: "PowerPoint 簡報", xlsx: "Excel 活頁簿" };
const extOf = (n) => (n.split(".").pop() || "").toLowerCase();

function clearPending() {
  pending = null; result = null;
  $("inp").readOnly = false;
}
function saveBlob(name, blob) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob); link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 4000);
}
function say(msg, err) { const s = $("status"); s.textContent = msg; s.classList.toggle("err", !!err); }

function setMode(m) {
  mode = m;
  document.querySelectorAll("#modes .btn").forEach((b) => b.classList.toggle("on", b.dataset.mode === m));
  $("keyrow").classList.toggle("show", m === "hash");
  $("modehint").textContent = MODE_HINT[m];
}
document.querySelectorAll("#modes .btn").forEach((b) => (b.onclick = () => setMode(b.dataset.mode)));

function showStats(stats) {
  const sum = $("sum"); sum.textContent = "";
  for (const [k, n] of Object.entries(stats)) {
    const li = document.createElement("li"), b = document.createElement("b");
    li.textContent = LABELS[k] || k; b.textContent = "×" + n; li.append(b); sum.append(li);
  }
}

async function runOffice(kind) {
  const ext = pending.ext;
  let outName, spansFn, opts = {}, d = null;
  if (kind === "anonymize") {
    const names = $("names").value.split("\n").map((s) => s.trim()).filter(Boolean);
    d = new Deid.Deidentifier(mode, names, $("key").value);
    spansFn = (t) => d.spans(t);
    const cols = new Set($("cols").value.split(/[,,、]/).map((s) => s.trim()).filter(Boolean));
    opts = { cols, forcedFn: (t) => d._replace("NAME", t) };
    outName = "deidentified-" + pending.name;
  } else {
    const mapping = JSON.parse($("map").value || "{}");
    spansFn = (t) => Deid.restoreSpans(t, mapping);
    outName = "restored-" + pending.name;
  }
  say("處理中…");
  const { blob, count } = await OfficeWeb.processOffice(pending.buf, ext, spansFn, opts);
  result = { name: outName, blob };
  saveBlob(outName, blob);
  $("out").value = "已產生 " + outName + "(已自動下載,也可按右上「下載」再存一次)。\n共處理 " + count + " 處。";
  if (d) {
    $("map").value = mode === "token" ? JSON.stringify(d.mapping, null, 2) : "";
    if (mode === "token") $("mapbox").open = true;
    showStats(d.stats);
  } else showStats({});
  say("完成。圖片與圖表內的文字無法偵測,請打開檔案人工檢查。");
}

async function anonymize() {
  if (pending) { try { await runOffice("anonymize"); } catch (e) { say("錯誤:" + e.message, true); } return; }
  try {
    const names = $("names").value.split("\n").map((s) => s.trim()).filter(Boolean);
    const d = new Deid.Deidentifier(mode, names, $("key").value);
    $("out").value = await d.anonymize($("inp").value);
    $("map").value = mode === "token" ? JSON.stringify(d.mapping, null, 2) : "";
    if (mode === "token") $("mapbox").open = true;
    showStats(d.stats);
    say(Object.keys(d.stats).length ? "完成,請檢查輸出。" : "未偵測到個資。");
  } catch (e) { say("錯誤:" + e.message, true); }
}
async function restore() {
  if (pending) { try { await runOffice("restore"); } catch (e) { say("錯誤:" + (e instanceof SyntaxError ? "對照表不是有效的 JSON" : e.message), true); } return; }
  try {
    $("out").value = Deid.restore($("inp").value, JSON.parse($("map").value || "{}"));
    showStats({}); say("已還原。");
  } catch (e) { say("錯誤:對照表不是有效的 JSON", true); }
}
function download(name, text) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
}

$("go").onclick = anonymize;
$("back").onclick = restore;
document.querySelectorAll("#examples .btn").forEach((b) => (b.onclick = async () => {
  clearPending();
  const ex = EXAMPLES[b.dataset.ex];
  $("inp").value = ex.text; $("names").value = ex.names; $("map").value = "";
  $("names").closest("details").open = !!ex.names;
  setMode(ex.mode);
  if (ex.mode === "hash") $("key").value = "demo-key";
  await anonymize();
  const tip = { token: "已套用範例:右側是去識別化結果。把輸出貼回左側,再按「用對照表還原」可還原。",
    mask: "已套用範例:個資已被 * 蓋住,此模式無法還原。注意開頭的「王經理」沒被遮:沒有關鍵字、也不在姓名清單的人名偵測不到,所以輸出一定要人工檢查。",
    hash: "已套用範例(密鑰 demo-key):同一個人在不同檔案會得到相同代號,但無法還原。" }[ex.mode];
  if (!$("status").classList.contains("err")) say(tip);
}));
$("file").onchange = async (e) => {
  const f = e.target.files[0]; e.target.value = ""; if (!f) return;
  clearPending(); $("out").value = ""; showStats({});
  const ext = extOf(f.name);
  if (OFFICE[ext]) {
    pending = { name: f.name, ext, buf: await f.arrayBuffer() };
    $("inp").value = "【已載入 " + OFFICE[ext] + ":" + f.name + "】\n按「去識別化」處理整份檔案,完成後會下載新檔案。\n還原:先把對照表貼到下方,再按「用對照表還原」。";
    $("inp").readOnly = true;
    say("已載入 " + f.name + "。");
  } else { $("inp").value = await f.text(); say("已載入 " + f.name); }
};
$("inp").addEventListener("input", () => { if (pending) clearPending(); });
$("dlOut").onclick = () => (result ? saveBlob(result.name, result.blob) : download("deidentified.txt", $("out").value));
$("dlMap").onclick = () => download("map.json", $("map").value);
$("copy").onclick = async () => { if (result) return say("這是檔案處理結果,請用「下載」。"); try { await navigator.clipboard.writeText($("out").value); say("已複製輸出。"); } catch (e) { say("無法複製,請手動選取。", true); } };
$("clear").onclick = () => { clearPending(); for (const id of ["inp", "out", "map", "key", "names"]) $(id).value = ""; showStats({}); say("已清除。"); };
$("mapfile").onchange = async (e) => {
  const f = e.target.files[0]; e.target.value = ""; if (!f) return;
  $("map").value = await f.text(); $("mapbox").open = true; say("已載入對照表 " + f.name + "。");
};
$("theme").onclick = () => {
  const el = document.documentElement;
  el.dataset.theme = el.dataset.theme === "light" ? "dark" : "light";
  try { localStorage.setItem("deid-theme", el.dataset.theme); } catch (e) {}
};

setMode("token");
