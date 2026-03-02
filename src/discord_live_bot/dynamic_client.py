from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import urlparse

import grpc

from .grpc import dynamic_pb2, dynamic_pb2_grpc


CARD_TYPE_LABELS = {
    1: "forward",
    2: "av",
    3: "pgc",
    6: "word",
    7: "draw",
    8: "article",
    9: "music",
    12: "live",
    15: "ad",
}


class DynamicFetchError(RuntimeError):
    """Raised when dynamic fetch fails due to transport or server errors."""


class DynamicDeserializeError(DynamicFetchError):
    """Raised when grpc response cannot be deserialized by local proto."""


@dataclass(frozen=True)
class DynamicItem:
    uid: str
    dyn_id: int
    card_type: int
    card_type_label: str
    author_name: str
    cover_url: str

    @property
    def dynamic_url(self) -> str:
        return f"https://t.bilibili.com/{self.dyn_id}"


class DynamicClient:
    _target = "grpc.biliapi.net"

    def __init__(
        self,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
        retry_delay_seconds: float = 0.6,
    ):
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, int(max_retries))
        self._retry_delay_seconds = max(0.0, float(retry_delay_seconds))

    async def fetch_user_dynamics(self, uid: str) -> list[DynamicItem]:
        uid_text = uid.strip()
        if not uid_text.isdigit():
            raise ValueError(f"UID must be numeric: {uid}")

        uid_int = int(uid_text)
        for attempt in range(self._max_retries + 1):
            try:
                response = await asyncio.to_thread(self._request_dyn_space, uid_int)
                break
            except grpc.RpcError as exc:
                details = (exc.details() or "").strip()
                is_rate_limited = details == "-352"
                can_retry = is_rate_limited and attempt < self._max_retries
                if can_retry:
                    await asyncio.sleep(self._retry_delay_seconds * (attempt + 1))
                    continue
                if "deserializing response" in details.lower():
                    raise DynamicDeserializeError(
                        f"Failed to deserialize dynamic response for uid={uid_text}: {details}"
                    ) from exc
                raise DynamicFetchError(
                    f"Failed to fetch dynamic response for uid={uid_text}: {exc.code()} {details}"
                ) from exc

        return self._parse_response(uid_text, response)

    def _request_dyn_space(self, uid: int) -> dynamic_pb2.DynSpaceRsp:
        channel = grpc.secure_channel(self._target, grpc.ssl_channel_credentials())
        try:
            stub = dynamic_pb2_grpc.DynamicStub(channel)
            request = dynamic_pb2.DynSpaceReq(host_uid=uid, history_offset="", page=1)
            return stub.DynSpace(request, metadata=tuple(), timeout=self._timeout_seconds)
        finally:
            channel.close()

    @staticmethod
    def _parse_response(uid: str, response: dynamic_pb2.DynSpaceRsp) -> list[DynamicItem]:
        items: list[DynamicItem] = []
        for raw in response.list:
            dyn_id_text = raw.extend.dyn_id_str.strip()
            if not dyn_id_text.isdigit():
                continue

            author_name = ""
            cover_url = DynamicClient._normalize_url(raw.extend.orig_img_url)
            for module in raw.modules:
                if module.HasField("module_author"):
                    author_name = module.module_author.author.name.strip()
                if module.HasField("module_dynamic"):
                    if module.module_dynamic.HasField("dyn_draw"):
                        for draw in module.module_dynamic.dyn_draw.items:
                            normalized = DynamicClient._normalize_url(draw.src)
                            if normalized:
                                cover_url = normalized
                                break
                    if not cover_url and module.module_dynamic.HasField("dyn_archive"):
                        cover_url = DynamicClient._normalize_url(module.module_dynamic.dyn_archive.cover)
                if author_name and cover_url:
                    break

            card_type = int(raw.card_type)
            items.append(
                DynamicItem(
                    uid=uid,
                    dyn_id=int(dyn_id_text),
                    card_type=card_type,
                    card_type_label=CARD_TYPE_LABELS.get(card_type, f"type_{card_type}"),
                    author_name=author_name,
                    cover_url=cover_url,
                )
            )

        return items

    @staticmethod
    def _normalize_url(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        if raw.startswith("//"):
            raw = f"https:{raw}"
        elif raw.startswith("http://"):
            raw = f"https://{raw[len('http://'):]}"
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"}:
            return ""
        if not parsed.netloc:
            return ""
        return raw
