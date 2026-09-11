import httpx2
import pytest

from tests.conftest import ClientFactory
from tests.helpers import models
from typesafe_sdk import (
    TypeSafeAPIError,
    TypeSafeAuthenticationError,
    TypeSafeBadRequestError,
    TypeSafeInternalServerError,
    TypeSafeNotFoundError,
    TypeSafePermissionDeniedError,
    TypeSafeRateLimitError,
    TypeSafeUnprocessableEntityError,
)


@pytest.mark.parametrize(
    "error_type",
    [
        TypeSafeAPIError,
        TypeSafeBadRequestError,
        TypeSafeAuthenticationError,
        TypeSafePermissionDeniedError,
        TypeSafeNotFoundError,
        TypeSafeUnprocessableEntityError,
        TypeSafeRateLimitError,
        TypeSafeInternalServerError,
    ],
)
@pytest.mark.parametrize("message", ["A custom explanation", ""])
def test_message_override(error_type: type[TypeSafeAPIError], message: str) -> None:
    headers = httpx2.Headers({"retry-after-ms": "125"})
    body = {"message": "Server explanation"}
    error = error_type(429, body, headers, message=message)
    assert str(error) == message
    assert error.status == 429
    assert error.body is body
    assert error.headers is headers
    assert error.request_id is None
    if isinstance(error, TypeSafeRateLimitError):
        assert error.retry_after_ms == 125


@pytest.mark.parametrize(
    "body,message",
    [
        (b"", "400 status code (no body)"),
        (b"null", "400 status code (no body)"),
        (b"[]", "400 []"),
        (b"42", "400 42"),
        (b"not JSON: \xff", "400 not JSON: \ufffd"),
        pytest.param(b"x" * 201, "400 " + "x" * 201, id="long-plain-message"),
        pytest.param(b'{"unknown":"' + b"x" * 201 + b'"}', '400 {"unknown":"' + "x" * 188 + "…", id="long-unstructured-body"),
        (b'{"error":"","message":"ignored"}', '400 {"error":"","message":"ignored"}'),
        (b'{"detail":[null,42,{"msg":4}]}', '400 {"detail":[null,42,{"msg":4}]}'),
    ],
)
async def test_error_body_edge_cases(clients: ClientFactory, body: bytes, message: str) -> None:
    with pytest.raises(TypeSafeAPIError) as caught:
        await models(clients(lambda request: httpx2.Response(400, content=body)))
    assert str(caught.value) == message
    assert caught.value.request_id is None
