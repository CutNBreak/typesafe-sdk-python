"""JSON encoding and lenient response decoding."""

from typing import Any

import msgspec


def serialize(value: object) -> bytes:
    return msgspec.json.encode(value)


def deserialize(content: bytes) -> Any:
    if not content:
        return None
    try:
        return msgspec.json.decode(content)
    except msgspec.DecodeError:
        return content.decode("utf-8", errors="replace")
