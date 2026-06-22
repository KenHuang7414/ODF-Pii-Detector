import re
from src.config import PIIMatch, PIIType

def validate_tw_id(id_str: str) -> bool:
    if not re.match(r"^[A-Z][12]\d{8}$", id_str):
        return False
    letter_map = {
        'A':10,'B':11,'C':12,'D':13,'E':14,'F':15,'G':16,'H':17,
        'I':34,'J':18,'K':19,'L':20,'M':21,'N':22,'O':35,'P':23,
        'Q':24,'R':25,'S':26,'T':27,'U':28,'V':29,'W':32,'X':30,
        'Y':31,'Z':33
    }
    n = letter_map[id_str[0]]
    total = (n // 10) + (n % 10) * 9
    for i, d in enumerate(id_str[1:9]):
        total += int(d) * (8 - i)
    total += int(id_str[9])
    return total % 10 == 0

# 中文數字字元集，供生日與地址 pattern 共用
CN_NUM = r"[一二三四五六七八九十百零〇0-9]"

PATTERNS = {
    PIIType.ID_NUMBER: re.compile(r"\b[A-Z][12]\d{8}\b"),
    PIIType.MOBILE: re.compile(r"09\d{2}[-\s]?\d{3}[-\s]?\d{3}"),
    PIIType.PHONE: re.compile(r"\(?0[2-8]\)?[-\s]?\d{3,4}[-\s]?\d{4}"),
    PIIType.EMAIL: re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),

    # 生日：三種格式
    # 1. 西元年：1980/07/15、1980-07-15、1980年7月15日
    # 2. 民國年＋阿拉伯數字：民國75年3月20日
    # 3. 民國年＋中文數字：民國七十五年三月二十日
    # 注意：「民國XX年度」這類公文慣用語不會被抓（因為後面沒有月日）
    # 已知限制：「填表日期：2026年3月10日」這種西元日期格式無法與生日區分，
    #           會一併被遮蔽，屬於設計上的保守策略（交由 LLM 層補充判斷）
    PIIType.DATE: re.compile(
        r"(19|20)\d{2}[/\-年]\d{1,2}[月/\-]\d{1,2}日?"
        rf"|民國\s?\d{{1,3}}\s?年\s?\d{{1,2}}\s?月\s?\d{{1,2}}\s?日"
        rf"|民國\s?{CN_NUM}{{1,4}}\s?年\s?{CN_NUM}{{1,3}}\s?月\s?{CN_NUM}{{1,3}}\s?日"
    ),

    # 地址：抓「路街名＋段巷弄號樓」核心片段
    # 設計原則：以「號」為必要錨點，避免「XX路線」「XX街道計畫」等誤判
    # 已知限制：縣市鄉鎮區等前綴（台北市、中正區）無法用正則可靠區分，
    #           交由 LLM 層補抓，兩層合併後可覆蓋完整地址
    PIIType.ADDRESS: re.compile(
        r"[\u4e00-\u9fa5]{2,10}"                       # 路街名稱（中文字 2-10 字）
        r"(路|街|大道|林蔭道)"                           # 路街類型（必要）
        rf"({CN_NUM}{{1,3}}段)?"                        # 段（可選，支援中文/阿拉伯數字）
        r"(\d{1,4}巷)?"                                 # 巷（可選）
        r"(\d{1,4}弄)?"                                 # 弄（可選）
        r"\d{1,4}號"                                    # 號（必要）
        rf"(\d{{1,3}}樓)?"                              # 樓（可選）
        rf"(\d{{1,3}}室)?"                              # 室（可選）
    ),
}

def detect(text: str) -> list[PIIMatch]:
    matches = []
    for pii_type, pattern in PATTERNS.items():
        for m in pattern.finditer(text):
            if pii_type == PIIType.ID_NUMBER and not validate_tw_id(m.group()):
                continue
            matches.append(PIIMatch(
                text=m.group(),
                pii_type=pii_type,
                start=m.start(),
                end=m.end(),
                confidence=0.99,
                source="regex",
                context=text[max(0, m.start()-15):m.end()+15],
            ))
    return matches