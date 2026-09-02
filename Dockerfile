# antique — self-hosted anti-detect browser
# Uses Playwright's official image so Chromium + Firefox + WebKit and all their
# system deps are preinstalled. Camoufox is optional (see QUICKSTART).
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

# Install Python deps first for better layer caching.
COPY pyproject.toml requirements.txt ./
COPY packaging/requirements-lock.txt ./packaging/requirements-lock.txt
COPY src ./src
RUN pip install --no-cache-dir -c packaging/requirements-lock.txt -e .

RUN useradd --create-home --uid 10001 antique \
    && mkdir -p /data \
    && chown -R antique:antique /app /data

# Data dir (SQLite DB + per-profile user data dirs) lives here; mount a volume
# to persist profiles across container restarts.
ENV ANTIQUE_DATA_DIR=/data
ENV PYTHONUNBUFFERED=1
VOLUME ["/data"]

EXPOSE 8080

# Headless by default in a container (no display). Override CMD to run headed
# with an X server if you really need a visible window.
ENV ANTIQUE_HEADLESS=1

# Default: remote mode with fail-closed auth.
# Set ANTIQUE_API_TOKEN (required for remote mode), or override DEPLOY_MODE
# to "local" or "lan" for less strict security.
ENV ANTIQUE_DEPLOY_MODE=remote

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3).read()" || exit 1

USER antique

# Remote mode requires a token — fail-closed at startup without one.
# Use `docker run -e ANTIQUE_API_TOKEN=<token>` or generate one with
# `python -m src.cli serve --deploy-mode remote --generate-token`.
CMD ["python", "-m", "src.cli", "serve", "--host", "0.0.0.0", "--ui-port", "8080", "--headless", "--deploy-mode", "remote"]
