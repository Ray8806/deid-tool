const $ = (id) => document.getElementById(id);
const LABELS = { NAME: "姓名", ID: "身分證", PHONE: "電話", EMAIL: "Email", ADDRESS: "地址", DATE: "日期", CARD: "信用卡", IP: "IP", MRN: "病歷號" };
const SAMPLE = "病人:王小明,身分證 A123456789,手機 0912-345-678,\nEmail wang@example.com,住台北市大安區和平東路二段106號3樓。\n就診日 民國113年5月6日,病歷號 MRN-00123,聯絡人 陳大文。\n(以上皆為虛構範例)";
let mode = "token";

function say(msg, err) { const s = $("status"); s.textContent = msg; s.classList.toggle("err", !!err); }

function setMode(m) {
  mode = m;
  document.querySelectorAll("#modes .btn").forEach((b) => b.classList.toggle("on", b.dataset.mode === m));
  $("keyrow").classList.toggle("show", m === "hash");
}
document.querySelectorAll("#modes .btn").forEach((b) => (b.onclick = () => setMode(b.dataset.mode)));

function showStats(stats) {
  const sum = $("sum"); sum.textContent = "";
  for (const [k, n] of Object.entries(stats)) {
    const li = document.createElement("li"), b = document.createElement("b");
    li.textContent = LABELS[k] || k; b.textContent = "×" + n; li.append(b); sum.append(li);
  }
}

async function anonymize() {
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
function restore() {
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
$("sample").onclick = () => { $("inp").value = SAMPLE; say("已載入範例,按「去識別化」試試。"); };
$("file").onchange = async (e) => { const f = e.target.files[0]; if (f) { $("inp").value = await f.text(); say("已載入 " + f.name); } };
$("dlOut").onclick = () => download("deidentified.txt", $("out").value);
$("dlMap").onclick = () => download("map.json", $("map").value);
$("copy").onclick = async () => { try { await navigator.clipboard.writeText($("out").value); say("已複製輸出。"); } catch (e) { say("無法複製,請手動選取。", true); } };
$("clear").onclick = () => { for (const id of ["inp", "out", "map", "key"]) $(id).value = ""; showStats({}); say("已清除。"); };
$("theme").onclick = () => {
  const el = document.documentElement;
  const dark = el.dataset.theme ? el.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  el.dataset.theme = dark ? "light" : "dark";
  try { localStorage.setItem("deid-theme", el.dataset.theme); } catch (e) {}
};
