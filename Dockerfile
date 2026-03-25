FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable

COPY src ./src
RUN uv sync --frozen --no-dev --no-editable && rm -rf /root/.cache


FROM python:3.11-slim

ARG INSTALL_PLAYWRIGHT=1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    SQLITE_PATH=/app/data/subscriptions.db \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg libopus0 \
    && if [ "$INSTALL_PLAYWRIGHT" = "1" ]; then \
      apt-get install -y --no-install-recommends \
      fontconfig \
      fonts-liberation \
      fonts-noto-cjk \
      libasound2 \
      libatk-bridge2.0-0 \
      libatk1.0-0 \
      libc6 \
      libcairo2 \
      libcups2 \
      libdbus-1-3 \
      libdrm2 \
      libgbm1 \
      libglib2.0-0 \
      libnspr4 \
      libnss3 \
      libpango-1.0-0 \
      libx11-6 \
      libx11-xcb1 \
      libxcb1 \
      libxcomposite1 \
      libxdamage1 \
      libxext6 \
      libxfixes3 \
      libxkbcommon0 \
      libxrandr2 \
      libxshmfence1 \
      libxss1 \
      libxtst6 \
      xdg-utils; \
    fi \
    && update-ca-certificates \
    && groupadd -r app \
    && useradd -r -g app appuser \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv

RUN mkdir -p /app/data /ms-playwright \
    && if [ "$INSTALL_PLAYWRIGHT" = "1" ]; then \
      python -m playwright install chromium --only-shell; \
      fc-cache -f; \
    fi \
    && rm -rf /root/.cache \
    && chown -R appuser:app /app /ms-playwright

USER appuser

CMD ["discord-live-bot"]
