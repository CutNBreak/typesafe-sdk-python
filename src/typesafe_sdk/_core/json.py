"""JSON encoding and lenient response decoding."""

from collections.abc import Mapping, Sequence
from typing import Any

import msgspec


def _enc_hook(value: object) -> object:
    """Materialize abstract input containers (any `Mapping`/`Sequence`) into JSON-encodable types.

    Public input types are declared as `Mapping`/`Sequence` so callers may pass, for example, a
    `MappingProxyType` or a tuple; msgspec natively encodes only concrete `dict`/`list`/`tuple`.
    """
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, Sequence):
        return list(value)
    raise TypeError(f"Encoding objects of type {type(value).__name__} is unsupported")


def serialize(value: object) -> bytes:
    return msgspec.json.encode(value, enc_hook=_enc_hook)


def deserialize(content: bytes) -> Any:
    if not content:
        return None
    try:
        return msgspec.json.decode(content)
    except msgspec.DecodeError:
        return content.decode("utf-8", errors="replace")
