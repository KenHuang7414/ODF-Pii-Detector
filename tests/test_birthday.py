import re

CN_NUM = r"[一二三四五六七八九十百零〇0-9]"

pattern = re.compile(
    r"(19|20)\d{2}[/\-年]\d{1,2}[月/\-]\d{1,2}日?"
    rf"|民國\s?\d{{1,3}}\s?年\s?\d{{1,2}}\s?月\s?\d{{1,2}}\s?日"
    rf"|民國\s?{CN_NUM}{{1,4}}\s?年\s?{CN_NUM}{{1,3}}\s?月\s?{CN_NUM}{{1,3}}\s?日"
)

tests = [
    # 正例：應該要抓到
    ("民國七十五年三月二十日",       True),
    ("民國一一三年五月十五日",       True),
    ("民國75年3月20日",             True),
    ("民國091年09月09日",           True),
    ("1980/07/15",                 True),
    ("1980-07-15",                 True),
    ("1980年7月15日",               True),
    ("1980年07月15日",              True),
    ("出生日期為民國九十八年八月八日", True),

    # 反例：不應該抓到
    ("民國113年度科學教育推動計畫",   False),
    ("依據教育部113年度辦理",        False),
    ("本計畫自民國110年起實施",       False),
    ("填表日期：2026年3月10日",      False),  # 邊界案例
]

print("=" * 55)
all_pass = True
for text, should_match in tests:
    m = pattern.search(text)
    matched = m.group() if m else None
    ok = (matched is not None) == should_match
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    label = "正例" if should_match else "反例"
    print(f"[{status}] {label} | {text!r}")
    if matched:
        print(f"       抓到: {matched!r}")
print("=" * 55)
print("全部通過！" if all_pass else "有失敗案例，請檢查 pattern")