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
├── claude.md               # 給 Claude Code / 隊友看的專案說明
├── cli.py                  # 命令列入口
├── src/
│   ├── __init__.py
│   ├── config.py           # PII 類型定義、遮蔽策略
│   ├── odt_io.py           # 讀寫 .odt、抽取純文字
│   ├── regex_detector.py   # 正則層偵測
│   ├── llm_detector.py     # Claude API 層偵測
│   ├── masker.py           # 套用遮蔽到 .odt
│   ├── reporter.py         # 產出偵測報告 .odt
│   └── pipeline.py         # 串接整個流程 + 自我驗證 loop
├── tests/
│   ├── test_regex.py
│   └── samples/
│       ├── ODF測試文件.odt   # 模擬政府公文
│       ├── 比賽報名表.odt    # 模擬競賽報名場景
│       └── 退學申請單.odt    # 模擬學校申請場景
└── outputs/                # 執行結果輸出（gitignore）
```

---

## 各程式檔案說明

### `src/config.py`
定義整個專案共用的資料結構：

- `PIIType`：PII 類型列舉（身分證號、手機、市話、Email、日期、姓名、機構、地址）
- `PIIMatch`：一筆偵測結果的資料格式（命中文字、類型、位置、信心度、來源是 `regex` 還是 `llm`）
- `MASK_STRATEGIES`：三種遮蔽策略的實作
  - `block`：全部替換成 `█`
  - `label`：替換成 `[類型名稱]`，例如 `[ID_NUMBER]`、`[DATE]`
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

- `validate_tw_id(id_str)`：驗證台灣身分證號檢查碼（最後一碼）是否正確，排除格式符合但非真實號碼的假號碼
- `CN_NUM`：中文數字字元集（一二三…百零〇及阿拉伯數字），供生日與地址 pattern 共用
- `PATTERNS`：各類型的正則表達式
- `detect(text)`：對輸入文字跑所有 pattern，回傳 `PIIMatch` 清單

**目前可正確偵測**：

| 類型 | 支援格式 |
|---|---|
| 身分證號 | 含檢查碼驗證，自動排除假號碼 |
| 手機 | `09XX-XXX-XXX` 及無分隔符格式 |
| 市話 | 含括號區碼，如 `(02)2345-6789`、`02-2345-6789` |
| Email | 標準 Email 格式，僅匹配英文字元避免中文誤抓 |
| 日期 | 西元年（`/`、`-`、中文分隔）；民國年＋阿拉伯數字；民國年＋中文數字（如「民國七十五年三月二十日」）；年月日齊全才抓，避免「XX年度」誤判 |
| 地址 | 路街名＋段巷弄號樓，支援中文數字段別（如「重慶南路一段122號5樓」） |

**設計上不處理（交給 LLM 層）**：

- 中文姓名、半遮蔽姓名（如「陳同學」）
- 機構/學校名稱
- 只有年份的模糊日期（如「民國八十年生」）
- 需要語意判斷才能確認的地址前綴（縣市、鄉鎮區）

### `src/llm_detector.py`
Claude API 偵測層，處理**需要語意理解**的 PII：

- `SYSTEM_PROMPT`：要求 Claude 只找姓名、機構、模糊日期、地址，且只回傳 JSON，不重複偵測正則層已涵蓋的類型
- `chunk_text(text)`：把長文件切成 2000 字、重疊 200 字的區塊，避免單次請求過長
- `detect(text)`：對每個 chunk 呼叫 Claude API，解析回傳的 JSON，把命中片段定位回原文，回傳 `PIIMatch` 清單（`source="llm"`）
- `merge(regex_matches, llm_matches)`：合併兩層結果並去重，以正則結果為準，LLM 結果只在不重疊的區段才採用

**隱私設計**：送給 Claude 之前，`pipeline.py` 會先把正則層找到的高敏感資訊（身分證號、電話、Email 等）替換成 placeholder（如 `[ID_NUMBER]`），確保明文個資不外送至 API。

需要 `ANTHROPIC_API_KEY` 才能執行。

### `src/masker.py`
把偵測結果實際套用到 `.odt` 文件：

- `apply_masks(doc, segments, matches, strategy)`：對每個段落，找出落在該段落範圍內的所有 `PIIMatch`，從後往前依序替換成遮蔽文字，最後寫回該段落
- `mask_text(text, matches, strategy)`：對純文字字串套用遮蔽，不碰 .odt 結構，用於送給 LLM 之前的 placeholder 預處理

**目前限制（MVP 階段）**：如果段落內含有 `<text:span>`、`<text:line-break/>`、`<text:tab/>` 等子元素（例如公文裡常見的條列式格式），會被「攤平」成單一文字節點——遮蔽結果正確，但段落內的換行/Tab/局部樣式會消失。詳見程式內註解。未來改進方向：改為走 span tree 進行精確的節點層級替換。

### `src/reporter.py`
產出偵測結果報告，格式也是 `.odt`：

- `build_report(matches, source_filename)`：產生一份包含總計筆數、類型統計、逐項列表（類型/原文/信心度/來源）的報告文件

### `src/pipeline.py`
串接以上所有模組的主流程，核心函式 `run()`：

1. 讀取 .odt，抽取純文字
2. 正則層掃描
3.（可選）把正則結果替換成 placeholder，再送給 Claude API 掃描，結果重新對應回原始位置
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
[3/5] Claude 掃描（已遮蔽身分證/電話/Email 等高敏感欄位）
      → 找到 M 筆
[4/5] 合併後共 N+M 筆，套用遮蔽
[驗證 round 1] 重新檢查遮蔽結果
      → 通過（或：仍有 X 筆殘留，二次遮蔽）
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

# 類型標籤，例如 [ID_NUMBER]、[DATE]
python cli.py "tests/samples/ODF測試文件.odt" --strategy label

# 部分遮蔽，例如 王○明
python cli.py "tests/samples/ODF測試文件.odt" --strategy partial
```

⚠️ 三次執行會產出同名檔案、互相覆蓋。若要保留三份比較，每次執行後手動把 `outputs/` 內的檔案改名。

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

- `validate_tw_id`：合法/不合法身分證檢查碼驗證
- 各類型 PII 的偵測：身分證號、手機、市話、Email、日期（西元/民國年/中文數字）、地址
- 正常文字不應誤判（no false positives）：公文字號含「號」不應被誤判為地址；「民國XX年度」不應被誤判為日期

執行方式：

```bash
pytest tests/test_regex.py -v
```

需要專案根目錄有 `pytest.ini`（內容 `[pytest]\npythonpath = .`），讓 pytest 能找到 `src` 模組。

### 測試樣本文件

三份樣本分別模擬不同公文場景，涵蓋的 PII 類型如下：

| 類型 | 範例 | 偵測層 | 說明 |
|---|---|---|---|
| 身分證號（合法檢查碼） | A123456789 | 正則 | |
| 身分證號（檢查碼錯誤） | B234567890 | **故意不被偵測** | 驗證檢查碼過濾邏輯正確 |
| 手機 | 0912-345-678 | 正則 | |
| 市話 | (02)2345-6789 | 正則 | |
| Email | wang.jianguo@example.com | 正則 | |
| 西元日期 | 1980/07/15 | 正則 | |
| 民國年日期（阿拉伯數字） | 民國75年3月20日 | 正則 | |
| 民國年日期（中文數字） | 民國七十五年三月二十日 | 正則 | 已支援，不再需要 LLM |
| 地址（路號樓） | 重慶南路一段122號5樓 | 正則 | |
| 完整地址（含縣市區） | 台北市中正區重慶南路一段122號5樓 | 正則 | |
| 姓名 | 王建國、林雅婷、張明遠 | LLM | |
| 半遮蔽姓名 | 陳同學、黃同學 | LLM | |
| 機構/學校 | 台北市立第一高級中學 | LLM | |
| 模糊日期（僅年份） | 民國八十年生 | LLM | 正則層已知限制，年月日齊全才抓 |

---

## 已知限制 / 未來改進

1. **段落格式攤平**：含 `<text:span>`、line-break、tab 的段落會被攤平成單一文字節點，內部樣式/換行消失（見 `src/masker.py` 註解）。未來改進方向：改為走 span tree 進行精確的節點層級替換，保留原始排版。

2. **模糊日期**：「民國八十年生」（只有年，無月日）正則層不處理，避免「民國XX年度」這類公文用語誤判。此類案例交由 LLM 層補抓。

3. **隱私考量**：LLM 層送出前已先用 placeholder 替換正則層找到的高敏感欄位（身分證號、電話、Email），降低明文外洩風險。`--no-llm` 提供「完全本機模式」，資料完全不送出。未來可考慮接入本地 LLM（如 Ollama + Qwen）作為零外洩選項。

4. **輸出檔名衝突**：三種遮蔽策略（block/label/partial）輸出同名檔案，會互相覆蓋。若需保留多份比較結果，執行後手動改名。