# Reference image for `flightdeck serve` (trusted networks only; see README + SECURITY.md).
FROM python:3.14-slim

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "flightdeck-ai>=1.1.1"

WORKDIR /workspace

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health').read()"

ENTRYPOINT ["/entrypoint.sh"]
