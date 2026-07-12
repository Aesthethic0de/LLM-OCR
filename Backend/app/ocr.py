import base64
import json
import re

import openai
from fastapi import HTTPException
from pydantic import ValidationError

from .config import Settings
from .schemas import ExtractedField, LineItem, OcrResult

SYSTEM_PROMPT = (
    "You are a document OCR assistant. You will be shown one or more images that together "
    "make up a single document (e.g. an invoice, receipt, form, or statement). Read the "
    "document carefully and respond with ONLY a single JSON object (no markdown fences, no "
    "commentary) matching this shape:\n"
    "{\n"
    '  "raw_text": string,\n'
    '  "line_items": [{"description": string, "quantity": string, "amount": string}],\n'
    '  "overall_confidence": number 0-100\n'
    "}\n"
    '"raw_text" is the most important field: transcribe the ENTIRE document verbatim. If the '
    "document has side-by-side columns or blocks at the same height (e.g. a \"BILL TO\" "
    "block next to a \"SHIP TO\" block, next to an \"INVOICE #\" details block), transcribe "
    "ONE block completely, top to bottom, before moving to the next block to its right - do "
    "NOT read across columns line by line, and do NOT interleave their lines together. Keep "
    "each block's heading directly above its own lines only.\n"
    '"line_items" should contain any tabular product/service row data if present, otherwise '
    "an empty array. "
    "If a value is unclear, make your best estimate and lower overall_confidence."
)

TEXT_FIELDS_PROMPT = (
    "You are a data-extraction assistant. You will be given the raw transcribed text of a "
    "single scanned document (invoice, receipt, form, or statement) - not an image, just its "
    "plain-text transcription. Convert it into ONE JSON object, with no markdown fences or "
    "commentary, matching this shape:\n"
    "{\n"
    '  "fields": [{"label": string, "value": string}],\n'
    '  "line_items": [{"description": string, "quantity": string, "amount": string}]\n'
    "}\n"
    "Read the whole text first, then extract EVERY distinct labeled field as its own entry in "
    '"fields" - never merge two different sections or headings into one value, even if the '
    "text runs them together with no blank line in between. But when a heading's own block "
    "spans several lines (name, street, city/state/zip), join ALL of those lines into that "
    "one field's value (comma-separated) - do not cut it short after just the first line.\n"
    "Specifically look for and extract, whenever present:\n"
    "- Invoice/document number, issue date, due date, PO number, payment terms\n"
    "- Bill From: the company/sender issuing the document. This is often unlabeled - it is "
    "usually the company name and address near the very top, before any \"BILL TO\" heading. "
    "Extract it as \"Bill From\" even if the text never says that.\n"
    "- Bill To: the billed customer's full name AND address block, stopping as soon as the "
    "next heading (Ship To, Invoice #, Date, etc.) begins.\n"
    "- Ship To: the full shipping address block, if present, stopping at the next heading.\n"
    "- Subtotal, tax (with its rate if shown), total, amount due, balance due, and any other "
    "totals - whatever format they're written in (a colon, a pipe, or just a space before the "
    "number) - each as its own field with just the label and its number. These are easy to "
    "miss when there's no colon or pipe, so check every line near the bottom of the document "
    "for a label followed only by a space and a number.\n"
    "- Any other clearly labeled value in the text not covered above.\n"
    '"line_items" should contain the tabular product/service rows if present (each row\'s '
    'description, quantity, and line amount), otherwise an empty array. Do not duplicate row '
    'data as "fields".\n\n'
    "Example input text:\n"
    "INVOICE\n"
    "Acme Supplies\n"
    "500 Market St, Denver, CO 80202\n"
    "BILL TO\n"
    "Jane Doe\n"
    "12 Elm St, Boulder, CO 80301\n"
    "SHIP TO\n"
    "Jane Doe Warehouse\n"
    "88 Pine Ave, Boulder, CO 80301\n"
    "INVOICE #\n"
    "A-100\n"
    "DATE\n"
    "01/05/2024\n"
    "QTY DESCRIPTION PRICE AMOUNT\n"
    "2 Widget 10.00 20.00\n"
    "Subtotal 20.00\n"
    "Tax 8% 1.60\n"
    "TOTAL $21.60\n\n"
    "Example output:\n"
    "{\n"
    '  "fields": [\n'
    '    {"label": "Bill From", "value": "Acme Supplies, 500 Market St, Denver, CO 80202"},\n'
    '    {"label": "Bill To", "value": "Jane Doe, 12 Elm St, Boulder, CO 80301"},\n'
    '    {"label": "Ship To", "value": "Jane Doe Warehouse, 88 Pine Ave, Boulder, CO 80301"},\n'
    '    {"label": "Invoice #", "value": "A-100"},\n'
    '    {"label": "Date", "value": "01/05/2024"},\n'
    '    {"label": "Subtotal", "value": "20.00"},\n'
    '    {"label": "Tax 8%", "value": "1.60"},\n'
    '    {"label": "Total", "value": "$21.60"}\n'
    "  ],\n"
    '  "line_items": [{"description": "Widget", "quantity": "2", "amount": "20.00"}]\n'
    "}\n"
    "Now do the same for the real document text you are given below."
)


def _image_to_data_uri(image_bytes: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _parse_model_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise HTTPException(status_code=502, detail="OCR model returned a non-JSON response")


_HEADING_ALIASES = {
    "bill to": "Bill To",
    "invoice to": "Bill To",
    "customer": "Bill To",
    "sold to": "Bill To",
    "bill from": "Bill From",
    "from": "Bill From",
    "vendor": "Bill From",
    "ship to": "Ship To",
    "shipping to": "Ship To",
    "deliver to": "Ship To",
}
_GENERIC_TITLE_RE = re.compile(
    r"^(invoice|receipt|statement|bill|purchase order|quote|estimate)s?$", re.IGNORECASE
)
_ITEM_ROW_RE = re.compile(r"^\d+\s+\S")
_KEY_VALUE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 /.#()%]{1,40})\s*[|:]\s*(.+)$")
_TOTAL_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 %()./#-]*?)\s+(\$?\d[\d,]*\.\d{2})$")


def _normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", label).strip().rstrip(":").strip().lower()


def _backfill_fields_from_raw_text(
    fields: list[ExtractedField],
    raw_text: str | None,
    default_confidence: float | None = None,
) -> list[ExtractedField]:
    """Recover fields (billing parties, totals) present in raw_text but dropped by the model."""
    if not raw_text:
        return fields

    blocks = [
        [line.strip() for line in block.splitlines() if line.strip()]
        for block in re.split(r"\n\s*\n", raw_text.strip())
    ]
    blocks = [block for block in blocks if block]

    has_recipient_heading = any(
        _HEADING_ALIASES.get(_normalize_label(block[0])) in {"Bill To", "Ship To"}
        for block in blocks
    )

    existing_labels = {_normalize_label(field.label) for field in fields}
    backfilled: list[ExtractedField] = []

    for index, lines in enumerate(blocks):
        heading_key = _normalize_label(lines[0])
        if heading_key in _HEADING_ALIASES:
            label = _HEADING_ALIASES[heading_key]
            norm = _normalize_label(label)
            if norm not in existing_labels:
                value = ", ".join(lines[1:]) if len(lines) > 1 else lines[0]
                if value:
                    backfilled.append(
                        ExtractedField(label=label, value=value, confidence=default_confidence)
                    )
                    existing_labels.add(norm)
            continue

        if index == 0 and has_recipient_heading and "bill from" not in existing_labels:
            content = lines[1:] if _GENERIC_TITLE_RE.match(heading_key) else lines
            value = ", ".join(content)
            if value:
                backfilled.append(
                    ExtractedField(label="Bill From", value=value, confidence=default_confidence)
                )
                existing_labels.add("bill from")
            continue

        if any(_ITEM_ROW_RE.match(line) for line in lines):
            continue  # this block is the line-items table, already captured separately

        for line in lines:
            match = _KEY_VALUE_RE.match(line) or _TOTAL_LINE_RE.match(line)
            if not match:
                continue
            label, value = match.group(1).strip(), match.group(2).strip()
            norm = _normalize_label(label)
            if norm in existing_labels or norm in {"p", "f"}:
                continue
            backfilled.append(
                ExtractedField(label=label, value=value, confidence=default_confidence)
            )
            existing_labels.add(norm)

    return fields + backfilled


def _extract_fields_from_text(
    client: openai.OpenAI,
    settings: Settings,
    raw_text: str,
    default_confidence: float | None,
) -> tuple[list[ExtractedField], list[LineItem]]:
    """Run a focused text-only pass that converts raw_text into structured fields."""
    try:
        response = client.chat.completions.create(
            model=settings.ocr_model_name,
            messages=[
                {"role": "system", "content": TEXT_FIELDS_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            temperature=0.0,
            max_tokens=2048,
        )
    except openai.OpenAIError:
        return [], []

    content = response.choices[0].message.content or ""
    try:
        parsed = _parse_model_json(content)
    except HTTPException:
        return [], []

    try:
        fields = [
            ExtractedField(
                label=field["label"].strip().rstrip(":").strip(),
                value=field["value"],
                confidence=default_confidence,
            )
            for field in parsed.get("fields", [])
        ]
        line_items = [LineItem(**item) for item in parsed.get("line_items", [])]
    except ValidationError:
        return [], []

    return fields, line_items


def extract_document(
    settings: Settings,
    images: list[tuple[bytes, str]],
    document_name: str,
) -> OcrResult:
    """Send page images to the OCR vision model and parse structured extraction."""
    client = openai.OpenAI(
        base_url=settings.ocr_base_url,
        api_key=settings.ocr_api_key,
        timeout=settings.ocr_request_timeout,
    )

    content: list[dict] = [
        {
            "type": "text",
            "text": f"Extract the structured data from this {len(images)}-page document.",
        }
    ]
    for image_bytes, mime_type in images:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": _image_to_data_uri(image_bytes, mime_type)},
            }
        )

    try:
        response = client.chat.completions.create(
            model=settings.ocr_model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            temperature=0.0,
            max_tokens=4096,
        )
    except openai.APIConnectionError as exc:
        raise HTTPException(
            status_code=503, detail="Could not reach the OCR model server"
        ) from exc
    except openai.APITimeoutError as exc:
        raise HTTPException(status_code=504, detail="OCR model request timed out") from exc
    except openai.APIStatusError as exc:
        raise HTTPException(
            status_code=502, detail=f"OCR model server error: {exc.message}"
        ) from exc

    raw_content = response.choices[0].message.content or ""
    parsed = _parse_model_json(raw_content)

    try:
        line_items = [LineItem(**item) for item in parsed.get("line_items", [])]
        raw_text = parsed.get("raw_text")
        overall_confidence = parsed.get("overall_confidence")

        fields: list[ExtractedField] = []
        if raw_text:
            fields, text_line_items = _extract_fields_from_text(
                client, settings, raw_text, overall_confidence
            )
            if not line_items:
                line_items = text_line_items
        fields = _backfill_fields_from_raw_text(fields, raw_text, overall_confidence)

        return OcrResult(
            document_name=document_name,
            page_count=len(images),
            overall_confidence=overall_confidence,
            fields=fields,
            line_items=line_items,
            raw_text=raw_text,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=502, detail="OCR model returned a malformed extraction"
        ) from exc
