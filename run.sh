#!/bin/bash
# Script untuk menjalankan Auto Slip Gaji Generator

echo "=========================================================="
echo "  🚀 Menjalankan Auto Slip Gaji Generator Web Dashboard"
echo "=========================================================="
echo "  Buka browser di: http://127.0.0.1:8000"
echo "  Tekan Ctrl+C untuk menghentikan server."
echo "=========================================================="

python3 -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
