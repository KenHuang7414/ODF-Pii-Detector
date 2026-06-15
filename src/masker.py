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
    
    # 把 matches 依段落分組
    for seg in segments:
        seg_end = seg.global_start + len(seg.text)
        seg_matches = [
            m for m in matches
            if seg.global_start <= m.start < seg_end
        ]
        if not seg_matches:
            continue
        
        # 從後往前替換避免位置偏移
        new_text = seg.text
        for m in sorted(seg_matches, key=lambda x: x.start, reverse=True):
            local_start = m.start - seg.global_start
            local_end = m.end - seg.global_start
            replacement = mask_fn(m.text, m.pii_type)
            new_text = new_text[:local_start] + replacement + new_text[local_end:]
        
        # 替換 element 內文（注意：這會丟失段內 span 樣式，MVP 階段可接受）
        seg.element.text = new_text
        # 清掉子元素以避免重複
        for child in list(seg.element.children):
            seg.element.delete(child)
    
    return doc