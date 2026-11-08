"""Stateless image OCR and translation API. No uploaded data is persisted."""
from __future__ import annotations

from io import BytesIO
import secrets
import os
import time
import threading
from collections import deque, defaultdict
from starlette.concurrency import run_in_threadpool
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image

from .ocr import OCRUnavailable, recognize_local, recognize_cloud, supported_languages
from .preprocess import ImageInputError, load_image, MAX_BYTES
from .documents import PDFInputError, pdf_to_images, MAX_PDF_PAGES
from .translation import TranslationUnavailable, translate
from .budget import begin_job, end_job, check_budget

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title='Myan OCR API', version='0.1.3', docs_url='/api/docs', redoc_url=None)
app.mount('/assets', StaticFiles(directory=ROOT/'web'), name='web-assets')

# In-process, local-development protection. A public deployment also requires an
# authenticating reverse proxy and a shared/central rate limiter across workers.
_OCR_CAPACITY = max(1, min(int(os.getenv('OCR_MAX_CONCURRENT', '2')), 8))
_OCR_SLOTS = threading.BoundedSemaphore(_OCR_CAPACITY)
_TRANSLATION_SLOTS = threading.BoundedSemaphore(2)
_RATE_LOCK = threading.Lock()
_HITS: dict[str, deque] = defaultdict(deque)
_RATE_WINDOW = 60
_RATE_LIMIT = max(1, int(os.getenv('API_REQUESTS_PER_MINUTE', '30')))
_MAX_CLIENT_BUCKETS = 4096
_ALLOWED_LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1', 'testserver'}


def _rate_allowed(key: str) -> bool:
    now = time.monotonic()
    with _RATE_LOCK:
        # Evict expired buckets before creating another key. A hostile client
        # cannot grow the in-memory dictionary without bound.
        if key not in _HITS and len(_HITS) >= _MAX_CLIENT_BUCKETS:
            for old_key in list(_HITS):
                values = _HITS[old_key]
                if not values or values[-1] <= now - _RATE_WINDOW:
                    _HITS.pop(old_key, None)
            if len(_HITS) >= _MAX_CLIENT_BUCKETS:
                return False
        q = _HITS[key]
        while q and q[0] <= now - _RATE_WINDOW:
            q.popleft()
        if len(q) >= _RATE_LIMIT:
            return False
        q.append(now)
        return True


def _api_authorized(request: Request) -> bool:
    key = os.getenv('MYAN_OCR_API_KEY', '').strip()
    if key:
        return secrets.compare_digest(request.headers.get('x-api-key', ''), key)
    # Explicit local-only mode; never infer authorization from the Host header
    # alone. Docker Compose binds the development application to loopback.
    if os.getenv('MYAN_OCR_LOCAL_DEV', '0') != '1':
        return False
    return request.url.hostname in _ALLOWED_LOCAL_HOSTS


def _host_allowed(request: Request) -> bool:
    allow = {h.strip().lower() for h in os.getenv('MYAN_OCR_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',') if h.strip()}
    return (request.url.hostname or '').lower() in allow


# Small defense in depth on image upload size. A reverse proxy should also cap body size.
@app.middleware('http')
async def response_security(request: Request, call_next):
    if not _host_allowed(request):
        return JSONResponse({'detail': 'Host is not allowed.'}, status_code=400)
    if request.url.path.startswith('/api/') and request.method == 'POST':
        # Browser same-origin or non-browser API key. Reject cross-origin form submissions.
        origin = request.headers.get('origin')
        if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail': 'Cross-origin API requests are not allowed.'}, status_code=403)
        if not _api_authorized(request):
            return JSONResponse({'detail': 'API key required.'}, status_code=401)
        host = request.client.host if request.client else 'unknown'
        # Never trust forwarded-for headers from the open internet.
        if not _rate_allowed(host):
            return JSONResponse({'detail': 'Too many requests; retry later.'}, status_code=429, headers={'Retry-After': '60'})
    if request.url.path.startswith('/api/') and request.headers.get('content-length'):
        try:
            if int(request.headers['content-length']) > MAX_BYTES + 100000:
                return JSONResponse({'detail': 'Request exceeds 12 MB image limit.'}, status_code=413)
        except ValueError:
            return JSONResponse({'detail': 'Invalid Content-Length.'}, status_code=400)
    budget_token = begin_job() if request.url.path in ('/api/ocr', '/api/batch', '/api/pdf') and request.method == 'POST' else None
    try:
        response = await call_next(request)
    finally:
        if budget_token is not None:
            end_job(budget_token)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response


@app.get('/')
async def home():
    return FileResponse(ROOT/'web'/'index.html')


@app.get('/api/health')
async def health():
    languages = supported_languages()
    return {'version': '0.1.3', 'ocr_available': 'mya' in languages and 'eng' in languages,
            'languages': languages, 'cloud_ocr_configured': bool(os.getenv('GOOGLE_CLOUD_API_KEY')),
            'translation_configured': bool(os.getenv('GOOGLE_CLOUD_API_KEY') or os.getenv('OLLAMA_MODEL')),
            'provider_status': 'configured_not_verified', 'translation_provider': ('ollama' if os.getenv('OLLAMA_MODEL') and os.getenv('TRANSLATION_PROVIDER','auto')!='google' else ('google' if os.getenv('GOOGLE_CLOUD_API_KEY') else 'none')),
            'max_upload_mb': 12, 'job_deadline_seconds': int(os.getenv('OCR_JOB_DEADLINE_SECONDS', '75')), 'max_pdf_pages': MAX_PDF_PAGES, 'storage': 'none'}


@app.post('/api/ocr')
async def ocr(file: UploadFile = File(...), language: str = Form('both'),
              mode: str = Form('accurate'), engine: str = Form('local'), rotate: int = Form(0)):
    if language not in ('my', 'en', 'both') or mode not in ('fast', 'balanced', 'accurate') or engine not in ('local', 'cloud'):
        raise HTTPException(status_code=422, detail='Invalid OCR settings.')
    payload = await file.read(MAX_BYTES+1)
    await file.close()
    try:
        image = load_image(payload, rotate)
    except ImageInputError as exc:
        raise HTTPException(status_code=400 if len(payload)<=MAX_BYTES else 413, detail=str(exc)) from exc
    result = await _recognize(image, language, mode, engine)
    result['image'] = {'width': image.width, 'height': image.height}
    result['detected_language'] = detect_script(result['text'])
    result['needs_review'] = True  # Confidence is never proof of exact OCR.
    result['timestamp'] = int(time.time())
    return result


async def _recognize(image: Image.Image, language: str, mode: str, engine: str) -> dict:
    if not _OCR_SLOTS.acquire(blocking=False):
        raise HTTPException(status_code=503, detail='OCR server is busy; retry shortly.')
    try:
        try:
            if engine == 'cloud':
                return await recognize_cloud(image, language)
            return await run_in_threadpool(recognize_local, image, language, mode)
        except OCRUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except TimeoutError as exc:
            raise HTTPException(status_code=504, detail=str(exc)) from exc
    finally:
        _OCR_SLOTS.release()


@app.post('/api/batch')
async def image_batch(files: list[UploadFile] = File(...), language: str = Form('both'),
                      mode: str = Form('balanced'), engine: str = Form('local')):
    if language not in ('my', 'en', 'both') or mode not in ('fast', 'balanced', 'accurate') or engine not in ('local', 'cloud'):
        raise HTTPException(status_code=422, detail='Invalid OCR settings.')
    if not 1 <= len(files) <= 4:
        raise HTTPException(status_code=422, detail='Batch accepts 1–4 images.')
    if not _OCR_SLOTS.acquire(blocking=False):
        raise HTTPException(status_code=503, detail='OCR server is busy; retry shortly.')
    try:
        outputs = []
        total_bytes = 0
        for index, file in enumerate(files):
            try: check_budget()
            except TimeoutError as exc: raise HTTPException(status_code=504, detail=str(exc)) from exc
            payload = await file.read(min(MAX_BYTES + 1, MAX_BYTES - total_bytes + 1))
            await file.close()
            total_bytes += len(payload)
            if total_bytes > MAX_BYTES:
                raise HTTPException(status_code=413, detail='Batch exceeds 12 MB total.')
            try:
                image = load_image(payload)
            except ImageInputError as exc:
                raise HTTPException(status_code=400, detail=f'Image {index + 1}: {exc}') from exc
            try:
                result = await recognize_cloud(image, language) if engine == 'cloud' else await run_in_threadpool(recognize_local, image, language, mode)
            except OCRUnavailable as exc:
                raise HTTPException(status_code=503, detail=f'Image {index + 1}: {exc}') from exc
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=f'Image {index + 1}: {exc}') from exc
            outputs.append({'page': index + 1, 'text': result['text'],
                            'confidence': result['confidence'], 'detected_language': detect_script(result['text'])})
        text = '\n\n'.join(f'--- Image {row["page"]} ---\n{row["text"]}' for row in outputs)
        return {'engine': engine, 'text': text, 'pages': outputs, 'page_count': len(outputs),
                'detected_language': detect_script(text), 'confidence': None, 'lines': [], 'alternatives': [],
                'variant': 'Batch images', 'needs_review': True,
                'note': 'Review every image. Server does not store input or output.'}
    finally:
        _OCR_SLOTS.release()


@app.post('/api/pdf')
async def pdf_ocr(file: UploadFile = File(...), language: str = Form('both'),
                  mode: str = Form('balanced'), engine: str = Form('local')):
    if language not in ('my', 'en', 'both') or mode not in ('fast', 'balanced', 'accurate') or engine not in ('local', 'cloud'):
        raise HTTPException(status_code=422, detail='Invalid OCR settings.')
    if not _OCR_SLOTS.acquire(blocking=False):
        raise HTTPException(status_code=503, detail='OCR server is busy; retry shortly.')
    try:
        payload = await file.read(MAX_BYTES + 1)
        await file.close()
        try:
            pages = await run_in_threadpool(pdf_to_images, payload)
        except PDFInputError as exc:
            raise HTTPException(status_code=400 if len(payload) <= MAX_BYTES else 413, detail=str(exc)) from exc
        except TimeoutError as exc:
            raise HTTPException(status_code=504, detail=str(exc)) from exc
        outputs = []
        for index, image in enumerate(pages):
            try: check_budget()
            except TimeoutError as exc: raise HTTPException(status_code=504, detail=str(exc)) from exc
            try:
                result = await recognize_cloud(image, language) if engine == 'cloud' else await run_in_threadpool(recognize_local, image, language, mode)
            except OCRUnavailable as exc:
                raise HTTPException(status_code=503, detail=f'Page {index + 1}: {exc}') from exc
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=f'Page {index + 1}: {exc}') from exc
            outputs.append({'page': index + 1, 'text': result['text'],
                            'confidence': result['confidence'], 'detected_language': detect_script(result['text'])})
        text = '\n\n'.join(f'--- Page {row["page"]} ---\n{row["text"]}' for row in outputs)
        return {'engine': engine, 'text': text, 'pages': outputs, 'page_count': len(outputs),
                'detected_language': detect_script(text), 'confidence': None, 'lines': [], 'alternatives': [],
                'variant': 'PDF document', 'needs_review': True,
                'note': 'Review every page against the source PDF. Page images and text are not stored.'}
    finally:
        _OCR_SLOTS.release()


def detect_script(text: str) -> str:
    my = sum('\u1000' <= c <= '\u109f' or '\uaa60' <= c <= '\uaa7f' for c in text)
    en = sum(c.isascii() and c.isalpha() for c in text)
    if my and en: return 'my+en'
    if my: return 'my'
    if en: return 'en'
    return 'undetermined'


class TranslationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    source: str = 'my'
    target: str = 'en'


@app.post('/api/translate')
async def translation(body: TranslationRequest):
    if not _TRANSLATION_SLOTS.acquire(blocking=False):
        raise HTTPException(status_code=503, detail='Translator is busy; retry shortly.')
    try:
        try:
            return await translate(body.text, body.source, body.target)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except TranslationUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        _TRANSLATION_SLOTS.release()
