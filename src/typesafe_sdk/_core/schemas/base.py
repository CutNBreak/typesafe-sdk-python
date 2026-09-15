"""Base msgspec structs shared by the response schemas."""

import re
from functools import cached_property

import httpx2
import msgspec
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
    if (missing := _ERROR_MISSING.search(message)) is not None:
        segments.append(missing.group("field"))
    return ".".join((*prefix, *segments))


def _request_endpoint(response: httpx2.Response) -> str | None:
    """Describe the endpoint if the response has an originating request."""
    try:
        request = response.request
    except RuntimeError:
        return None
    return f"{request.method} {request.url.copy_with(userinfo=b'', query=None, fragment=None)}"


def validation_error(response: httpx2.Response, path: str) -> TypeSafeAPIResponseValidationError:
    """Build a `TypeSafeAPIResponseValidationError` locating a bad field in `response`."""
    return TypeSafeAPIResponseValidationError(
        response.status_code, deserialize(response.content), response.headers, path, _request_endpoint(response)
    )


# dict=True gives the struct a __dict__ so subclasses can memoize derived views with cached_property.
class Response(Schema, frozen=True, kw_only=True, dict=True):
    """A response object that also exposes the originating HTTP response via ``raw_http_response`` and ``request_id``."""

    def __copy__(self) -> Self:
        """Copy response fields and runtime metadata."""
        result = msgspec.structs.replace(self)
        result.__dict__.update(self.__dict__)
        return result

    def __reduce__(self) -> tuple[object, ...]:
        """Preserve runtime metadata during deep copies and pickling."""
        return (*super().__reduce__(), self.__dict__)

    @classmethod
    def from_http_response(cls, response: httpx2.Response) -> Self:
        """Parse an HTTP response into this response type, attaching the raw response.

        A non-success status raises the matching `TypeSafeAPIError`; a body that does not
        match the schema raises a `TypeSafeAPIResponseValidationError`.
        """
        if not response.is_success:
            raise api_error(response.status_code, deserialize(response.content), response.headers, _request_endpoint(response))
        try:
            result = cls._decode(response)
        except msgspec.DecodeError as error:
            raise validation_error(response, field_path((), error)) from error
        # Transport metadata is runtime state, not part of the serializable response schema.
        result.__dict__["_request_id"] = response.headers.get(REQUEST_ID_HEADER)
        result.__dict__["_raw"] = response
        return result

    @classmethod
    def _decode(cls, response: httpx2.Response) -> Self:
        """Build the response from its HTTP body. Subclasses implement the type-specific decode."""
        raise NotImplementedError

    @cached_property
    def request_id(self) -> str:
        """The ``x-typesafe-request-id`` response header."""
        request_id: str | None = self.__dict__.get("_request_id")
        if request_id is None:
            raise TypeSafeError("The response did not include a request ID.")
        return request_id

    @property
    def raw_http_response(self) -> httpx2.Response:
        """The underlying `httpx2.Response`, exposing status, headers, and body."""
        response: httpx2.Response | None = self.__dict__.get("_raw")
        if response is None:
            raise TypeSafeError("The response was not created from a raw HTTP response.")
        return response
