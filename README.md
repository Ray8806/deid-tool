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
支援 `.txt/.md`、`.csv`、`.xlsx`、`.docx`、`.pptx`、`.pdf`。

## Excel / Word / PowerPoint / PDF
```bash
pip install python-docx python-pptx lxml   # Word / PowerPoint / Excel(PDF 另需 pymupdf)
python -m deid_tool anonymize 報告.docx -o out.docx --map map.json --names names.txt
python -m deid_tool restore out.docx -o back.docx --map map.json
python -m deid_tool anonymize 簡報.pptx -o out.pptx --map map.json
python -m deid_tool anonymize 名單.xlsx -o out.xlsx --map map.json --column 姓名=NAME
python -m deid_tool anonymize 掃描前.pdf -o out.pdf
```
| 格式 | 作法 | 可還原 |
|---|---|---|
| Word `.docx` | 逐段落替換,保留字型/粗體等格式;處理內文、表格、頁首頁尾、文字方塊、註解、註腳,並清空作者、註解/修訂者與預覽縮圖 | 是(token 模式) |
| PowerPoint `.pptx` | 同上,另含講者備忘稿 | 是(token 模式) |
| Excel `.xlsx` | 直接改檔案內部的文字,**格式、數字、公式、圖片、圖表原樣保留**;處理儲存格、註解、文字方塊;`--column` 可指定標題欄整欄處理,並清掉不再被引用的原值 | 是(token 模式) |
| PDF | 偵測後做**真正的塗黑**(連底層文字層一起移除,複製貼上也找不到),並清空中繼資料 | 否(一律塗黑) |

限制:
- **圖片內的文字**(截圖、掃描檔、圖表圖片)無法偵測。掃描型 PDF 沒有文字層,工具會警告並略過該頁,請先 OCR 或人工處理。
- 圖表(chart)內的資料標籤、Word/PPT 內嵌物件不在處理範圍。
- PDF 若個資被換行或斷成多段,可能搜尋不到,處理後請開啟檢查。
- 處理完請務必人工打開輸出檔,逐頁確認。

## 網站版(純前端,推薦給一般使用者)
`docs/index.html` 是靜態網頁,所有處理都在瀏覽器內完成,沒有後端、不上傳資料,頁面的 CSP 也禁止對外連線。
- 直接用瀏覽器開啟 `docs/index.html` 即可離線使用。
- 要部署成網址:GitHub repo → Settings → Pages → Deploy from a branch → `main` / `/docs`。
  (私人 repo 使用 Pages 需要付費方案;網頁本身不含任何個資,可考慮改為公開 repo。)
- 規則與 Python 版一致(`docs/deid-core.js` ↔ `deid_tool/core.py`),修改規則時兩邊都要改。
- 網站版支援文字、`.txt`、`.csv`,以及 **Word `.docx`、PowerPoint `.pptx`、Excel `.xlsx`**:逐段落替換並保留格式,清除作者與預覽縮圖,Excel 可指定欄名整欄當姓名處理;處理後的檔案直接下載,還原時載入該檔並貼上對照表即可。
- **手動標記**:在輸入框選取文字按「標記選取文字」,或在輸入框右邊直接輸入詞,文中(或整份 Word/PPT/Excel 內)所有相同字串都會處理,可指定類型、可隨時移除。人名沒有關鍵字時特別好用。
- 網站版不含 PDF 與 NER,這些請用 Python 版。
- `docs/jszip.min.js` 為 [JSZip](https://stuk.github.io/jszip/) 3.10.1(MIT 授權,見 `docs/JSZIP-LICENSE.md`),以自家檔案提供,頁面不需連到外部網站。
- `docs/samples/` 內是虛構資料的 Word / PowerPoint / Excel 範例檔。

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

## 表格(CSV / Excel)的整欄自動處理
依第一列標題自動判斷整欄類型,**不依賴規則是否涵蓋每種寫法**(電話、地址格式五花八門時最可靠):

| 標題含有 | 整欄當作 |
|---|---|
| 電話、手機、傳真、Phone、Mobile | 電話 |
| 地址、住址、通訊處、Address | 地址 |
| 信箱、Email、電子郵件 | Email |
| 身分證、居留證、護照 | 身分證 |
| 生日、出生 | 日期 |
| 姓名、名字、聯絡人、負責人、收件人、承辦人、申請人、代表人、窗口、病人、患者 | 姓名 |

- 以數字儲存的電話等數字儲存格也會處理(還原時會變成文字)。
- 標題不在清單內(例如「對口」)可用 `--column 對口=NAME` 指定;不想自動判斷用 `--no-auto-columns`。
- 「統一編號」是公司稅籍編號,不屬於個人資料,預設不處理;公司名稱也不處理。

## 注意
- `map.json` 內含原始個資,等同機密檔,權限為 600,請勿與去識別化後的檔案放在一起或上傳。
- 規則式偵測不保證 100% 涵蓋(尤其是無關鍵字的姓名、非結構化描述),正式使用前請人工抽查。
- 測試:`python -m unittest discover -s tests`
