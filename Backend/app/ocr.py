import base64
import json
import re

import openai
from fastapi import HTTPException
from pydantic import ValidationError

from .config import Settings
from .schemas import ExtractedField, LineItem, OcrResult

SYSTEM_PROMPT = (
    "You are a document OCR and data-extraction assistant. You will be shown one or more "
    "images that together make up a single document (e.g. an invoice, receipt, form, or "
    "statement). Read the document carefully and respond with ONLY a single JSON object "
    "(no markdown fences, no commentary) matching this shape:\n"
    "{\n"
    '  "raw_text": string,\n'
    '  "fields": [{"label": string, "value": string, "confidence": number 0-100}],\n'
    '  "line_items": [{"description": string, "quantity": string, "amount": string}],\n'
    '  "overall_confidence": number 0-100\n'
    "}\n"
    'Fill "raw_text" first: transcribe the ENTIRE document verbatim, top to bottom, before '
    'writing anything else. Then derive "fields" and "line_items" from that transcription '
    "so nothing gets missed.\n"
    '"fields" must list every labeled field on the document, in the order they appear. '
    "Extract ALL of the following, check each one individually, and include every one that "
    "appears anywhere on the document (in a table, a plain text block, a logo header, or a "
    "callout) - do not skip any of them just because there are many:\n"
    "- Invoice / document number\n"
    "- Invoice / issue date\n"
    "- Due date\n"
    "- PO number\n"
    "- Payment terms\n"
    "- Name of rep / contact person, contact phone\n"
    "- Bill From: the company sending the invoice. This is almost never labeled - it is "
    "the company name, address, phone, and logo printed near the top of the page, separate "
    "from the Bill To block. Extract it as \"Bill From\" even with no label.\n"
    "- Bill To: the customer being billed, usually labeled Bill To / Invoice To / Customer.\n"
    "- Ship To: a separate shipping address block, usually labeled Ship To / Shipping To, "
    "if one exists.\n"
    "- Subtotal, tax, amount due, grand total, and any other totals\n"
    "- Any other labeled field or form value not listed above\n"
    "For Bill From, Bill To, and Ship To, capture the whole block (name, address, phone, "
    "email) as one field value. "
    '"line_items" should contain any tabular row data if present, otherwise an empty array. '
    "If a value is unclear, make your best estimate and lower its confidence score."
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
            match = _KEY_VALUE_RE.match(line)
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
        fields = [ExtractedField(**field) for field in parsed.get("fields", [])]
        line_items = [LineItem(**item) for item in parsed.get("line_items", [])]
        raw_text = parsed.get("raw_text")
        overall_confidence = parsed.get("overall_confidence")
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
