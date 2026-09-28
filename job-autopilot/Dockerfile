# Official Playwright image: Python + Chromium + all OS dependencies, pinned.
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    JOBAP_DATA_DIR=/data JOBAP_HEADLESS=true
WORKDIR /app
COPY pyproject.toml README.md ./
COPY autopilot ./autopilot
# Optional build secret "extra_ca" (e.g. a corporate TLS proxy CA). Never stored in the image.
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -f /run/secrets/extra_ca ]; then export PIP_CERT=/run/secrets/extra_ca; fi; \
    pip install --break-system-packages "playwright==1.55.0" . \
 && mkdir -p /data && chown pwuser:pwuser /data
USER pwuser
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=4).status==200 else 1)" || exit 1
ENTRYPOINT ["autopilot"]
CMD ["web", "--host", "0.0.0.0", "--port", "8000"]
