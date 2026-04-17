FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini .

RUN mkdir -p /data/audio /data/uploads && \
    useradd -r -u 1000 bot && \
    chown -R bot:bot /data /app

USER bot

CMD ["python", "-m", "app.main"]
