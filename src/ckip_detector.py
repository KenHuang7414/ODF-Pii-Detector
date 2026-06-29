# src/ckip_detector.py
from __future__ import annotations
from .config import PIIMatch, PIIType

_known_names: list[str] = []

def set_known_names(names: list[str]) -> None:
    global _known_names
    _known_names = sorted(
        list({n.strip() for n in names if n.strip()}),
        key=len, reverse=True,
    )
    print(f"[CKIP] 已載入 {len(_known_names)} 個姓名：{_known_names}")

def detect(text: str) -> list[PIIMatch]:
    if not text.strip() or not _known_names:
        return []
    matches = []
    for name in _known_names:
        search_start = 0
        while True:
            pos = text.find(name, search_start)
            if pos == -1:
                break
            matches.append(PIIMatch(
                text=name,
                pii_type=PIIType.NAME,
                start=pos,
                end=pos + len(name),
                confidence=1.0,
                source="ckip",
                context=text[max(0, pos - 20) : pos + len(name) + 20],
            ))
            search_start = pos + len(name)
    return sorted(matches, key=lambda m: m.start)