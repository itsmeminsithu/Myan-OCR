from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_frontend_components():
    html=(ROOT/'web/index.html').read_text()
    js=(ROOT/'web/app.js').read_text()
    for item in ['cameraModal','takePhoto','dropzone','filePicker','scanButton','ocrOverlay','extractedText','translatedText','translateButton','downloadText']:
        assert f'id="{item}"' in html
    assert 'getUserMedia' in js
    assert 'FormData' in js
    assert "textContent" in js
    assert 'innerHTML' not in js

def test_no_exposed_key():
    text=(ROOT/'web/app.js').read_text()+(ROOT/'web/index.html').read_text()
    assert 'GOOGLE_CLOUD_API_KEY' not in text
    assert 'api/ocr' in text
