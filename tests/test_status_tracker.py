from discord_live_bot.bili_client import RoomInfo
from discord_live_bot.status_tracker import StatusTracker


def make_room(uid: str, live_status: int, live_time: int | None = None) -> RoomInfo:
    return RoomInfo(
        uid=uid,
        uname=f"u{uid}",
        live_status=live_status,
        room_id=1,
        short_id=0,
        title="title",
        cover="",
        face="",
        area_parent="game",
        area_name="fps",
        live_time=live_time,
    )


def test_tracker_initial_snapshot_no_notifications():
    tracker = StatusTracker()
    changes = tracker.diff({"1": make_room("1", 0)}, now_ts=1_000)
    assert changes == []


def test_tracker_live_then_offline_duration():
    tracker = StatusTracker()

    tracker.diff({"1": make_room("1", 0)}, now_ts=1_000)
    changes = tracker.diff({"1": make_room("1", 1, live_time=1_050)}, now_ts=1_100)
    assert len(changes) == 1
    assert changes[0].went_live is True

    changes = tracker.diff({"1": make_room("1", 0)}, now_ts=1_200)
    assert len(changes) == 1
    assert changes[0].went_live is False
    assert changes[0].duration_seconds == 150


def test_tracker_prune_removes_stale():
    tracker = StatusTracker()
    tracker.diff({"1": make_room("1", 1, live_time=1_000)}, now_ts=1_000)
    tracker.prune([])
    changes = tracker.diff({"1": make_room("1", 0)}, now_ts=1_050)
    assert changes == []
