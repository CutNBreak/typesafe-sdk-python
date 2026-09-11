"""Base msgspec structs shared by the response schemas."""

import re
from functools import cached_property

import httpx2
import msgspec
from msgspec.structs import force_setattr
from typing_extensions import Self

from typesafe_sdk._core.constants import REQUEST_ID_HEADER
from typesafe_sdk._core.errors import TypeSafeAPIResponseValidationError, TypeSafeError, api_error
from typesafe_sdk._core.json import deserialize


# Unknown fields in a response are ignored rather than rejected, so a newer server never breaks
# an older client.
class Schema(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=False):
    """Base type for response objects. Instances are immutable."""


_ERROR_AT = re.compile(r"`\$(?P<path>[^`]*)`")
_ERROR_MISSING = re.compile(r"missing required field `(?P<field>[^`]+)`")


def field_path(prefix: tuple[str, ...], error: msgspec.DecodeError) -> str:
    """Translate a msgspec decode error's location into the SDK's dotted `field_path`."""
    message = str(error)
    segments: list[str] = []
    at = _ERROR_AT.search(message)
    if at is not None:
        segments = [segment for segment in at.group("path").split(".") if segment]
    elif (missing := _ERROR_MISSING.search(message)) is not None:
        segments = [missing.group("field")]
    return ".".join((*prefix, *segments))


def validation_error(response: httpx2.Response, path: str) -> TypeSafeAPIResponseValidationError:
    """Build a `TypeSafeAPIResponseValidationError` locating a bad field in `response`."""
    return TypeSafeAPIResponseValidationError(response.status_code, deserialize(response.content), response.headers, path)


# dict=True gives the struct a __dict__ so subclasses can memoize derived views with cached_property.
class Response(Schema, frozen=True, kw_only=True, dict=True):
    """A response object that also exposes the originating HTTP response via ``raw_http_response`` and ``request_id``."""

    _request_id: str | None = None
    _raw: httpx2.Response | None = None

    @classmethod
    def from_http_response(cls, response: httpx2.Response) -> Self:
        """Parse an HTTP response into this response type, attaching the raw response.

        A non-success status raises the matching `TypeSafeAPIError`; a body that does not
        match the schema raises a `TypeSafeAPIResponseValidationError`.
        """
        if not response.is_success:
            raise api_error(response.status_code, deserialize(response.content), response.headers)
        try:
            result = cls._decode(response)
        except msgspec.DecodeError as error:
            raise validation_error(response, field_path((), error)) from error
        force_setattr(result, "_request_id", response.headers.get(REQUEST_ID_HEADER))
        force_setattr(result, "_raw", response)
        return result

    @classmethod
    def _decode(cls, response: httpx2.Response) -> Self:
        """Build the response from its HTTP body. Subclasses implement the type-specific decode."""
        raise NotImplementedError

    @cached_property
    def request_id(self) -> str:
        """The ``x-typesafe-request-id`` response header."""
        if self._request_id is None:
            raise TypeSafeError("The response did not include a request ID.")
        return self._request_id

    @property
    def raw_http_response(self) -> httpx2.Response:
        """The underlying `httpx2.Response`, exposing status, headers, and body."""
        if self._raw is None:
            raise TypeSafeError("The response was not created from a raw HTTP response.")
        return self._raw
