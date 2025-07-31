#!/bin/zsh
set -euo pipefail

SRC_ENV_FILE="${1:-/Users/vieirama/Documents/.env}"

if [[ ! -f "$SRC_ENV_FILE" ]]; then
  echo "source .env not found at: $SRC_ENV_FILE"
  exit 1
fi

cp "$SRC_ENV_FILE" .env
echo "copied .env to $(pwd)/.env"

# Load env vars
set -a
source .env
set +a

# Create virtualenv if needed
if [[ ! -d ".venv" ]]; then
  echo "creating .venv with current python"
  python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Ensure pip is up-to-date
python -m pip install --upgrade pip

# Install requirements
if [[ -f "requirements.txt" ]]; then
  echo "installing from requirements.txt"
  pip install -r requirements.txt
else
  echo "no requirements.txt; installing at least requests so main.py can run"
  pip install requests
fi

# Optional: regenerate requirements
if command -v pipreq >/dev/null 2>&1; then
  echo "regenerating requirements with pipreq"
  pipreq . --force
else
  echo "pipreq not installed; skipping regeneration of requirements"
fi

echo "starting main.py on port 5008"
python3 main.py --port 5008
