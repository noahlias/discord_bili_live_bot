from datetime import datetime, timezone

from discord_live_bot.bili_client import RoomInfo
from discord_live_bot.dynamic_client import DynamicItem
from discord_live_bot.rendering import live_end_embed, live_start_embed, live_start_view, snapshot_embeds


def make_room(uid: str, live_status: int) -> RoomInfo:
    return RoomInfo(
        uid=uid,
        uname=f"user-{uid}",
        live_status=live_status,
        room_id=100 + int(uid),
        short_id=0,
        title="stream title",
        cover="https://example.com/cover.png",
        face="https://example.com/face.png",
        area_parent="game",
        area_name="fps",
        live_time=100,
    )


def test_live_start_embed_and_view_shape():
    room = make_room("1", 1)
    embed = live_start_embed(room, datetime.now(timezone.utc))
    view = live_start_view(room)

    assert "LIVE" in embed.title
    assert len(embed.fields) == 3
    assert len(view.children) == 2


def test_live_end_embed_contains_duration_field():
    room = make_room("1", 0)
    embed = live_end_embed(room, 3661, datetime.now(timezone.utc))
    assert "offline" in embed.title
    assert embed.fields[0].name.startswith("Session Duration")


def test_snapshot_embeds_pagination_and_counts():
    rooms = [make_room("1", 1), make_room("2", 0)]
    embeds = snapshot_embeds(rooms, following_count=2, live_only=False)

    assert len(embeds) == 3
    assert embeds[0].fields[0].name == "Following"
    assert embeds[0].fields[0].value == "2"
    assert embeds[1].thumbnail.url == "https://example.com/face.png"
    assert embeds[1].image.url == "https://example.com/cover.png"


def test_dynamic_embed_shape():
    from discord_live_bot.rendering import dynamic_post_embed

    item = DynamicItem(
        uid="7261854",
        dyn_id=123456,
        card_type=7,
        card_type_label="draw",
        author_name="tester",
        cover_url="https://example.com/dynamic.jpg",
    )
    embed = dynamic_post_embed(item, datetime.now(timezone.utc))

    assert "tester" in embed.title.lower()
    assert embed.fields[0].value == "7261854"
    assert embed.fields[1].value == "123456"
    assert embed.fields[2].name == "链接"
