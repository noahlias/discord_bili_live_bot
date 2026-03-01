# Discord Live Bot (Bilibili)

Discord bot subproject for tracking Bilibili live status with slash commands, rich embeds, and link buttons.

## Features

- Slash commands: `/subscribe`, `/unsubscribe`, `/list`, `/live`, `/help`
- `/unsubscribe` supports UID autocomplete from current subscriptions
- Rich Discord embeds for live/offline transitions
- URL buttons (`Watch Live`, `Bilibili Profile`)
- SQLite subscription storage
- Direct Bilibili API via `httpx` with normalized image URLs

## Requirements

- `uv`
- Discord bot token with application command permission

## Quick Start

```bash
cd discord_live_bot
cp .env.example .env
# fill values in .env
uv sync
uv run discord-live-bot
```

## Docker Deploy

Build and run directly:

```bash
cd discord_live_bot
docker build -t discord-live-bot:latest .
docker run -d \
  --name discord-live-bot \
  --restart unless-stopped \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  discord-live-bot:latest
```

Or use Compose:

```bash
cd discord_live_bot
docker compose up -d --build
```

Check logs:

```bash
docker logs -f discord-live-bot
```

## Linux x86_64 Tar Deploy (Recommended for your server)

Build a Linux `amd64` image tarball on your machine:

```bash
cd discord_live_bot
chmod +x scripts/build_linux_amd64_tar.sh scripts/deploy_from_tar.sh
./scripts/build_linux_amd64_tar.sh latest
```

This creates:

- `dist/discord-live-bot_latest_linux_amd64.tar.gz`

Upload to server:

1. Upload the tarball (and `scripts/deploy_from_tar.sh`) to your Linux server.
2. Put your `.env` on the server.
3. Run deploy script on server:

```bash
chmod +x scripts/deploy_from_tar.sh
./scripts/deploy_from_tar.sh dist/discord-live-bot_latest_linux_amd64.tar.gz .env
```

Run in background is automatic (`docker run -d` + `--restart unless-stopped`).

## One-Command SSH Deploy (Build + Upload + Run)

This is the easiest flow if you want to include SSH user/host once and just run one command.

```bash
cd discord_live_bot
cp deploy/server.conf.example deploy/server.conf
# edit deploy/server.conf: SSH_USER / SSH_HOST / paths
chmod +x scripts/remote_deploy_via_ssh.sh scripts/build_linux_amd64_tar.sh scripts/deploy_from_tar.sh
./scripts/remote_deploy_via_ssh.sh
```

You can also pass a custom config path:

```bash
./scripts/remote_deploy_via_ssh.sh /path/to/server.conf
```

## Environment Variables

- `DISCORD_TOKEN`: Bot token
- `DISCORD_NOTIFY_CHANNEL_ID`: Channel to push live/offline notifications
- `DISCORD_GUILD_ID`: Optional guild id for faster command sync during development
- `POLL_INTERVAL_SECONDS`: Polling interval, default `30`
- `SQLITE_PATH`: SQLite file path, default `data/subscriptions.db`
- `LOG_LEVEL`: `DEBUG`/`INFO`/`WARNING`/`ERROR`

## Discord Permissions

- `View Channels`
- `Send Messages`
- `Embed Links`
- `Use Slash Commands`
