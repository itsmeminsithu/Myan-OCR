#!/usr/bin/env bash
# Optional: fetch official slower tessdata_best models for local evaluation.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v curl >/dev/null || { echo "curl is required"; exit 1; }
mkdir -p models
for lang in mya eng; do
  url="https://github.com/tesseract-ocr/tessdata_best/raw/refs/heads/main/${lang}.traineddata"
  echo "Downloading $lang model from official Tesseract repository..."
  curl -fL --retry 3 --connect-timeout 15 --max-time 300 "$url" -o "models/${lang}.traineddata.tmp"
  test -s "models/${lang}.traineddata.tmp" || { echo "Empty model file"; exit 1; }
  mv "models/${lang}.traineddata.tmp" "models/${lang}.traineddata"
done
printf '%s\n' 'Best-model files are in ./models/ (not committed to GitHub).'
printf '%s\n' 'For local Python: export TESSDATA_PREFIX="$PWD/models"'
printf '%s\n' 'For Docker: set TESSDATA_PREFIX=/models in .env and restart docker compose.'
