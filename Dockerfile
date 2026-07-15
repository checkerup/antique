# antique — self-hosted anti-detect browser
# Uses Playwright's official image so Chromium + Firefox + WebKit and all their
# system deps are preinstalled. Camoufox is optional (see QUICKSTART).
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

# Install Python deps first for better layer caching.
COPY pyproject.toml requirements.txt ./
COPY src ./src
RUN pip install --no-cache-dir -e .

# Data dir (SQLite DB + per-profile user data dirs) lives here; mount a volume
# to persist profiles across container restarts.
ENV ANTIQUE_DATA_DIR=/data
VOLUME ["/data"]

EXPOSE 8080

# Headless by default in a container (no display). Override CMD to run headed
# with an X server if you really need a visible window.
ENV ANTIQUE_HEADLESS=1
CMD ["python", "-m", "src.cli", "serve", "--host", "0.0.0.0", "--ui-port", "8080", "--headless"]
