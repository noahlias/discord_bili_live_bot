from discord_live_bot.db import SubscriptionStore


def test_subscription_store_crud(tmp_path):
    db_path = tmp_path / "test.db"
    store = SubscriptionStore(str(db_path))

    assert store.list_uids() == []

    assert store.add_uid("100") is True
    assert store.add_uid("100") is False
    assert store.add_uid("200") is True
    assert store.list_uids() == ["100", "200"]

    assert store.remove_uid("100") is True
    assert store.remove_uid("100") is False
    assert store.list_uids() == ["200"]

    store.close()
