from odfdo import Document
from src.config import PIIMatch, MASK_STRATEGIES
from src.odt_io import TextSegment

# ODF text 命名空間
_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_LINE_BREAK_TAG = f"{{{_TEXT_NS}}}line-break"
_TAB_TAG = f"{{{_TEXT_NS}}}tab"


def _walk_text_nodes(el, cursor=0, is_root=True):
    """
    深度遍歷 lxml element，產生跟 text_recursive 完全對齊的位置映射。
    回傳 (list of nodes, next_cursor)
      每個 node = (start, end, holder, attr)
        - holder + attr 非 None: 可寫入的文字節點
        - holder is None: line-break / tab 的虛擬字元，不可寫入
    """
    nodes = []

    if el.text:
        nodes.append((cursor, cursor + len(el.text), el, 'text'))
        cursor += len(el.text)

    for child in el:
        tag = child.tag
        if tag == _LINE_BREAK_TAG:
            # text_recursive 把它變成 '\n'，占 1 字元
            nodes.append((cursor, cursor + 1, None, None))
            cursor += 1
        elif tag == _TAB_TAG:
            # text_recursive 把它變成 '\t'，占 1 字元
            nodes.append((cursor, cursor + 1, None, None))
            cursor += 1
        else:
            # span 等內嵌元素，遞迴進去
            sub_nodes, cursor = _walk_text_nodes(child, cursor, is_root=False)
            nodes.extend(sub_nodes)

        if child.tail:
            nodes.append((cursor, cursor + len(child.tail), child, 'tail'))
            cursor += len(child.tail)

    return nodes, cursor


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

        el = seg.element._xml_element

        # 換算到段落內的相對位置
        local_matches = [
            (m.start - seg.global_start, m.end - seg.global_start, m)
            for m in seg_matches
        ]

        # 從後往前替換，避免前面的替換影響後面 match 的位置
        for local_start, local_end, m in sorted(
            local_matches, key=lambda x: x[0], reverse=True
        ):
            replacement = mask_fn(m.text, m.pii_type)

            # 每次替換前重新計算節點佈局（因前一次替換可能改變了文字長度）
            nodes, _ = _walk_text_nodes(el)

            # 找出 match 跨越的所有節點
            affected = []
            for n_start, n_end, holder, attr in nodes:
                overlap_start = max(local_start, n_start)
                overlap_end = min(local_end, n_end)
                if overlap_start >= overlap_end:
                    continue
                affected.append((n_start, n_end, holder, attr, overlap_start, overlap_end))

            if not affected:
                continue

            # 從後往前寫入：最後一個被 match 涵蓋的可寫節點放完整 replacement
            # 其餘節點把 match 範圍內的內容清空
            replacement_written = False
            for n_start, n_end, holder, attr, o_start, o_end in reversed(affected):
                if holder is None:
                    # line-break/tab，保留結構不動
                    continue
                rel_start = o_start - n_start
                rel_end = o_end - n_start
                val = getattr(holder, attr)
                if not replacement_written:
                    new_val = val[:rel_start] + replacement + val[rel_end:]
                    replacement_written = True
                else:
                    new_val = val[:rel_start] + val[rel_end:]
                setattr(holder, attr, new_val)

    return doc


def mask_text(text: str, matches: list[PIIMatch], strategy: str = "label") -> str:
    """
    對純文字字串套用遮蔽，不碰 .odt 結構。
    用於「送給 LLM 之前」的預處理，避免明文 PII 流出。
    """
    mask_fn = MASK_STRATEGIES[strategy]
    new_text = text
    for m in sorted(matches, key=lambda x: x.start, reverse=True):
        replacement = mask_fn(m.text, m.pii_type)
        new_text = new_text[:m.start] + replacement + new_text[m.end:]
    return new_text