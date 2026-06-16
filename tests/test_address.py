import re

CN_NUM = r"[一二三四五六七八九十百零〇0-9]"

pattern = re.compile(
    r"[\u4e00-\u9fa5]{2,10}"
    r"(路|街|大道|林蔭道)"
    rf"({CN_NUM}{{1,3}}段)?"
    r"(\d{1,4}巷)?"
    r"(\d{1,4}弄)?"
    r"\d{1,4}號"
    rf"(\d{{1,3}}樓)?"
    rf"(\d{{1,3}}室)?"
)

tests = [
    # 正例
    ("台北市中正區重慶南路一段122號5樓",   True),
    ("高雄市左營區明誠二路78號3樓",        True),
    ("台中市北區三民路三段129號",          True),
    ("忠孝東路四段100號",                 True),
    ("中山北路一段3巷5弄12號2樓",         True),
    ("信義路五段7號10樓301室",            True),

    # 反例
    ("依據教育部113年度科學教育推動計畫辦理", False),
    ("本案經費預算表已檢附",               False),
    ("府教字第1130012345號",              False),  # 公文字號含「號」
    ("全國中學生科學競賽",                 False),
    ("鐵路計畫第三期工程",                 False),
]

print("=" * 60)
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
print("=" * 60)
print("全部通過！" if all_pass else "有失敗案例，請檢查 pattern")