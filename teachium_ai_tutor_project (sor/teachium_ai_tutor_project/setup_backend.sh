#!/usr/bin/env bash
# ===== TEACHIUM AI Tutor - installation du backend (Linux / macOS) =====
set -e
cd "$(dirname "$0")/backend"

[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  echo "ATTENTION : backend/.env est absent."
  echo "Copiez backend/.env.example vers backend/.env puis collez votre chaine Neon."
  exit 1
fi

python scripts/init_database.py
echo "Installation terminee. Lancez ./run_backend.sh puis ./run_frontend.sh"
