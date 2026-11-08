"""Provider contract tests with a local stub, no network calls."""
import asyncio

import httpx
from app.translation import translate


def test_local_ollama_translation_provider(monkeypatch):
    monkeypatch.setenv('OLLAMA_MODEL', 'mock:1b')
    monkeypatch.setenv('TRANSLATION_PROVIDER', 'ollama')
    monkeypatch.setenv('OLLAMA_URL', 'http://localhost:11434')
    original = httpx.AsyncClient

    def handler(request):
        assert request.url.path == '/api/generate'
        assert request.method == 'POST'
        return httpx.Response(200, json={'response':'Hello from a local model.'})

    def fake_client(*args, **kwargs):
        kwargs['transport'] = httpx.MockTransport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, 'AsyncClient', fake_client)
    result = asyncio.run(translate('မင်္ဂလာပါ', 'my', 'en'))
    assert result['translated_text'] == 'Hello from a local model.'
    assert result['provider'].startswith('Ollama:')
