import io

import pypdfium2 as pdfium
from fastapi import HTTPException


def render_pdf_to_png_pages(pdf_bytes: bytes, max_pages: int, scale: float = 2.0) -> list[bytes]:
    """Rasterize each page of a PDF to PNG bytes so a vision model can read it."""
    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
    except pdfium.PdfiumError as exc:
        raise HTTPException(status_code=422, detail="Could not read PDF file") from exc

    page_count = len(pdf)
    if page_count == 0:
        raise HTTPException(status_code=422, detail="PDF has no pages")

    pages_to_render = min(page_count, max_pages)
    images: list[bytes] = []
    for index in range(pages_to_render):
        page = pdf[index]
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        images.append(buffer.getvalue())
        page.close()
    pdf.close()
    return images
