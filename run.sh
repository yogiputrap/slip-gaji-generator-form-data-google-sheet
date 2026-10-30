#!/bin/bash
# Script untuk menjalankan Auto Slip Gaji Generator

# Muat kredensial login (AUTH_*) dari .env bila ada
if [ -f "$(dirname "$0")/.env" ]; then
  set -a; . "$(dirname "$0")/.env"; set +a
fi

PORT=${PORT:-8000}
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
  echo "⚠️ Port $PORT sedang digunakan oleh proses lain."
  PORT=8008
  echo "👉 Mengalihkan ke port $PORT..."
fi

echo "=========================================================="
echo "  🚀 Menjalankan Auto Slip Gaji Generator Web Dashboard"
echo "=========================================================="
echo "  Buka browser di: http://127.0.0.1:$PORT"
echo "  Tekan Ctrl+C untuk menghentikan server."
echo "=========================================================="

python3 -m uvicorn app:app --host 127.0.0.1 --port $PORT --reload
