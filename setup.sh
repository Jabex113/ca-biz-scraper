#!/usr/bin/env bash
set -euo pipefail

rm -rf .venv
python3.13 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install --only-binary :all: -r requirements.txt

python -m playwright install --with-deps chromium

echo "Setup complete. Start the API with:"
echo "  source .venv/bin/activate && uvicorn app.main:app --reload --port 8000"
