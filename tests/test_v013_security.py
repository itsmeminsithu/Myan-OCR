"""v0.1.3 regression tests; all network calls are intercepted."""
import asyncio
from io import BytesIO
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.ocr import OCRUnavailable, recognize_cloud
from app.budget import begin_job, end_job, check_budget, remaining_seconds
from app.documents import pdf_to_images, PDFInputError


def tiny_image():
    return Image.new('RGB', (40, 30), 'white')


def test_remote_host_denied_even_with_dev_mode(monkeypatch):
    monkeypatch.setenv('MYAN_OCR_LOCAL_DEV', '1')
    with TestClient(app) as c:
        r = c.post('/api/ocr', headers={'host': 'evil.example'}, files={'file': ('a.png', b'x', 'image/png')})
    assert r.status_code == 400


def test_public_mode_requires_key(monkeypatch):
    monkeypatch.setenv('MYAN_OCR_LOCAL_DEV', '0')
    monkeypatch.delenv('MYAN_OCR_API_KEY', raising=False)
    with TestClient(app) as c:
        assert c.post('/api/ocr', files={'file': ('a.png', b'x', 'image/png')}).status_code == 401


def test_public_mode_valid_key(monkeypatch):
    monkeypatch.setenv('MYAN_OCR_LOCAL_DEV', '0')
    monkeypatch.setenv('MYAN_OCR_API_KEY', 'long-secret')
    with TestClient(app) as c:
        response = c.post('/api/ocr', headers={'x-api-key': 'long-secret'}, files={'file': ('a.png', b'bad', 'image/png')})
    assert response.status_code == 400  # authenticated; input invalid


@pytest.mark.parametrize('bad_data', [
    None, [], 'bad', {}, {'responses': None}, {'responses': []},
    {'responses': {}}, {'responses': [None]}, {'responses': ['x']},
    {'responses': [{'fullTextAnnotation': 'bad'}]},
    {'responses': [{'fullTextAnnotation': {'text': 123}}]},
    {'responses': [{'fullTextAnnotation': {'pages': 'x'}}]},
])
def test_cloud_malformed_envelope_is_controlled(monkeypatch, bad_data):
    monkeypatch.setenv('GOOGLE_CLOUD_API_KEY', 'fake-test-key')
    real = httpx.AsyncClient

    def transport(req):
        return httpx.Response(200, json=bad_data)

    def factory(*args, **kwargs):
        kwargs['transport'] = httpx.MockTransport(transport)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, 'AsyncClient', factory)
    with pytest.raises(OCRUnavailable):
        asyncio.run(recognize_cloud(tiny_image(), 'my'))


def test_cloud_provider_error_is_sanitized(monkeypatch):
    monkeypatch.setenv('GOOGLE_CLOUD_API_KEY', 'fake-test-key')
    real = httpx.AsyncClient
    def factory(*args, **kwargs):
        kwargs['transport'] = httpx.MockTransport(lambda request: httpx.Response(200, json={
            'responses': [{'error': {'code': 403, 'message': 'secret document metadata'}}]}))
        return real(*args, **kwargs)
    monkeypatch.setattr(httpx, 'AsyncClient', factory)
    with pytest.raises(OCRUnavailable) as exc:
        asyncio.run(recognize_cloud(tiny_image(), 'my'))
    assert '403' in str(exc.value)
    assert 'secret document metadata' not in str(exc.value)


def test_expired_job_budget(monkeypatch):
    import app.budget as budget
    token = budget._DEADLINE.set(0.0)
    try:
        with pytest.raises(TimeoutError):
            check_budget()
    finally:
        budget._DEADLINE.reset(token)


def test_pdf_pixel_budget_definition():
    from app.documents import MAX_DOCUMENT_PIXELS, MAX_PDF_PAGES
    assert MAX_DOCUMENT_PIXELS <= MAX_PDF_PAGES * 4_000_000


def test_health_discloses_configured_not_tested():
    with TestClient(app) as c:
        r = c.get('/api/health')
    assert r.status_code == 200
    assert r.json()['provider_status'] == 'configured_not_verified'
