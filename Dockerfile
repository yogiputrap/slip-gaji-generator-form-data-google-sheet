FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    DATA_DIR=/data \
    CHROME_PATH=/usr/bin/chromium

# Chromium untuk render PDF. Carlito = pengganti Calibri (metrik sama) agar tata letak slip tetap presisi.
RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium fontconfig fonts-crosextra-carlito fonts-liberation \
 && rm -rf /var/lib/apt/lists/* \
 && fc-cache -f

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data persisten (unggahan logo/TTD, hasil PDF). Mount volume Dokploy ke /data.
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/login' % os.environ.get('PORT','8000'), timeout=4)"

# --proxy-headers: ambil IP klien & skema https asli dari Traefik (untuk pembatas login dan cookie Secure)
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips '*'"]
