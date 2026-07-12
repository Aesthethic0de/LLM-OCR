from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .ocr import extract_document
from .pdf_utils import render_pdf_to_png_pages
from .schemas import OcrResult

app = FastAPI(title="OCR-Free Backend", version="0.1.0")

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

IMAGE_CONTENT_TYPES = {
    "image/png": "image/png",
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
}
PDF_CONTENT_TYPE = "application/pdf"


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "ocr_base_url": settings.ocr_base_url,
        "ocr_model_name": settings.ocr_model_name,
    }


@app.post("/api/ocr/process", response_model=OcrResult)
async def process_document(file: UploadFile = File(...)) -> OcrResult:
    if not file.filename:
        raise HTTPException(status_code=422, detail="Uploaded file is missing a filename")

    content_type = file.content_type or ""
    max_bytes = settings.max_upload_mb * 1024 * 1024
    body = await file.read()

    if len(body) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(body) > max_bytes:
        raise HTTPException(
            status_code=413, detail=f"File exceeds the {settings.max_upload_mb}MB limit"
        )

    if content_type == PDF_CONTENT_TYPE or file.filename.lower().endswith(".pdf"):
        pages = render_pdf_to_png_pages(body, max_pages=settings.max_pdf_pages)
        images = [(page, "image/png") for page in pages]
    elif content_type in IMAGE_CONTENT_TYPES:
        images = [(body, IMAGE_CONTENT_TYPES[content_type])]
    else:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Please upload a PDF, PNG, or JPEG file.",
        )

    return extract_document(settings, images, document_name=file.filename)
