"""本機網頁介面:只綁 127.0.0.1,無狀態,資料不落地、不外送。"""
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core import Deidentifier, restore_text

PAGE = """<!doctype html><html lang="zh-Hant"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>去識別化工具</title>
<style>body{font:15px system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px}
textarea{width:100%;height:170px;font:14px monospace;box-sizing:border-box}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:8px 0}
button{padding:8px 16px;cursor:pointer}#stats{color:#555}small{color:#a00}</style>
<h1>去識別化工具</h1>
<small>僅在本機執行,資料不會上傳。對照表含原始個資,請妥善保管。</small>
<h3>輸入</h3><textarea id="inp" placeholder="貼上要處理的文字"></textarea>
<div class="row">
<label>模式 <select id="mode"><option value="token">token(可還原)</option>
<option value="mask">mask(遮蔽)</option><option value="hash">hash(假名化)</option></select></label>
<label>密鑰(hash) <input id="key" type="password"></label>
<label>已知姓名(一行一個)<br><textarea id="names" style="height:50px;width:220px"></textarea></label></div>
<div class="row"><button onclick="run('anonymize')">去識別化 ↓</button>
<button onclick="run('restore')">用對照表還原 ↓</button><span id="stats"></span></div>
<h3>輸出</h3><textarea id="out" readonly></textarea>
<h3>對照表(JSON,可貼回以還原)</h3><textarea id="map"></textarea>
<script>
const $=id=>document.getElementById(id);
async function run(kind){
 const body=kind=='anonymize'?{text:$('inp').value,mode:$('mode').value,key:$('key').value,
  names:$('names').value.split('\\n').map(s=>s.trim()).filter(Boolean)}
  :{text:$('inp').value,mapping:JSON.parse($('map').value||'{}')};
 try{const r=await fetch('/api/'+kind,{method:'POST',body:JSON.stringify(body)});
  const j=await r.json(); if(j.error){$('stats').textContent='錯誤:'+j.error;return}
  $('out').value=j.text; if(kind=='anonymize'){$('map').value=JSON.stringify(j.mapping,null,2);
  $('stats').textContent='偵測:'+JSON.stringify(j.stats)}else $('stats').textContent='已還原'}
 catch(e){$('stats').textContent='錯誤:'+e}}
</script></html>"""


def make_handler(use_ner):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _host_ok(self):  # 防 DNS rebinding
            return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

        def do_GET(self):
            if self.path == "/" and self._host_ok():
                self._send(200, PAGE, "text/html; charset=utf-8")
            else:
                self._send(404, "{}")

        def do_POST(self):
            if not self._host_ok():
                return self._send(403, json.dumps({"error": "forbidden"}))
            try:
                req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                if self.path == "/api/anonymize":
                    d = Deidentifier(req.get("mode", "token"), req.get("names", []),
                                     req.get("key") or None, ner=use_ner)
                    text = d.anonymize_text(req.get("text", ""))
                    out = {"text": text, "mapping": d.mapping, "stats": d.stats}
                elif self.path == "/api/restore":
                    out = {"text": restore_text(req.get("text", ""), req.get("mapping", {}))}
                else:
                    return self._send(404, "{}")
                self._send(200, json.dumps(out, ensure_ascii=False))
            except Exception as e:  # 回報給使用者,不洩漏堆疊
                self._send(400, json.dumps({"error": str(e)}, ensure_ascii=False))

        def log_message(self, *a):  # 不記錄請求,避免個資進 log
            pass

    return H


def serve(port=8765, use_ner=False, open_browser=True):
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(use_ner))
    url = f"http://127.0.0.1:{port}/"
    print("介面已啟動:", url, "(Ctrl+C 結束)")
    if open_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
