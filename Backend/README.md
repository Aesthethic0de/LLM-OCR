# OCR-Free Backend

FastAPI backend that accepts a PDF/PNG/JPEG upload, converts PDF pages to
images if needed, and sends the page image(s) to an Ollama-hosted vision
language model (default: `qwen2.5vl:7b`) for structured data extraction.

> Ollama serves models GGUF-quantized by default, so the 7B model only
> needs ~6GB VRAM — comfortable on a ~12GB GPU. If you want a smaller
> footprint, `qwen2.5vl:3b` works too. The backend talks to any
> OpenAI-compatible chat completions endpoint, so vLLM or another server
> works as a drop-in replacement — just change `OCR_BASE_URL` /
> `OCR_MODEL_NAME` in `.env`.

## Setup

```bash
cd Backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # then edit OCR_BASE_URL / OCR_MODEL_NAME if needed
```

## Run

Make sure Ollama is installed (https://ollama.com) and pull the model:

```bash
ollama pull qwen2.5vl:7b
```

Ollama runs as a background service on `http://localhost:11434` once
installed — no extra step needed to "start" it. Verify it's up with:

```bash
curl http://localhost:11434/v1/models
```

Then start the backend:

```bash
uvicorn app.main:app --reload --port 8080
```

The frontend (Vite dev server on `http://localhost:5173`) is preconfigured
in `.env.example` under `CORS_ORIGINS`.

## API

### `POST /api/ocr/process`

Multipart form upload with a single `file` field (`.pdf`, `.png`, `.jpg`, `.jpeg`).

Response:

```json
{
  "document_name": "invoice.pdf",
  "page_count": 1,
  "overall_confidence": 97.8,
  "fields": [{"label": "Invoice number", "value": "INV-2048", "confidence": 99}],
  "line_items": [{"description": "...", "quantity": "1", "amount": "$1,200.00"}],
  "raw_text": "..."
}
```

### `GET /api/health`

Returns backend status plus the configured OCR model base URL and name.
