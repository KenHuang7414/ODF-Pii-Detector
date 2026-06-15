from pathlib import Path
from src import odt_io, regex_detector, llm_detector, masker, reporter
from src.config import PIIMatch

def remap_to_original(llm_matches: list[PIIMatch], full_text: str) -> list[PIIMatch]:
    remapped = []
    for m in llm_matches:
        idx = full_text.find(m.text)
        if idx == -1:
            continue
        remapped.append(PIIMatch(
            text=m.text,
            pii_type=m.pii_type,
            start=idx,
            end=idx + len(m.text),
            confidence=m.confidence,
            source=m.source,
            context=m.context,
        ))
    return remapped


def run(
    input_path: str,
    output_dir: str = "outputs",
    strategy: str = "block",
    use_llm: bool = True,
    max_validation_rounds: int = 2,
) -> dict:
    Path(output_dir).mkdir(exist_ok=True)
    input_name = Path(input_path).stem

    print(f"[1/5] 讀取 {input_path}")
    doc = odt_io.load(input_path)
    full_text, segments = odt_io.extract_text(doc)

    print(f"[2/5] 正則掃描")
    regex_matches = regex_detector.detect(full_text)
    print(f"      → 找到 {len(regex_matches)} 筆")
    # Debug
    safe_text = masker.mask_text(full_text, regex_matches, strategy="label")
    print(safe_text[:400])

    llm_matches = []
    if use_llm:
        # === 新增：送給 Claude 前，先把正則找到的高敏感資訊換成 placeholder ===
        safe_text = masker.mask_text(full_text, regex_matches, strategy="label")

        print(f"[3/5] Claude 掃描（已遮蔽身分證/電話/Email 等高敏感欄位）")
        llm_matches_raw = llm_detector.detect(safe_text)
        # === 新增：把位置對應回原始文字 ===
        llm_matches = remap_to_original(llm_matches_raw, full_text)
        print(f"      → 找到 {len(llm_matches)} 筆")

    all_matches = llm_detector.merge(regex_matches, llm_matches)
    print(f"[4/5] 合併後共 {len(all_matches)} 筆，套用遮蔽")

    masked_doc = masker.apply_masks(doc, segments, all_matches, strategy)
    masked_path = f"{output_dir}/{input_name}_masked.odt"
    odt_io.save(masked_doc, masked_path)

    # 自我驗證 loop（不變，因為這裡讀的本來就是已遮蔽的 masked.odt，
    # 不存在明文 PII 外洩的問題）
    if use_llm:
        for round_n in range(1, max_validation_rounds + 1):
            print(f"[驗證 round {round_n}] 重新檢查遮蔽結果")
            verify_doc = odt_io.load(masked_path)
            verify_text, verify_segs = odt_io.extract_text(verify_doc)
            residual = llm_detector.detect(verify_text)
            residual = [m for m in residual if "█" not in m.text and "○" not in m.text]
            if not residual:
                print(f"      → 通過")
                break
            print(f"      → 仍有 {len(residual)} 筆殘留，二次遮蔽")
            verify_doc = masker.apply_masks(verify_doc, verify_segs, residual, strategy)
            odt_io.save(verify_doc, masked_path)
            all_matches.extend(residual)

    print(f"[5/5] 產出報告")
    report = reporter.build_report(all_matches, Path(input_path).name)
    report_path = f"{output_dir}/{input_name}_report.odt"
    odt_io.save(report, report_path)

    return {
        "input": input_path,
        "masked": masked_path,
        "report": report_path,
        "total_matches": len(all_matches),
    }