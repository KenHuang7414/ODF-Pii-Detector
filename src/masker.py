from odfdo import Document
from src.config import PIIMatch, MASK_STRATEGIES
from src.odt_io import TextSegment

_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_LINE_BREAK_TAG = f"{{{_TEXT_NS}}}line-break"
_TAB_TAG = f"{{{_TEXT_NS}}}tab"


def _walk_text_nodes(el, cursor=0):
    """走訪 lxml element，產生跟 text_recursive 對齊的位置映射"""
    nodes = []
    if el.text:
        nodes.append((cursor, cursor + len(el.text), el, 'text'))
        cursor += len(el.text)
    for child in el:
        tag = child.tag
        if tag == _LINE_BREAK_TAG or tag == _TAB_TAG:
            nodes.append((cursor, cursor + 1, None, None))
            cursor += 1
        else:
            sub_nodes, cursor = _walk_text_nodes(child, cursor)
            nodes.extend(sub_nodes)
        if child.tail:
            nodes.append((cursor, cursor + len(child.tail), child, 'tail'))
            cursor += len(child.tail)
    return nodes, cursor


def _deduplicate(matches: list[PIIMatch]) -> list[PIIMatch]:
    """
    去除重疊的 match，重疊時保留範圍較大的那一筆。
    例：「教育部」和「教育部113年度科學教育推動計畫」重疊，保留後者。
    """
    if not matches:
        return matches
    # 依「範圍大→start 小」排序，優先選範圍大的
    sorted_m = sorted(matches, key=lambda m: (-(m.end - m.start), m.start))
    kept = []
    for m in sorted_m:
        overlap = any(not (m.end <= k.start or m.start >= k.end) for k in kept)
        if not overlap:
            kept.append(m)
    return sorted(kept, key=lambda m: m.start)


def apply_masks(
    doc: Document,
    segments: list[TextSegment],
    matches: list[PIIMatch],
    strategy: str = "block",
) -> Document:
    mask_fn = MASK_STRATEGIES[strategy]
    # 先去除重疊
    matches = _deduplicate(matches)

    for seg in segments:
        seg_end = seg.global_start + len(seg.text)
        seg_matches = [
            m for m in matches
            if seg.global_start <= m.start < seg_end
        ]
        if not seg_matches:
            continue

        el = seg.element._xml_element

        # 一次性算出節點佈局（基於原始 seg.text）
        nodes, _ = _walk_text_nodes(el)

        # 為每個 match 預先算好「要寫到哪個 holder/attr，rel_start, rel_end, replacement」
        # 由於去重後 match 不會重疊，所以可以批次處理
        # 對每個 holder/attr 分別收集要替換的區段
        # key = id(holder)+attr, value = (holder, attr, [(rel_start, rel_end, replacement), ...])
        pending = {}

        for m in seg_matches:
            local_start = m.start - seg.global_start
            local_end = m.end - seg.global_start
            replacement = mask_fn(m.text, m.pii_type)

            # 找出 match 跨越的可寫節點
            affected_writable = []
            for n_start, n_end, holder, attr in nodes:
                if holder is None:
                    continue
                overlap_start = max(local_start, n_start)
                overlap_end = min(local_end, n_end)
                if overlap_start >= overlap_end:
                    continue
                rel_start = overlap_start - n_start
                rel_end = overlap_end - n_start
                affected_writable.append((n_start, holder, attr, rel_start, rel_end))

            if not affected_writable:
                continue

            # 把 replacement 寫到最後一個 affected 節點（從後往前的第一個）
            # 前面的節點把 match 範圍內的內容清空
            for i, (n_start, holder, attr, rel_start, rel_end) in enumerate(affected_writable):
                key = (id(holder), attr)
                if key not in pending:
                    pending[key] = (holder, attr, [])
                is_last = (i == len(affected_writable) - 1)
                if is_last:
                    pending[key][2].append((rel_start, rel_end, replacement))
                else:
                    pending[key][2].append((rel_start, rel_end, ""))

        # 對每個文字節點，從後往前套用替換
        for key, (holder, attr, edits) in pending.items():
            val = getattr(holder, attr)
            for rel_start, rel_end, replacement in sorted(edits, key=lambda x: x[0], reverse=True):
                val = val[:rel_start] + replacement + val[rel_end:]
            setattr(holder, attr, val)

    return doc


def mask_text(text: str, matches: list[PIIMatch], strategy: str = "label") -> str:
    """對純文字字串套用遮蔽，用於送 LLM 之前的預處理"""
    mask_fn = MASK_STRATEGIES[strategy]
    matches = _deduplicate(matches)
    new_text = text
    for m in sorted(matches, key=lambda x: x.start, reverse=True):
        replacement = mask_fn(m.text, m.pii_type)
        new_text = new_text[:m.start] + replacement + new_text[m.end:]
    return new_text