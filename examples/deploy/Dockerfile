# Reference image for `flightdeck serve` (trusted networks only; see README + SECURITY.md).
FROM python:3.14-slim

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "flightdeck-ai>=1.2.0"

WORKDIR /workspace

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8765

# Respect PORT at runtime (e.g. Railway); default matches local Compose.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request; p=os.environ.get('PORT','8765'); urllib.request.urlopen(f'http://127.0.0.1:{p}/health').read()"

ENTRYPOINT ["/entrypoint.sh"]
