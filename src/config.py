from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

class PIIType(str, Enum):
    ID_NUMBER = "id_number"
    MOBILE = "mobile"
    PHONE = "phone"
    EMAIL = "email"
    DATE = "date"
    NAME = "name"
    ORG = "organization"
    ADDRESS = "address"
    SCHOOL_ID = "school_id"

@dataclass
class PIIMatch:
    text: str                  # 命中的原文片段
    pii_type: PIIType
    start: int                 # 在純文字中的起始位置
    end: int                   # 結束位置
    confidence: float          # 0.0 ~ 1.0
    source: Literal["regex", "llm", "ckip"]
    context: str = ""          # 前後文（debug 用）

# 遮蔽策略
MASK_STRATEGIES = {
    "block": lambda text, t: "█" * len(text),
    "label": lambda text, t: f"[{t.value.upper()}]",
    "partial": lambda text, t: _partial_mask(text, t),
}

def _partial_mask(text: str, pii_type: PIIType) -> str:
    """保留首尾，中間遮蔽。王小明 → 王○明"""
    if len(text) <= 2:
        return "○" * len(text)
    return text[0] + "○" * (len(text) - 2) + text[-1]