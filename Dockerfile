FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    MAMATCH_LLM=off \
    MAMATCH_UPLOAD_DIR=/app/data/uploads

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && groupadd --system --gid 10001 mamatch \
    && useradd --system --uid 10001 --gid mamatch --home-dir /app mamatch \
    && mkdir -p /app/data/uploads \
    && chown -R mamatch:mamatch /app

USER mamatch
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/health/live', timeout=3)"

CMD ["python", "-m", "mamatch.container"]
