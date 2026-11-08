# Myan OCR

Image-to-text recognition for printed Myanmar and English. The web interface supports camera capture, image upload, PDF pages, batch images, text correction and optional translation.

**Version:** 0.1.3  
**Developed by Min SiThu** — https://minsithu.org

## Live preview — try it in your browser

**https://itsmeminsithu.github.io/Myan-OCR/**

A working demo that runs Tesseract OCR (Tesseract.js, `mya` + `eng`) entirely in your browser — upload an image or use the bundled sample, and the extracted text appears on the page. Your image never leaves your device.

This demo is not the full app. The full app runs on the Python/FastAPI backend in this repo and adds PDF pages, batch images, camera/crop tools, detected-text boxes, editable results with history, and optional translation. OCR quality can differ between the demo and the backend. There is no Codespaces preview.

## Features

- Tesseract OCR with Fast, Balanced and Accurate processing modes
- Optional Google Cloud Vision recognition
- Camera capture, photo upload, paste, crop and rotation
- PDF recognition (up to 8 pages) and image batch recognition (up to 4 images)
- Editable results, detected text boxes and alternate OCR output
- Optional Myanmar ↔ English translation through Google Cloud or Ollama
- Text export and opt-in browser-local text history

## Requirements

- Docker Desktop for the packaged Mac setup, or Python 3 with Tesseract and `mya`/`eng` language data
- Google Cloud project, enabled APIs, credentials and billing only for cloud functions
- Ollama and a compatible local model only for Ollama translation

## Run on Mac

Extract the source ZIP to Downloads, then run:

```bash
cd "$HOME/Downloads/Myan-OCR-v0.1.3"
./scripts/start-mac.sh
```

Open http://localhost:8388. Stop the application with `docker compose down` from the project directory. See [Mac setup](docs/START-MAC-MY.md) for native Python instructions and camera permissions.

## Cloud configuration

Copy the environment template and enter credentials only on the backend:

```bash
cp .env.example .env
# Edit .env and set GOOGLE_CLOUD_API_KEY
# Enable the relevant Google Cloud APIs and billing first
docker compose up -d --build
```

Cloud Vision and Translation are optional and explicitly requested by the user. The app does not verify billing or API access merely because a key is present. Do not expose `.env` or embed credentials in browser JavaScript.

## API and deployment

API documentation: http://localhost:8388/api/docs

The Docker configuration binds the server to `127.0.0.1:8388` and enables `MYAN_OCR_LOCAL_DEV=1`. **Do not publish that configuration to the internet.** For a public service, disable local mode and implement authenticated server-side access, HTTPS, proxy request limits and shared rate limiting. The bundled browser UI does not send `MYAN_OCR_API_KEY`.

Request limits include 12 MiB uploads, 16-megapixel images, an eight-page PDF limit and OCR processing budgets. Deadlines are cooperative, not a guarantee that native PDF rendering can always be interrupted. See [Security](docs/SECURITY.md).

## Testing

```bash
python -m pytest -q
node --check web/app.js
python -m compileall -q app scripts
```

The latest recorded source test run passed 54 automated tests. The public Google APIs, Docker image build and physical phone cameras have not been verified in this environment. See [Test report](docs/TEST-REPORT.md).

## OCR accuracy

Recognition must be checked against the original. One synthetic printed Myanmar sample measured 5.71% character error rate and did not exactly match. That sample does not establish general camera accuracy or improvement between releases. See [Accuracy](docs/ACCURACY.md).

## Documentation

- [Mac installation](docs/START-MAC-MY.md)
- [Accuracy evaluation](docs/ACCURACY.md)
- [Security and data handling](docs/SECURITY.md)
- [Verification](docs/TEST-REPORT.md)
- [Upgrade from v0.1.2](docs/UPGRADE-v0.1.3.md)
- [Release history](CHANGELOG.md)
