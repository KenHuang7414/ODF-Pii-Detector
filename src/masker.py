from odfdo import Document
from src.config import PIIMatch, MASK_STRATEGIES
from src.odt_io import TextSegment

def apply_masks(
    doc: Document,
    segments: list[TextSegment],
    matches: list[PIIMatch],
    strategy: str = "block",
) -> Document:
    mask_fn = MASK_STRATEGIES[strategy]

    for seg in segments:
        seg_end = seg.global_start + len(seg.text)
        seg_matches = [
            m for m in matches
            if seg.global_start <= m.start < seg_end
        ]
        if not seg_matches:
            continue

        new_text = seg.text
        for m in sorted(seg_matches, key=lambda x: x.start, reverse=True):
            local_start = m.start - seg.global_start
            local_end = m.end - seg.global_start
            replacement = mask_fn(m.text, m.pii_type)
            new_text = new_text[:local_start] + replacement + new_text[local_end:]

        # NOTE: MVP limitation — flatten the paragraph to a single text node.
        # The original text_recursive already encoded <text:line-break/> as "\n"
        # and <text:tab/> as "\t" into new_text, but child elements (spans,
        # line breaks, tabs) must be removed BEFORE setting .text, otherwise
        # odfdo duplicates content (old children + new text both present).
        # Cost: per-run styling/line-break structure within this paragraph
        # is lost. Future improvement: splice masks into the span tree to
        # preserve formatting. See README "樣式保留改進".
        for child in list(seg.element.children):
            seg.element.delete(child)
        seg.element.text = new_text

    return doc
def mask_text(text: str, matches: list[PIIMatch], strategy: str = "label") -> str:
    """
    對純文字字串套用遮蔽，不碰 .odt 結構。
    用於「送給 LLM 之前」的預處理，避免明文 PII 流出。
    """
    mask_fn = MASK_STRATEGIES[strategy]
    new_text = text
    # 從後往前替換，避免位置偏移影響後面的替換
    for m in sorted(matches, key=lambda x: x.start, reverse=True):
        replacement = mask_fn(m.text, m.pii_type)
        new_text = new_text[:m.start] + replacement + new_text[m.end:]
    return new_text