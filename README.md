# ODT PII Detector

偵測並去識別化 ODT 公文中的個人識別資訊（PII），結合「正則表達式」與「Claude API」雙層偵測，並具備自我驗證 loop。

---

## 專案結構

```
pii-detector/
├── .env                    # 存放 ANTHROPIC_API_KEY（不進 git）
├── .env.example
├── .gitignore
├── pytest.ini              # 讓 pytest 找得到 src 模組
├── requirements.txt
├── README.md
├── claude.md                # 給 Claude Code / 隊友看的專案說明
├── cli.py                   # 命令列入口
├── src/
│   ├── __init__.py
│   ├── config.py            # PII 類型定義、遮蔽策略
│   ├── odt_io.py             # 讀寫 .odt、抽取純文字
│   ├── regex_detector.py     # 正則層偵測
│   ├── llm_detector.py        # Claude API 層偵測
│   ├── masker.py              # 套用遮蔽到 .odt
│   ├── reporter.py            # 產出偵測報告 .odt
│   └── pipeline.py            # 串接整個流程 + 自我驗證 loop
├── tests/
│   ├── test_regex.py
│   └── samples/
│       └── ODF測試文件.odt
└── outputs/                  # 執行結果輸出（gitignore）
```

---

## 各程式檔案說明

### `src/config.py`
定義整個專案共用的資料結構：

- `PIIType`：PII 類型列舉（身分證號、手機、市話、Email、生日、姓名、機構、地址）
- `PIIMatch`：一筆偵測結果的資料格式（命中文字、類型、位置、信心度、來源是 `regex` 還是 `llm`）
- `MASK_STRATEGIES`：三種遮蔽策略的實作
  - `block`：全部替換成 `█`
  - `label`：替換成 `[類型名稱]`
  - `partial`：保留頭尾，中間用 `○` 遮蔽（例如「王小明」→「王○明」）

其他模組都依賴這份定義，是整個專案的「共同語言」。

### `src/odt_io.py`
負責讀寫 `.odt` 檔案，封裝 `odfdo` 套件：

- `load(path)`：讀取 .odt，回傳 `Document` 物件
- `save(doc, path)`：儲存 .odt
- `extract_text(doc)`：走訪文件所有段落（`<text:p>` / `<text:h>`），把段落內容（包含 line-break、tab 等都轉成 `\n`/`\t`）合併成一份純文字字串，同時回傳每個段落對應的 `TextSegment`（記錄該段文字在合併字串中的起始位置，供後續定位遮蔽用）

這是 PII 偵測和遮蔽的「入口」與「出口」。

### `src/regex_detector.py`
正則表達式偵測層，處理**格式固定、可規則化**的 PII：

- `validate_tw_id(id_str)`：驗證台灣身分證號檢查碼是否正確
- `PATTERNS`：各類型的正則表達式（身分證號、手機、市話、Email、生日）
- `detect(text)`：對輸入文字跑所有 pattern，回傳 `PIIMatch` 清單。身分證號會額外用檢查碼過濾掉格式對但檢查碼錯的假號碼

**目前可正確偵測**：身分證號（含檢查碼驗證）、手機（09 開頭）、市話（含括號區碼）、Email、西元格式生日。

**設計上無法處理**：中文姓名、機構名稱、民國年中文數字生日、地址——這些交給 LLM 層。

### `src/llm_detector.py`
Claude API 偵測層，處理**需要語意理解**的 PII：

- `SYSTEM_PROMPT`：要求 Claude 只找姓名、機構、模糊生日、地址，且只回傳 JSON
- `chunk_text(text)`：把長文件切成 2000 字、重疊 200 字的區塊，避免單次請求過長
- `detect(text)`：對每個 chunk 呼叫 Claude API，解析回傳的 JSON，把命中片段定位回原文，回傳 `PIIMatch` 清單（`source="llm"`）
- `merge(regex_matches, llm_matches)`：合併兩層結果並去重——以正則結果為準，LLM 結果只在不重疊的區段才採用

需要 `ANTHROPIC_API_KEY` 才能執行。

### `src/masker.py`
把偵測結果實際套用到 `.odt` 文件：

- `apply_masks(doc, segments, matches, strategy)`：對每個段落，找出落在該段落範圍內的所有 `PIIMatch`，從後往前依序替換成遮蔽文字，最後寫回該段落

**目前限制（MVP 階段）**：如果段落內含有 `<text:span>`、`<text:line-break/>`、`<text:tab/>` 等子元素（例如公文裡常見的條列式格式），會被「攤平」成單一文字節點——遮蔽結果正確，但段落內的換行/Tab/局部樣式會消失。詳見程式內註解。

### `src/reporter.py`
產出偵測結果報告，格式也是 `.odt`：

- `build_report(matches, source_filename)`：產生一份包含總計筆數、類型統計、逐項列表（類型/原文/信心度/來源）的報告文件

### `src/pipeline.py`
串接以上所有模組的主流程，核心函式 `run()`：

1. 讀取 .odt，抽取純文字
2. 正則層掃描
3.（可選）Claude API 層掃描
4. 合併兩層結果，套用遮蔽，輸出 `*_masked.odt`
5.（可選）**自我驗證 loop**：把遮蔽後的文件再丟給 Claude 檢查是否還有殘留 PII，有的話再遮一次，最多執行 `max_validation_rounds` 次
6. 輸出 `*_report.odt`

回傳值包含輸出路徑與偵測總筆數。

### `cli.py`
命令列入口，呼叫 `pipeline.run()` 並印出進度與結果路徑。

---

## 安裝

```bash
# 建立並啟用虛擬環境
python -m venv .venv
source .venv/bin/activate          # Mac/Linux
# .venv\Scripts\activate           # Windows

# 安裝套件
pip install -r requirements.txt
```

`.env` 需包含：

```
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

---

## 使用方式（cli.py）

### 基本指令格式

```bash
python cli.py <輸入檔案路徑> [--strategy block|label|partial] [--no-llm]
```

### 完整流程（正則 + Claude API + 自我驗證）

```bash
python cli.py "tests/samples/ODF測試文件.odt" --strategy block
```

執行步驟與輸出：

```
[1/5] 讀取 tests/samples/ODF測試文件.odt
[2/5] 正則掃描
      → 找到 N 筆
[3/5] Claude 掃描
      → 找到 M 筆
[4/5] 合併後共 N+M 筆，套用遮蔽
[驗證 round 1] 重新檢查遮蔽結果
      → 通過 (或：仍有 X 筆殘留，二次遮蔽)
[5/5] 產出報告

完成！
  遮蔽版：outputs/ODF測試文件_masked.odt
  報告：  outputs/ODF測試文件_report.odt
  總計：  N 筆 PII
```

### 只跑正則層（不需要 API key，免費、快速）

```bash
python cli.py "tests/samples/ODF測試文件.odt" --no-llm --strategy block
```

適合：

- 沒有設定 `.env` 時的快速測試
- 「敏感模式」——資料完全不送出本機
- 驗證 odfdo 讀寫和遮蔽邏輯本身是否正常運作（排除 LLM 層的變因）

### 切換遮蔽策略

```bash
# 全黑遮蔽（預設）
python cli.py "tests/samples/ODF測試文件.odt" --strategy block

# 類型標籤，例如 [ID_NUMBER]
python cli.py "tests/samples/ODF測試文件.odt" --strategy label

# 部分遮蔽，例如 王○明
python cli.py "tests/samples/ODF測試文件.odt" --strategy partial
```

⚠️ 三次執行會產出同名檔案、互相覆蓋。若要保留三份比較，每次執行後手動把 `outputs/` 內的檔案改名，或執行前修改 `pipeline.py` 的輸出檔名邏輯。

### 輸出檔案

| 檔案 | 內容 |
|---|---|
| `outputs/<檔名>_masked.odt` | 去識別化後的文件 |
| `outputs/<檔名>_report.odt` | 偵測報告（總筆數、類型統計、逐項列表） |

兩者都可用 LibreOffice / OnlyOffice 開啟檢查。

---

## 測試（tests/）

### `tests/test_regex.py`

針對 `src/regex_detector.py` 的單元測試，**不需要 API key**，涵蓋：

- `validate_tw_id`：合法/不合法身分證檢查碼
- 各類型 PII 的偵測（身分證號、手機、市話、Email、西元生日）
- 正常文字不應誤判（no false positives）
- 一個刻意設計成 PASS 的「已知限制」測試：民國年中文數字生日（如「民國七十五年三月二十日」），正則層**理當抓不到**，這個測試斷言「抓不到」這件事本身是正確的，提醒這部分要靠 LLM 層處理，不是 bug

執行方式：

```bash
pytest tests/test_regex.py -v
```

需要專案根目錄有 `pytest.ini`（內容 `[pytest]\npythonpath = .`），讓 pytest 能找到 `src` 模組。

### `tests/samples/ODF測試文件.odt`

一份模擬公文，內容混合「正則容易抓」與「正則難抓、需 LLM」的案例，用於整合測試（即跑 `cli.py`）：

| 類型 | 範例 | 偵測層 |
|---|---|---|
| 身分證號（合法檢查碼） | A123456789 | 正則 |
| 身分證號（檢查碼錯誤） | B234567890 | **故意不被偵測**，驗證檢查碼過濾邏輯正確 |
| 手機 | 0912-345-678、0987-654-321 | 正則 |
| 市話 | (02)2345-6789 | 正則 |
| Email | wang.jianguo@example.com | 正則 |
| 西元生日 | 1980/07/15 | 正則 |
| 民國生日（中文數字） | 民國七十五年三月二十日 | LLM |
| 姓名 | 王建國、林雅婷、張明遠 | LLM |
| 半遮蔽姓名 | 陳同學、黃同學 | LLM |
| 機構/學校 | 台北市立第一高級中學 | LLM |
| 地址 | 台北市中正區重慶南路一段122號5樓 | LLM（效果待驗證）|

---

## 已知限制 / 未來改進

1. **段落格式**：含 `<text:span>`、line-break、tab 的段落會被攤平成單行，內部樣式/換行消失（見 `src/masker.py` 註解）
2. **地址偵測**：尚未充分測試，LLM 層效果待驗證
3. **隱私考量**：目前 LLM 層會把文件全文送至 Claude API。`--no-llm` 提供「敏感模式」，未來可考慮接入本地 LLM（如透過 Ollama）作為零外洩選項，但準確度會下降
4. **遮蔽策略輸出檔名**：三種策略輸出同名檔案會互相覆蓋，尚未做版本區分