const $ = (id) => document.getElementById(id);
const say = (m) => ($("status").textContent = m);

async function anonymize() {
  try {
    const d = new Deid.Deidentifier($("mode").value,
      $("names").value.split("\n").map((s) => s.trim()).filter(Boolean), $("key").value);
    $("out").value = await d.anonymize($("inp").value);
    $("map").value = $("mode").value === "token" ? JSON.stringify(d.mapping, null, 2) : "";
    say("偵測:" + (JSON.stringify(d.stats) === "{}" ? "未偵測到個資" : JSON.stringify(d.stats)));
  } catch (e) { say("錯誤:" + e.message); }
}
function restore() {
  try {
    $("out").value = Deid.restore($("inp").value, JSON.parse($("map").value || "{}"));
    say("已還原");
  } catch (e) { say("錯誤:對照表不是有效的 JSON"); }
}
function download(name, text) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
}
$("go").onclick = anonymize;
$("back").onclick = restore;
$("file").onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return;
  $("inp").value = await f.text(); say("已載入 " + f.name);
};
$("dlOut").onclick = () => download("deidentified.txt", $("out").value);
$("dlMap").onclick = () => download("map.json", $("map").value);
$("copy").onclick = async () => { await navigator.clipboard.writeText($("out").value); say("已複製輸出"); };
$("clear").onclick = () => { for (const id of ["inp", "out", "map", "key"]) $(id).value = ""; say("已清除"); };
