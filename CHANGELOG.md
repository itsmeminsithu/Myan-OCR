# Changelog

## 0.1.3 — 2026-11-08

### Fixed

- Require explicit local-development mode for unauthenticated POST requests and enforce allowed Host headers.
- Validate Google Vision and Translation provider responses and handle malformed responses.
- Correct crop coordinates against the displayed image and handle missing canvas support.
- Fix pytest import-path configuration.

### Changed

- Add cooperative OCR job deadlines, a total PDF pixel budget and Docker resource limits.
- Distinguish configured cloud credentials from verified provider access.
- Update security documentation and pin Python dependencies.
- Add authentication, provider-response and resource-budget regression tests.

### Limitations

- OCR recognition still requires manual review.
- Real Google API calls, production proxy security and physical mobile camera tests are unverified.
- Native PDF rendering is not covered by a hard cancellation deadline.

## 0.1.2 — 2026-11-08

### Added

- PDF OCR for up to eight pages and batch recognition for up to four images.
- Optional browser-local text history, saved only on request.
- PDF validation, total request limits, rate-limit bucket cap and cross-origin POST checks.

## 0.1.1 — 2026-11-08

### Fixed

- Preserve Myanmar text spacing using OCR token geometry rather than joining every token with a space.
- Reduce OCR candidate ranking bias toward long text and sparse layouts.
- Support Myanmar-to-English and English-to-Myanmar translation directions.
- Improve JPEG orientation handling and image crop validation.

### Added

- Per-process request throttling, concurrent-job limits and optional server API key.
- Review-required recognition status independent of engine confidence.

## 0.1.0 — 2026-11-08

### Added

- Browser camera capture and image upload.
- Myanmar and English OCR through Tesseract, with optional Cloud Vision.
- Text editing, copy/export, alternative recognition results and text bounding boxes.
- Optional Cloud Translation and Ollama translation.
- FastAPI endpoints, Docker setup, tests and benchmark scripts.
