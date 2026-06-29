import os
import json
from anthropic import Anthropic
from src.config import PIIMatch, PIIType

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """你是台灣公文個資審查員，專門找出文件中可能洩漏個人身分的資訊。

任務：找出以下類型的 PII，特別是「正則表達式不容易抓到」的：
- name: 中文姓名（含「申請人王○○」這種半遮蔽寫法）
- organization: 學校、單位、公司名稱
- date: 日期資訊（如「民國八十年三月生」）
- address: 地址（含部分地址如「住台北市信義區」）
- school_id: 學號

不要重複偵測：身分證號、Email、電話/手機（這些已經由正則處理）。

只回傳 JSON，不要任何其他文字。格式：
{
  "detections": [
    {"text": "原文中的確切片段", "type": "name|organization|date|address|school_id", "confidence": 0.0-1.0}
  ]
}

如果沒有發現，回傳 {"detections": []}。
"""

def chunk_text(text: str, size: int = 2000, overlap: int = 200) -> list[tuple[int, str]]:
    """切 chunk，回傳 [(offset, chunk_text), ...]"""
    chunks = []
    i = 0
    while i < len(text):
        chunks.append((i, text[i:i+size]))
        i += size - overlap
    return chunks

def detect(text: str, model: str = "claude-sonnet-4-5") -> list[PIIMatch]:
    matches = []
    for offset, chunk in chunk_text(text):
        resp = client.messages.create(
            model=model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"<document>\n{chunk}\n</document>"}],
        )
        raw = resp.content[0].text.strip()
        # 去除可能的 markdown fence
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json\n")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        
        for d in data.get("detections", []):
            # 在 chunk 裡找這個片段定位回原文
            local_idx = chunk.find(d["text"])
            if local_idx == -1:
                continue
            global_start = offset + local_idx
            matches.append(PIIMatch(
                text=d["text"],
                pii_type=PIIType(d["type"]),
                start=global_start,
                end=global_start + len(d["text"]),
                confidence=d.get("confidence", 0.7),
                source="llm",
                context=chunk[max(0,local_idx-15):local_idx+len(d["text"])+15],
            ))
    return matches

def merge(regex_matches: list[PIIMatch], llm_matches: list[PIIMatch]) -> list[PIIMatch]:
    """合併去重：以正則為準，LLM 補完未重疊區段"""
    result = list(regex_matches)
    regex_spans = [(m.start, m.end) for m in regex_matches]
    for m in llm_matches:
        overlap = any(not (m.end <= s or m.start >= e) for s, e in regex_spans)
        if not overlap:
            result.append(m)
    return sorted(result, key=lambda x: x.start)