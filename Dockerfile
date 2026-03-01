FROM python:3.11-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable --compile-bytecode

COPY src ./src
RUN uv sync --frozen --no-dev --no-editable --compile-bytecode && rm -rf /root/.cache


FROM python:3.11-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    SQLITE_PATH=/app/data/subscriptions.db

WORKDIR /app

RUN addgroup -S app && adduser -S -G app appuser

COPY --from=builder --chown=appuser:app /app/.venv /app/.venv

RUN mkdir -p /app/data && chown appuser:app /app/data

USER appuser

CMD ["discord-live-bot"]
