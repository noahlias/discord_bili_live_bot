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


def test_subscription_store_dynamic_offsets(tmp_path):
    db_path = tmp_path / "test.db"
    store = SubscriptionStore(str(db_path))

    assert store.get_dynamic_offset("100") is None

    store.upsert_dynamic_offset("100", 123)
    assert store.get_dynamic_offset("100") == 123

    store.upsert_dynamic_offset("100", 456)
    assert store.get_dynamic_offset("100") == 456

    store.upsert_dynamic_offset("200", 999)
    store.prune_dynamic_offsets(["100"])
    assert store.get_dynamic_offset("100") == 456
    assert store.get_dynamic_offset("200") is None

    store.delete_dynamic_offset("100")
    assert store.get_dynamic_offset("100") is None

    store.close()


def test_subscription_store_dota_search_history(tmp_path):
    db_path = tmp_path / "test.db"
    store = SubscriptionStore(str(db_path))

    store.record_dota_search("455095162", "first-name")
    store.record_dota_search("123456789", "Beta")
    store.record_dota_search("455095162", "o(´^｀)o")

    ranked = store.list_dota_searches()
    assert ranked[0] == ("455095162", "o(´^｀)o", 2)
    assert ranked[1] == ("123456789", "Beta", 1)

    by_account = store.list_dota_searches("455")
    assert by_account[0][0] == "455095162"

    by_name = store.list_dota_searches("bet")
    assert by_name[0][0] == "123456789"

    store.close()
