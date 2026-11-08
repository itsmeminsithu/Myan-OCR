"""v0.1.1 correctness and abuse limits; tests do not call external services."""
import asyncio
import json
from io import BytesIO

import httpx
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app, _rate_allowed, _HITS, _RATE_LOCK
from app.ocr import _line_boxes, _rank
from app.translation import translate


def _ocr_data(tokens, x, width):
    return {'text':tokens,'conf':['87']*len(tokens),'left':x,'top':[20]*len(tokens),
            'width':width,'height':[20]*len(tokens),'page_num':[1]*len(tokens),
            'block_num':[1]*len(tokens),'par_num':[1]*len(tokens),'line_num':[1]*len(tokens)}


def test_myanmar_adjacent_tokens_no_spurious_space():
    data=_ocr_data(['မြန်','မာစာ'],[0,25],[25,30]); lines,_=_line_boxes(data,300,100)
    assert lines[0]['text']=='မြန်မာစာ'


def test_myanmar_real_gap_preserved():
    data=_ocr_data(['မြန်မာ','စာ'],[0,90],[55,20]); lines,_=_line_boxes(data,300,100)
    assert lines[0]['text']=='မြန်မာ စာ'


def test_english_words_spaced():
    data=_ocr_data(['Hello','world'],[0,52],[50,48]); lines,_=_line_boxes(data,300,100)
    assert lines[0]['text']=='Hello world'


def test_rank_does_not_reward_length():
    assert _rank(82,'မြန်မာ','my') == _rank(82,'မြန်မာမြန်မာမြန်မာ','my')


def test_ollama_prompt_both_directions(monkeypatch):
    seen=[]
    real=httpx.AsyncClient
    def handler(request):
        payload=json.loads(request.content)
        seen.append(payload['prompt'])
        return httpx.Response(200,json={'response':'result'})
    def fake(*args,**kwargs):
        kwargs['transport']=httpx.MockTransport(handler)
        return real(*args,**kwargs)
    monkeypatch.setenv('OLLAMA_MODEL','fake')
    monkeypatch.setenv('TRANSLATION_PROVIDER','ollama')
    monkeypatch.setattr(httpx,'AsyncClient',fake)
    asyncio.run(translate('မင်္ဂလာပါ','my','en'))
    asyncio.run(translate('Hello','en','my'))
    assert 'into English' in seen[0]
    assert 'into Myanmar (Burmese, Unicode)' in seen[1]


def test_api_auth_is_opt_in(monkeypatch):
    monkeypatch.setenv('MYAN_OCR_API_KEY','a-secure-test-key')
    with TestClient(app) as c:
        assert c.post('/api/translate',json={'text':'x'}).status_code==401
        assert c.post('/api/translate',headers={'x-api-key':'wrong'},json={'text':'x'}).status_code==401
    monkeypatch.delenv('MYAN_OCR_API_KEY',raising=False)


def test_rate_limiter():
    key='test-v011-special'
    with _RATE_LOCK:
        _HITS.pop(key,None)
    for _ in range(30):
        assert _rate_allowed(key)
    assert not _rate_allowed(key)
    with _RATE_LOCK:
        _HITS.pop(key,None)


def test_api_review_flag_not_accuracy_claim(monkeypatch):
    from app import main
    monkeypatch.setattr(main,'recognize_local',lambda *args,**kwargs:{'engine':'local','text':'မြန်မာ','lines':[], 'confidence':99.9,'variant':'mock','alternatives':[]})
    img=Image.new('RGB',(50,50),'white'); out=BytesIO();img.save(out,format='PNG')
    with TestClient(app) as c:
        r=c.post('/api/ocr',files={'file':('x.png',out.getvalue(),'image/png')},data={'mode':'fast'})
    assert r.status_code==200
    assert r.json()['needs_review'] is True


def test_client_translation_controls_in_source():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    html=(root/'web/index.html').read_text()
    js=(root/'web/app.js').read_text()
    for control in ('translateSource','translateTarget','swapLanguages'):
        assert f'id="{control}"' in html
    assert 'source,target' in js
    assert 'syncTranslationDirection()' in js
