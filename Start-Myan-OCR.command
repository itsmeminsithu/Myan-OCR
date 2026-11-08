#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "Starting Myan OCR Docker environment..."
./scripts/start-mac.sh
open "http://localhost:8388" || true
printf '\nMyan OCR started. Press Enter to close this Terminal window.\n'
read -r _
