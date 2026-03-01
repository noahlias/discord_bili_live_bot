FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable --compile-bytecode

COPY src ./src
RUN uv sync --frozen --no-dev --no-editable --compile-bytecode && rm -rf /root/.cache


FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    SQLITE_PATH=/app/data/subscriptions.db

WORKDIR /app

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder /app/.venv /app/.venv

RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

CMD ["discord-live-bot"]
