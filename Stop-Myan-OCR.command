#!/bin/bash
set -e
cd "$(dirname "$0")"
docker compose down
printf '\nMyan OCR stopped. Press Enter to close.\n'
read -r _
