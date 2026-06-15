from odfdo import Document, Paragraph
from dataclasses import dataclass

@dataclass
class TextSegment:
    """一段純文字 + 它在 ODT element tree 中的位置"""
    text: str
    element: any           # odfdo element 參考
    global_start: int      # 在合併文字中的起始位置

def extract_text(doc: Document) -> tuple[str, list[TextSegment]]:
    """走訪所有段落，回傳 (合併純文字, 段落清單)"""
    segments = []
    cursor = 0
    full_text = []
    
    body = doc.body
    for elem in body.get_elements("//text:p | //text:h"):
        text = elem.text_recursive or ""
        if not text:
            continue
        segments.append(TextSegment(
            text=text,
            element=elem,
            global_start=cursor,
        ))
        full_text.append(text)
        cursor += len(text) + 1   # +1 for 段落分隔
    
    return "\n".join(full_text), segments

def save(doc: Document, path: str):
    doc.save(path)

def load(path: str) -> Document:
    return Document(path)