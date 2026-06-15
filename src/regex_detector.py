import re
from src.config import PIIMatch, PIIType

# 台灣身分證檢查碼驗證
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

PATTERNS = {
    PIIType.ID_NUMBER: re.compile(r"\b[A-Z][12]\d{8}\b"),
    PIIType.MOBILE: re.compile(r"09\d{2}[-\s]?\d{3}[-\s]?\d{3}"),
    PIIType.PHONE: re.compile(r"0[2-8][-\s]?\d{4}[-\s]?\d{4}"),
    PIIType.EMAIL: re.compile(r"[\w\.-]+@[\w\.-]+\.\w+"),
    PIIType.BIRTHDAY: re.compile(
        r"(19|20)\d{2}[/\-年]\d{1,2}[/\-月]\d{1,2}日?"
        r"|民國\s?\d{1,3}\s?年\s?\d{1,2}\s?月\s?\d{1,2}\s?日"
    ),
}

def detect(text: str) -> list[PIIMatch]:
    matches = []
    for pii_type, pattern in PATTERNS.items():
        for m in pattern.finditer(text):
            # 身分證額外驗證檢查碼
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