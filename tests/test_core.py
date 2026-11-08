"""Pure functions, request validation, and API smoke tests."""
from io import BytesIO
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app, detect_script
from app.preprocess import load_image, variants, ImageInputError
from app.ocr import _rank, _line_boxes, supported_languages
from app.translation import translate, TranslationUnavailable

client = TestClient(app)


def sample_png(width=400, height=150):
    im = Image.new('RGB', (width, height), 'white')
    out = BytesIO(); im.save(out, 'PNG')
    return out.getvalue()


def test_status():
    r = client.get('/api/health')
    assert r.status_code == 200
    assert r.json()['version'] == '0.1.3'
    assert r.headers['x-content-type-options'] == 'nosniff'
    assert r.headers['cache-control'] == 'no-store'


def test_home():
    r=client.get('/')
    assert r.status_code == 200
    assert 'Myan OCR' in r.text
    assert 'Developed by' in r.text


def test_detect_language():
    assert detect_script('မင်္ဂလာပါ') == 'my'
    assert detect_script('Hello') == 'en'
    assert detect_script('Hello မြန်မာ') == 'my+en'
    assert detect_script('123') == 'undetermined'


def test_load_dimensions():
    im=load_image(sample_png(90,40), 90)
    assert im.size==(40,90)


def test_invalid_images():
    with pytest.raises(ImageInputError): load_image(b'')
    with pytest.raises(ImageInputError): load_image(b'not an image')
    with pytest.raises(ImageInputError): load_image(sample_png(), 45)
    with pytest.raises(ImageInputError): load_image(b'0'*(12*1024*1024+1))


def test_variants():
    img=Image.new('RGB',(200,100),'white')
    assert len(variants(img,'fast'))==1
    assert len(variants(img,'balanced'))==2
    assert len(variants(img,'accurate'))==4
    with pytest.raises(ValueError): variants(img,'ultra')


def test_rank_language():
    assert _rank(65,'မြန်မာစာ','my') > _rank(65,'abcdef','my')
    assert _rank(65,'english','en') > _rank(65,'12345','en')
    assert _rank(0,'','en')<0


def test_line_boxes():
    d={'text':['မင်္ဂလာပါ','Hello'], 'conf':['79.5','84.2'],'left':[10,100],
       'top':[20,20],'width':[80,65],'height':[25,25], 'page_num':[1,1],
       'block_num':[1,1],'par_num':[1,1],'line_num':[1,1]}
    lines,score=_line_boxes(d,200,100)
    assert len(lines)==1 and 'Hello' in lines[0]['text']
    assert round(score,1)==81.8
    assert lines[0]['box']['x']==.05


def test_api_reject_wrong_image():
    r=client.post('/api/ocr',files={'file':('bad.png',b'not image','image/png')})
    assert r.status_code==400


def test_api_reject_unsupported_settings():
    r=client.post('/api/ocr',data={'mode':'ultra'},files={'file':('x.png',sample_png(),'image/png')})
    assert r.status_code==422


def test_translation_needs_key(monkeypatch):
    monkeypatch.delenv('GOOGLE_CLOUD_API_KEY',raising=False)
    r=client.post('/api/translate',json={'text':'မင်္ဂလာပါ','source':'my','target':'en'})
    assert r.status_code==503
    assert 'not configured' in r.json()['detail']


def test_translation_input_limits():
    r=client.post('/api/translate',json={'text':'x'*10001,'source':'my','target':'en'})
    assert r.status_code==422
    r=client.post('/api/translate',json={'text':'test','source':'my','target':'my'})
    assert r.status_code==422


def test_cloud_requires_key(monkeypatch):
    monkeypatch.delenv('GOOGLE_CLOUD_API_KEY',raising=False)
    r=client.post('/api/ocr',data={'engine':'cloud'},files={'file':('x.png',sample_png(),'image/png')})
    assert r.status_code==503


def test_local_ocr_if_installed():
    if not {'mya','eng'}.issubset(set(supported_languages())):
        pytest.skip('Tesseract language packages not installed')
    r=client.post('/api/ocr',data={'engine':'local','mode':'fast','language':'my'},
                  files={'file':('blank.png',sample_png(),'image/png')})
    assert r.status_code==200
    assert r.json()['engine']=='local'
    assert r.json()['image']['width']==400
    assert r.json()['confidence']>=0
