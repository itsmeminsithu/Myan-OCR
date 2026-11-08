#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v docker >/dev/null 2>&1; then
 echo "Install Docker Desktop for Mac: https://www.docker.com/products/docker-desktop/"; exit 1
fi
if ! docker info >/dev/null 2>&1; then
 echo "Open Docker Desktop, confirm Engine running, then retry."; exit 1
fi
docker compose up -d --build
echo "Myan OCR: http://localhost:8388"
echo "Status: http://localhost:8388/api/health"
