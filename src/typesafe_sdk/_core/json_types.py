"""Shared JSON value types."""

from collections.abc import Mapping, Sequence
from typing import TypeAlias

JSONValue: TypeAlias = str | int | float | bool | Sequence["JSONValue | None"] | Mapping[str, "JSONValue | None"]
"""A JSON-like value. May be nested and contain `None`."""

JSONContent: TypeAlias = str | Mapping[str, JSONValue | None] | Sequence[JSONValue | None]
"""Either a plain string or a mapping/sequence of [`JSONValue`][typesafe_sdk.JSONValue] entries."""
