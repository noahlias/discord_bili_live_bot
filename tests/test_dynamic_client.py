import grpc
import pytest

from discord_live_bot.dynamic_client import (
    DynamicClient,
    DynamicDeserializeError,
    DynamicFetchError,
)
from discord_live_bot.grpc import dynamic_pb2


class _FakeRpcError(grpc.RpcError):
    def __init__(self, code: grpc.StatusCode, details: str):
        super().__init__()
        self._code = code
        self._details = details

    def code(self):
        return self._code

    def details(self):
        return self._details


def _make_response(dyn_ids: list[str]) -> dynamic_pb2.DynSpaceRsp:
    response = dynamic_pb2.DynSpaceRsp()
    for dyn_id in dyn_ids:
        item = response.list.add()
        item.card_type = 7
        item.extend.dyn_id_str = dyn_id
        item.extend.orig_img_url = "http://i0.hdslb.com/bfs/new_dyn/orig.jpg"
        module = item.modules.add()
        module.module_author.author.name = "tester"
        module.module_dynamic.dyn_draw.items.add().src = "http://i0.hdslb.com/bfs/new_dyn/draw.jpg"
    return response


def test_parse_response_extracts_fields():
    response = _make_response(["123", "456"])

    items = DynamicClient._parse_response("2", response)

    assert len(items) == 2
    assert items[0].dyn_id == 123
    assert items[0].author_name == "tester"
    assert items[0].card_type_label == "draw"
    assert items[0].cover_url == "https://i0.hdslb.com/bfs/new_dyn/draw.jpg"


def test_parse_response_skips_non_numeric_dyn_id():
    response = _make_response(["abc", "789"])

    items = DynamicClient._parse_response("2", response)

    assert len(items) == 1
    assert items[0].dyn_id == 789


@pytest.mark.asyncio
async def test_fetch_user_dynamics_maps_deserialize_error(monkeypatch):
    client = DynamicClient()

    def _raise(_uid: int):
        raise _FakeRpcError(grpc.StatusCode.INTERNAL, "Exception deserializing response!")

    monkeypatch.setattr(client, "_request_dyn_space", _raise)

    with pytest.raises(DynamicDeserializeError):
        await client.fetch_user_dynamics("2")


@pytest.mark.asyncio
async def test_fetch_user_dynamics_maps_generic_rpc_error(monkeypatch):
    client = DynamicClient()

    def _raise(_uid: int):
        raise _FakeRpcError(grpc.StatusCode.UNKNOWN, "-352")

    monkeypatch.setattr(client, "_request_dyn_space", _raise)

    with pytest.raises(DynamicFetchError):
        await client.fetch_user_dynamics("2")


@pytest.mark.asyncio
async def test_fetch_user_dynamics_uses_request_result(monkeypatch):
    client = DynamicClient()

    monkeypatch.setattr(client, "_request_dyn_space", lambda _uid: _make_response(["900"]))

    items = await client.fetch_user_dynamics("2")

    assert len(items) == 1
    assert items[0].dyn_id == 900


@pytest.mark.asyncio
async def test_fetch_user_dynamics_retries_on_rate_limit(monkeypatch):
    client = DynamicClient(max_retries=2, retry_delay_seconds=0)
    calls = {"count": 0}

    def _request(_uid: int):
        calls["count"] += 1
        if calls["count"] < 3:
            raise _FakeRpcError(grpc.StatusCode.UNKNOWN, "-352")
        return _make_response(["901"])

    monkeypatch.setattr(client, "_request_dyn_space", _request)

    items = await client.fetch_user_dynamics("2")

    assert calls["count"] == 3
    assert items[0].dyn_id == 901
