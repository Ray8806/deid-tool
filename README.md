# deid-tool 去識別化工具

離線執行、只用 Python 標準庫(處理 `.xlsx` 才需 `pip install openpyxl`)。資料不會離開你的電腦。

## 用法
```bash
# 掃描:只看偵測到幾筆,不輸出內容
python -m deid_tool scan 病歷.txt

# 去識別化(可還原):輸出內容 + 對照表
python -m deid_tool anonymize 病歷.csv -o out.csv --map map.json --names names.txt --column 姓名=NAME

# 還原
python -m deid_tool restore out.csv -o back.csv --map map.json

# 不可還原:遮蔽 / HMAC 假名化
python -m deid_tool anonymize in.txt -o out.txt --mode mask
python -m deid_tool anonymize in.txt -o out.txt --mode hash --key 你的密鑰
```
支援 `.txt/.md`、`.csv`、`.xlsx`。

## 網站版(純前端,推薦給一般使用者)
`docs/index.html` 是靜態網頁,所有處理都在瀏覽器內完成,沒有後端、不上傳資料,頁面的 CSP 也禁止對外連線。
- 直接用瀏覽器開啟 `docs/index.html` 即可離線使用。
- 要部署成網址:GitHub repo → Settings → Pages → Deploy from a branch → `main` / `/docs`。
  (私人 repo 使用 Pages 需要付費方案;網頁本身不含任何個資,可考慮改為公開 repo。)
- 規則與 Python 版一致(`docs/deid-core.js` ↔ `deid_tool/core.py`),修改規則時兩邊都要改。
- 網站版支援文字、`.txt`、`.csv`(整份當文字處理),不含 Excel、整欄處理與 NER,這些請用 Python 版。

## 網頁介面(本機)
```bash
python -m deid_tool gui            # 開啟 http://127.0.0.1:8765/
python -m deid_tool gui --ner      # 同時啟用 NER 人名偵測
```
只綁定 127.0.0.1、不記錄請求內容、不寫入磁碟;對照表只顯示在頁面上,由你自行複製保存。

## NER 人名偵測(選用)
```bash
pip install ckip-transformers
python -m deid_tool anonymize 病歷.txt -o out.txt --map map.json --ner
```
可找出沒有「姓名:」等關鍵字提示的人名。首次使用會下載模型(需連網),之後可離線。NER 有誤判與漏判,請人工抽查。

## 偵測項目
身分證/居留證(含檢查碼驗證)、手機、市話、Email、信用卡(Luhn)、IP、日期(西元/民國)、地址、病歷號、姓名(關鍵字後面 + `--names` 清單)。

## 注意
- `map.json` 內含原始個資,等同機密檔,權限為 600,請勿與去識別化後的檔案放在一起或上傳。
- 規則式偵測不保證 100% 涵蓋(尤其是無關鍵字的姓名、非結構化描述),正式使用前請人工抽查。
- 測試:`python -m unittest discover -s tests`
