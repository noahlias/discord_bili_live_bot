from discord_live_bot.bot import SubscriptionCog


class _DummyStore:
    def __init__(self, uids: list[str]) -> None:
        self._uids = uids

    def list_uids(self) -> list[str]:
        return list(self._uids)


class _DummyBot:
    def __init__(self, uids: list[str]) -> None:
        self.store = _DummyStore(uids)


def test_unsubscribe_autocomplete_prefix_first():
    cog = SubscriptionCog(_DummyBot(["120", "312", "129", "9912", "555"]))
    choices = cog._autocomplete_uid_choices("12")
    values = [choice.value for choice in choices]

    assert values == ["120", "129", "312", "9912"]


def test_unsubscribe_autocomplete_empty_current_lists_all():
    cog = SubscriptionCog(_DummyBot(["1", "2", "3"]))
    choices = cog._autocomplete_uid_choices("")
    values = [choice.value for choice in choices]

    assert values == ["1", "2", "3"]


def test_unsubscribe_autocomplete_limits_25_choices():
    uids = [str(1000 + n) for n in range(30)]
    cog = SubscriptionCog(_DummyBot(uids))
    choices = cog._autocomplete_uid_choices("")

    assert len(choices) == 25
    assert choices[0].value == "1000"
    assert choices[-1].value == "1024"
