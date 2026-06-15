# PII Detector for ODT

## 專案目標
偵測並去識別化台灣公文 .odt 檔中的個人識別資訊（PII）。

## 角色定義（給 Claude API 用）
當呼叫 Claude API 偵測 PII 時，使用以下 system prompt:
"你是台灣公文個資審查員，專門找出文件中的個人識別資訊..."

## 偵測項目
- 身分證號（含檢查碼驗證）
- 手機/市話
- Email
- 生日（西元/民國/模糊）
- 中文姓名
- 學校/機構名稱
- 地址

## 技術選型
- 文件處理：odfdo
- LLM：Claude Sonnet
- Web：FastAPI

## 開發規範
- 所有偵測器回傳統一格式 PIIMatch (見 src/config.py)
- 遮蔽不破壞原 ODF 樣式
- 不在 log 中印出 PII 原文，只印類型和位置