from __future__ import annotations

from html import escape

from loguru import logger
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from .models import DotaHeroAsset, DotaItemAsset, DotaMatchDetail, DotaMatchPlayerStats


OPENDOTA_MATCH_URL_TEMPLATE = "https://www.opendota.com/matches/{match_id}"
OPENDOTA_PLAYER_MATCHES_URL_TEMPLATE = "https://www.opendota.com/players/{account_id}/matches"


def _item_image_tag(item_id: int | None, item_assets: dict[int, DotaItemAsset], *, neutral: bool = False) -> str:
    if item_id is None:
        class_name = "item-slot neutral" if neutral else "item-slot"
        return f'<div class="{class_name} empty"></div>'

    item = item_assets.get(item_id)
    item_name = item.display_name if item is not None else f"Item #{item_id}"
    image_url = item.image_url if item is not None else ""
    class_name = "item-slot neutral" if neutral else "item-slot"
    if image_url:
        return (
            f'<div class="{class_name}" title="{escape(item_name)}">'
            f'<img src="{escape(image_url)}" alt="{escape(item_name)}" loading="lazy" />'
            "</div>"
        )
    return f'<div class="{class_name} fallback" title="{escape(item_name)}">{escape(item_name[:2])}</div>'


def _avatar_tag(player: DotaMatchPlayerStats) -> str:
    if player.avatar_url:
        return f'<img class="avatar" src="{escape(player.avatar_url)}" alt="player avatar" loading="lazy" />'
    name = player.persona_name.strip() or "?"
    return f'<div class="avatar placeholder">{escape(name[0].upper())}</div>'


def _hero_block(player: DotaMatchPlayerStats, hero_assets: dict[int, DotaHeroAsset]) -> str:
    hero = hero_assets.get(player.hero_id)
    hero_name = hero.localized_name if hero is not None else f"Hero #{player.hero_id}"
    hero_icon = ""
    if hero is not None:
        hero_icon = hero.icon_url or hero.portrait_url

    hero_img = (
        f'<img class="hero" src="{escape(hero_icon)}" alt="{escape(hero_name)}" loading="lazy" />'
        if hero_icon
        else '<div class="hero placeholder">H</div>'
    )
    return (
        f"{hero_img}"
        '<div class="meta">'
        f'<div class="name">{escape(player.persona_name or str(player.account_id or "Anonymous"))}</div>'
        f'<div class="hero-name">{escape(hero_name)}</div>'
        "</div>"
    )


def _player_row(
    player: DotaMatchPlayerStats,
    *,
    hero_assets: dict[int, DotaHeroAsset],
    item_assets: dict[int, DotaItemAsset],
) -> str:
    inventory_slots = player.item_slot_ids or (None, None, None, None, None, None)
    backpack_slots = player.backpack_item_ids or (None, None, None)

    item_html = "".join(_item_image_tag(item_id, item_assets) for item_id in inventory_slots[:6])
    item_html += "".join(_item_image_tag(item_id, item_assets) for item_id in backpack_slots[:3])
    item_html += _item_image_tag(player.neutral_item_id, item_assets, neutral=True)

    result = "W" if player.won else "L"
    return (
        '<div class="player-row">'
        '<div class="identity">'
        f"{_avatar_tag(player)}"
        f"{_hero_block(player, hero_assets)}"
        "</div>"
        f'<div class="stat win">{result}</div>'
        f'<div class="stat kda">{player.kills}/{player.deaths}/{player.assists}</div>'
        f'<div class="stat level">{player.level}</div>'
        f'<div class="items">{item_html}</div>'
        "</div>"
    )


def _team_section(
    title: str,
    players: list[DotaMatchPlayerStats],
    *,
    hero_assets: dict[int, DotaHeroAsset],
    item_assets: dict[int, DotaItemAsset],
    variant: str,
) -> str:
    rows = "".join(
        _player_row(player, hero_assets=hero_assets, item_assets=item_assets)
        for player in players
    )
    return (
        f'<section class="team {variant}">'
        f'<div class="team-title">{escape(title)}</div>'
        '<div class="table-head">'
        '<div>Player / Hero</div><div>W</div><div>KDA</div><div>Lv</div><div>Items</div>'
        "</div>"
        f"{rows}"
        "</section>"
    )


def build_match_table_html(
    detail: DotaMatchDetail,
    *,
    hero_assets: dict[int, DotaHeroAsset],
    item_assets: dict[int, DotaItemAsset],
) -> str:
    radiant_players = sorted(
        [player for player in detail.players if player.player_slot < 128],
        key=lambda player: player.player_slot,
    )
    dire_players = sorted(
        [player for player in detail.players if player.player_slot >= 128],
        key=lambda player: player.player_slot,
    )

    match_result = "Unknown"
    if detail.radiant_win is True:
        match_result = "Radiant Victory"
    elif detail.radiant_win is False:
        match_result = "Dire Victory"

    score_text = ""
    if detail.radiant_score is not None and detail.dire_score is not None:
        score_text = f"Radiant {detail.radiant_score} : {detail.dire_score} Dire"

    radiant_title = "Radiant"
    dire_title = "Dire"
    if detail.radiant_win is True:
        radiant_title += " (WIN)"
        dire_title += " (LOSE)"
    elif detail.radiant_win is False:
        radiant_title += " (LOSE)"
        dire_title += " (WIN)"

    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<style>
  body {{
    margin: 0;
    padding: 24px;
    background: #0b0f19;
    color: #e8eefc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  .card {{
    width: 1560px;
    border-radius: 14px;
    border: 1px solid #26324a;
    background: linear-gradient(180deg, #111a2c 0%, #0d1525 100%);
    box-shadow: 0 14px 36px rgba(0, 0, 0, 0.35);
    padding: 16px;
  }}
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 14px;
  }}
  .title {{
    font-size: 26px;
    font-weight: 700;
    letter-spacing: 0.3px;
  }}
  .subtitle {{
    font-size: 16px;
    color: #9db2d6;
  }}
  .teams {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }}
  .team {{
    border-radius: 10px;
    padding: 12px;
    border: 1px solid #2f3e5f;
    background: rgba(16, 24, 40, 0.9);
  }}
  .team.radiant {{ border-color: #2ea043; }}
  .team.dire {{ border-color: #c63d3d; }}
  .team-title {{
    font-size: 18px;
    font-weight: 700;
    margin-bottom: 10px;
  }}
  .table-head,
  .player-row {{
    display: grid;
    grid-template-columns: 2.4fr 0.5fr 0.9fr 0.5fr 2.7fr;
    gap: 8px;
    align-items: center;
  }}
  .table-head {{
    color: #8aa0c8;
    font-size: 12px;
    padding: 4px 0 8px;
    border-bottom: 1px solid #27334d;
    margin-bottom: 4px;
  }}
  .player-row {{
    min-height: 54px;
    border-bottom: 1px dashed #202d45;
    padding: 4px 0;
    font-size: 13px;
  }}
  .identity {{
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }}
  .avatar {{
    width: 28px;
    height: 28px;
    border-radius: 50%;
    object-fit: cover;
    flex-shrink: 0;
    border: 1px solid #3d4d70;
    background: #13203a;
  }}
  .avatar.placeholder,
  .hero.placeholder {{
    display: flex;
    align-items: center;
    justify-content: center;
    color: #d8e5ff;
    font-size: 12px;
    font-weight: 700;
  }}
  .hero {{
    width: 36px;
    height: 20px;
    object-fit: cover;
    border-radius: 4px;
    border: 1px solid #3f5077;
    flex-shrink: 0;
    background: #1a2740;
  }}
  .meta {{
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }}
  .name,
  .hero-name {{
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .name {{ font-weight: 600; }}
  .hero-name {{ color: #9fb2d8; font-size: 12px; }}
  .stat {{
    text-align: center;
    font-weight: 600;
    color: #d7e4ff;
  }}
  .items {{
    display: flex;
    gap: 3px;
    flex-wrap: nowrap;
  }}
  .item-slot {{
    width: 22px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #40547a;
    overflow: hidden;
    background: #1a2842;
    flex-shrink: 0;
  }}
  .item-slot img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }}
  .item-slot.empty {{
    opacity: 0.28;
  }}
  .item-slot.neutral {{
    border-color: #ffc23d;
  }}
  .item-slot.fallback {{
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 9px;
    color: #dce9ff;
  }}
</style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="title">Match #{detail.match_id}</div>
      <div class="subtitle">{escape(match_result)} | {escape(score_text)}</div>
    </div>
    <div class="teams">
      {_team_section(radiant_title, radiant_players, hero_assets=hero_assets, item_assets=item_assets, variant="radiant")}
      {_team_section(dire_title, dire_players, hero_assets=hero_assets, item_assets=item_assets, variant="dire")}
    </div>
  </div>
</body>
</html>
"""


async def render_match_table_png(
    detail: DotaMatchDetail,
    *,
    hero_assets: dict[int, DotaHeroAsset],
    item_assets: dict[int, DotaItemAsset],
) -> bytes | None:
    screenshot = await _render_opendota_layout_png(detail.match_id)
    if screenshot is not None:
        return screenshot
    return await _render_custom_layout_png(
        detail,
        hero_assets=hero_assets,
        item_assets=item_assets,
    )


async def render_recent_matches_png(account_id: int, limit: int) -> bytes | None:
    safe_limit = max(1, min(int(limit), 10))
    url = OPENDOTA_PLAYER_MATCHES_URL_TEMPLATE.format(account_id=account_id)
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage"],
            )
            try:
                page = await browser.new_page(
                    viewport={"width": 1680, "height": 2200},
                    device_scale_factor=2,
                )
                await page.goto(url, wait_until="domcontentloaded", timeout=40_000)
                await page.wait_for_load_state("networkidle", timeout=40_000)
                await page.wait_for_timeout(1_200)
                await page.evaluate("window.scrollTo(0, 0)")

                clip = await page.evaluate(
                    """
(limit) => {
  const table = document.querySelector('main table') || document.querySelector('table');
  if (!table) {
    return null;
  }

  const bodyRows = Array.from(table.querySelectorAll('tbody tr'));
  bodyRows.forEach((row, idx) => {
    if (idx >= limit) {
      row.style.display = 'none';
    }
  });

  const heading = Array.from(document.querySelectorAll('*')).find(
    (el) => (el.textContent || '').trim() === 'Recent Matches'
  );
  const tableRect = table.getBoundingClientRect();
  const headingRect = heading ? heading.getBoundingClientRect() : tableRect;
  const top = Math.max(0, Math.min(tableRect.top, headingRect.top) + window.scrollY - 28);
  const bottom = tableRect.bottom + window.scrollY + 20;
  const docHeight = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
  const maxWidth = Math.max(1000, Math.min(window.innerWidth - 16, tableRect.width + 40));
  const x = Math.max(0, tableRect.left + window.scrollX - 12);
  const y = top;
  const width = Math.max(960, maxWidth);
  const height = Math.max(380, Math.min(docHeight - y, bottom - top));

  return { x, y, width, height };
}
""",
                    safe_limit,
                )
                if not isinstance(clip, dict):
                    return None
                return await page.screenshot(clip=clip, type="jpeg", quality=85)
            finally:
                await browser.close()
    except PlaywrightError as exc:
        logger.warning("Failed to capture OpenDota recent matches screenshot: {}", exc)
        return None
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Unexpected recent matches screenshot error: {}", exc)
        return None


async def _render_opendota_layout_png(match_id: int) -> bytes | None:
    url = OPENDOTA_MATCH_URL_TEMPLATE.format(match_id=match_id)
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage"],
            )
            try:
                page = await browser.new_page(
                    viewport={"width": 1680, "height": 2300},
                    device_scale_factor=2,
                )
                await page.goto(url, wait_until="domcontentloaded", timeout=40_000)
                await page.wait_for_load_state("networkidle", timeout=40_000)
                await page.wait_for_timeout(1_200)
                await page.evaluate("window.scrollTo(0, 0)")

                clip = await page.evaluate(
                    """
() => {
  const all = Array.from(document.querySelectorAll('*'));
  const matchText = (text) => all.find((el) => (el.textContent || '').trim().startsWith(text));
  const radiant = matchText('Radiant - Overview');
  const dire = matchText('Dire - Overview');
  if (!radiant || !dire) {
    return null;
  }

  const r = radiant.getBoundingClientRect();
  const d = dire.getBoundingClientRect();
  const top = Math.max(0, Math.min(r.top, d.top) + window.scrollY - 300);
  const bottom = Math.max(r.bottom, d.bottom) + window.scrollY + 1050;
  const docHeight = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
  const height = Math.max(460, Math.min(docHeight - top, bottom - top));
  const width = Math.max(1000, window.innerWidth - 24);
  return {
    x: 12,
    y: top,
    width,
    height,
  };
}
"""
                )
                if isinstance(clip, dict):
                    return await page.screenshot(clip=clip, type="jpeg", quality=85)
                return await page.screenshot(type="jpeg", quality=85)
            finally:
                await browser.close()
    except PlaywrightError as exc:
        logger.warning("Failed to capture OpenDota match screenshot: {}", exc)
        return None
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Unexpected OpenDota screenshot error: {}", exc)
        return None


async def _render_custom_layout_png(
    detail: DotaMatchDetail,
    *,
    hero_assets: dict[int, DotaHeroAsset],
    item_assets: dict[int, DotaItemAsset],
) -> bytes | None:
    html = build_match_table_html(
        detail,
        hero_assets=hero_assets,
        item_assets=item_assets,
    )

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage"],
            )
            try:
                page = await browser.new_page(
                    viewport={"width": 1660, "height": 920},
                    device_scale_factor=2,
                )
                await page.set_content(html, wait_until="networkidle")
                await page.wait_for_timeout(200)
                return await page.screenshot(full_page=True, type="jpeg", quality=88)
            finally:
                await browser.close()
    except PlaywrightError as exc:
        logger.warning("Failed to render Dota match table via Playwright: {}", exc)
        return None
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Unexpected Dota match table render error: {}", exc)
        return None
