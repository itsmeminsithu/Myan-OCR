# Security and privacy

Myan OCR v0.1.3 is a local development application. It has not passed a production security audit.

## Local use

- Docker Compose publishes `127.0.0.1:8388` only. Keep this loopback binding for local use.
- `MYAN_OCR_LOCAL_DEV=1` explicitly enables no-key POSTs for local hostnames; **never expose this mode through a public proxy**. A Host header is not proof of client origin.
- Without local mode, all API POSTs require `X-API-Key: <MYAN_OCR_API_KEY>`. The bundled browser UI does not contain API credentials; production requires a secured first-party session/BFF or reverse proxy. Do not embed keys in public JavaScript.
- Allowed HTTP hostnames are controlled by `MYAN_OCR_ALLOWED_HOSTS`. Cross-origin POSTs are rejected. These checks do not replace authenticated ingress controls.
- The single-process in-memory rate limit and OCR semaphore are defense in depth, not distributed protection. Configure proxy request size caps, shared quotas, TLS, provider quotas and billing alerts for public deployment.

## Images, PDF and timeouts

- Images and PDFs are processed in memory; the backend does not intentionally write uploaded images or extracted text to persistent storage.
- Single upload and batch request totals are limited to 12 MiB. Images are limited to 16 megapixels. PDFs are limited to 8 pages, 4 megapixels/page and 20 megapixels total.
- A cooperative 75-second job budget is checked between OCR passes and PDF pages; per-Tesseract subprocess timeouts and Docker CPU/memory limits provide additional containment. **This is not a hard preemption guarantee for native PDF rendering.**
- Google Vision/Translation requests are explicit and send document content/text to Google; an Ollama translation sends text to its configured server. Do not submit sensitive documents without authorization.
- Google credentials must remain in `.env` on the backend, never in the browser or Git.

## Local browser history

- The user may explicitly save recognized text and translation to browser `localStorage`. No history is saved unless Save History is selected.
- This browser history remains after closing the tab and may be accessible to other users of the same browser profile. Clear saved history on shared devices. Backend deletion does not clear local browser history.
- OCR confidence is not a verified accuracy rate. OCR output must be reviewed against the source, especially Myanmar combining marks and older fonts.
