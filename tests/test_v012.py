"""v0.1.2 regressions for PDF, batch and browser-facing API behavior."""
from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
import fitz

from app.main import app, _rate_allowed, _HITS, _RATE_LOCK
from app.documents import pdf_to_images, PDFInputError

client = TestClient(app)


def png():
    img=Image.new('RGB',(120,80),'white')
    b=BytesIO();img.save(b, format='PNG');return b.getvalue()


def pdf(pages=2):
    doc=fitz.open()
    for i in range(pages):
        page=doc.new_page(width=260,height=180)
        page.insert_text((25,50),f'Hello page {i + 1}')
    data=doc.tobytes();doc.close();return data


def fake_ocr(image, lang, mode):
    return {'text': 'မင်္ဂလာပါ', 'confidence': 75.0, 'lines': [], 'alternatives': [], 'variant': 'fake', 'engine':'local'}


def test_pdf_rasterization():
    pages=pdf_to_images(pdf(2))
    assert len(pages)==2
    assert all(x.width>100 and x.height>50 for x in pages)


def test_pdf_rejects_invalid():
    import pytest
    with pytest.raises(PDFInputError):pdf_to_images(b'not pdf')
    with pytest.raises(PDFInputError):pdf_to_images(pdf(9))


def test_pdf_api_with_mocked_ocr():
    with patch('app.main.recognize_local', side_effect=fake_ocr):
        resp=client.post('/api/pdf',data={'language':'my','mode':'fast'},files={'file':('doc.pdf',pdf(2),'application/pdf')})
    assert resp.status_code==200,resp.text
    data=resp.json()
    assert data['page_count']==2 and len(data['pages'])==2
    assert '--- Page 2 ---' in data['text']
    assert data['needs_review'] is True


def test_image_batch_with_mocked_ocr():
    with patch('app.main.recognize_local', side_effect=fake_ocr):
        resp=client.post('/api/batch',data={'language':'my','mode':'fast'},files=[('files',('a.png',png(),'image/png')),('files',('b.png',png(),'image/png'))])
    assert resp.status_code==200, resp.text
    assert resp.json()['page_count']==2
    assert '--- Image 2 ---' in resp.json()['text']


def test_batch_rejects_too_many_files():
    entries=[('files',(f'{i}.png',png(),'image/png')) for i in range(5)]
    response=client.post('/api/batch',files=entries)
    assert response.status_code==422


def test_cross_origin_rejected():
    response=client.post('/api/translate',headers={'Origin':'https://attacker.example'},json={'text':'Hi','source':'en','target':'my'})
    assert response.status_code==403


def test_local_health_version():
    response=client.get('/api/health')
    assert response.status_code==200
    assert response.json()['max_pdf_pages']==8
    assert response.json()['version']=='0.1.3'


def test_malformed_pdf():
    response=client.post('/api/pdf',files={'file':('bad.pdf',b'%PDF-corrupt','application/pdf')})
    assert response.status_code==400
