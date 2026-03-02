# Repository Guidelines

## Project Structure & Module Organization
- Core code lives in `src/discord_live_bot/`.
- Entry point: `main.py` (`discord-live-bot` console script).
- Main modules: `bot.py` (Discord commands/scheduler), `bili_client.py` (Bilibili API client), `db.py` (SQLite subscriptions), `status_tracker.py` (live/offline diffing), `rendering.py` (embeds/views), `config.py` (env-backed settings).
- Tests are in `tests/` and mirror module behavior (`test_db.py`, `test_rendering.py`, etc.).
- Deployment assets/scripts: `Dockerfile`, `docker-compose.yml`, `deploy/`, `scripts/`.
- Runtime data defaults to `data/subscriptions.db`; build artifacts go to `dist/`.

## Build, Test, and Development Commands
- `uv sync`: install runtime + dev dependencies from `pyproject.toml`/`uv.lock`.
- `cp .env.example .env`: create local config, then fill required values.
- `uv run discord-live-bot`: run the bot locally.
- `uv run pytest -q`: run the full test suite.
- `docker compose up -d --build`: build and run containerized bot.
- `./scripts/build_linux_amd64_tar.sh`: build Linux `amd64` image tarball into `dist/`.

## Coding Style & Naming Conventions
- Python 3.11+, 4-space indentation, type hints on public functions.
- Use `snake_case` for functions/variables/files, `PascalCase` for classes, `UPPER_SNAKE_CASE` for env vars/constants.
- Keep modules focused (API, persistence, rendering, tracking separated as they are now).
- Prefer small, explicit functions and dataclasses for structured payloads (`RoomInfo`, `Settings`).

## Testing Guidelines
- Framework: `pytest` with `pytest-asyncio` for async paths.
- Name files `test_*.py`; name tests by behavior (for example `test_unsubscribe_autocomplete_prefix_first`).
- Use fixtures like `tmp_path` and `monkeypatch` to avoid network/FS side effects.
- Add/adjust tests in the matching domain when changing logic (client, tracker, DB, bot command behavior).

## Commit & Pull Request Guidelines
- Current history uses short imperative commit subjects (for example `Update docker tag`). Keep subjects concise and action-oriented.
- Prefer one logical change per commit.
- PRs should include: purpose, key changes, test evidence (`uv run pytest -q` output), and any deploy/config impact (`.env`, Docker, `deploy/server.conf`).

## Security & Configuration Tips
- Never commit secrets; `.env` is local-only. Keep `.env.example` as the template.
- Validate required env vars before deploy (`DISCORD_TOKEN`, `DISCORD_NOTIFY_CHANNEL_ID`).
- Persist `data/` in Docker deployments so subscriptions survive restarts.
