from odfdo import Document, Header, Paragraph, Table, Row, Cell
from collections import Counter
from src.config import PIIMatch

def build_report(matches: list[PIIMatch], source_filename: str) -> Document:
    doc = Document("text")
    body = doc.body
    body.clear()
    
    body.append(Header(1, "PII 偵測報告"))
    body.append(Paragraph(f"來源檔案：{source_filename}"))
    body.append(Paragraph(f"總計偵測：{len(matches)} 筆"))
    
    body.append(Header(2, "類型統計"))
    counter = Counter(m.pii_type.value for m in matches)
    for t, c in counter.most_common():
        body.append(Paragraph(f"• {t}: {c} 筆"))
    
    body.append(Header(2, "逐項列表"))
    table = Table("detections")
    table.append_row(Row())
    header_row = table.get_row(0)
    for h in ["#", "類型", "原文", "信心度", "來源"]:
        header_row.append_cell(Cell(h))
    
    for i, m in enumerate(matches, 1):
        row = Row()
        row.append_cell(Cell(str(i)))
        row.append_cell(Cell(m.pii_type.value))
        row.append_cell(Cell(m.text))
        row.append_cell(Cell(f"{m.confidence:.2f}"))
        row.append_cell(Cell(m.source))
        table.append_row(row)
    
    body.append(table)
    return doc