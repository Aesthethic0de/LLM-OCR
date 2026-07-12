from pydantic import BaseModel


class ExtractedField(BaseModel):
    label: str
    value: str
    confidence: float | None = None


class LineItem(BaseModel):
    description: str
    quantity: str = ""
    amount: str = ""


class OcrResult(BaseModel):
    document_name: str
    page_count: int
    overall_confidence: float | None = None
    fields: list[ExtractedField] = []
    line_items: list[LineItem] = []
    raw_text: str | None = None
