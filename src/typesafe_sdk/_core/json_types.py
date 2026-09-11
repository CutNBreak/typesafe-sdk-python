"""Shared JSON value types."""

from typing import TypeAlias

JSONValue: TypeAlias = str | int | float | bool | list["JSONValue | None"] | dict[str, "JSONValue | None"]
"""A non-null JSON value, with null permitted inside arrays and objects."""
