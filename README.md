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

## 偵測項目
身分證/居留證(含檢查碼驗證)、手機、市話、Email、信用卡(Luhn)、IP、日期(西元/民國)、地址、病歷號、姓名(關鍵字後面 + `--names` 清單)。

## 注意
- `map.json` 內含原始個資,等同機密檔,權限為 600,請勿與去識別化後的檔案放在一起或上傳。
- 規則式偵測不保證 100% 涵蓋(尤其是無關鍵字的姓名、非結構化描述),正式使用前請人工抽查。
- 測試:`python -m unittest discover -s tests`
