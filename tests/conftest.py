import pytest

@pytest.fixture(autouse=True)
def local_test_mode(monkeypatch):
    # TestClient uses a non-network transport. Production's default is key-required.
    monkeypatch.setenv('MYAN_OCR_LOCAL_DEV', '1')
    monkeypatch.setenv('MYAN_OCR_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver')
