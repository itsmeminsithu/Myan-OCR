"""Bounded rasterization of local PDF uploads. No OCR of encrypted PDFs."""
from io import BytesIO

from PIL import Image
from .preprocess import MAX_BYTES
from .budget import check_budget

MAX_PDF_PAGES = 8
MAX_PAGE_PIXELS = 4_000_000
MAX_DOCUMENT_PIXELS = 20_000_000

class PDFInputError(ValueError):
    pass


def pdf_to_images(payload: bytes) -> list[Image.Image]:
    if not payload or len(payload) > MAX_BYTES:
        raise PDFInputError('PDF is empty or exceeds the 12 MB upload limit.')
    if not payload.startswith(b'%PDF-'):
        raise PDFInputError('Upload a valid PDF file.')
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(payload)
        if not 1 <= len(pdf) <= MAX_PDF_PAGES:
            raise PDFInputError(f'PDF must have 1–{MAX_PDF_PAGES} pages.')
        pages = []
        total_pixels = 0
        try:
            for i in range(len(pdf)):
                check_budget()
                page = pdf[i]
                try:
                    # Target ~170 dpi but never allow huge raster surfaces.
                    width, height = page.get_size()
                    if width <= 0 or height <= 0:
                        raise PDFInputError(f'Invalid page dimensions: {i + 1}.')
                    scale = min(170 / 72, (MAX_PAGE_PIXELS / (width * height)) ** .5)
                    bitmap = page.render(scale=scale)
                    image = bitmap.to_pil().convert('RGB')
                    total_pixels += image.width * image.height
                    if total_pixels > MAX_DOCUMENT_PIXELS:
                        image.close()
                        raise PDFInputError('PDF exceeds the total raster pixel budget.')
                    pages.append(image)
                    check_budget()
                    bitmap.close()
                finally:
                    page.close()
        finally:
            pdf.close()
        return pages
    except (PDFInputError, TimeoutError):
        raise
    except Exception as exc:
        raise PDFInputError('PDF could not be read (invalid, encrypted or unsupported).') from exc
