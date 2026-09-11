from typing import get_args, get_origin, get_type_hints

import httpx2
import msgspec
import pytest

from tests.conftest import ClientFactory
from tests.helpers import system_one
from typesafe_sdk import AsyncTypeSafeClient, Choice, JSONValue, Noul, Questions, Score, TypeSafeClient


def test_json_value_and_state_exclude_top_level_none() -> None:
    assert type(None) not in get_args(JSONValue)
    for client in (AsyncTypeSafeClient, TypeSafeClient):
        state_type = get_type_hints(client.system_one)["state"]
        assert type(None) not in get_args(state_type)
        text_type, object_type, array_type = get_args(state_type)
        assert text_type is str
        assert get_origin(object_type) is dict
        key_type, value_type = get_args(object_type)
        assert key_type is str
        assert type(None) in get_args(value_type)
        assert get_origin(array_type) is list
        assert type(None) in get_args(get_args(array_type)[0])


@pytest.mark.parametrize("raw", [False, True])
async def test_array_inputs(clients: ClientFactory, raw: bool) -> None:
    state: list[JSONValue | None] = [{"message": "Classify"}, None]
    instructions: list[JSONValue | None] = ["Read the message", {"context": None}]
    description: list[JSONValue | None] = ["Example", None]
    questions: Questions
    if raw:
        questions = {
            "yes": {"type": "noul", "instructions": instructions, "criteria": {"true": description, "false": None}},
            "label": {"type": "choice", "instructions": instructions, "criteria": {"a": description, "b": None}},
            "rating": {"type": "score", "instructions": instructions, "criteria": {0: description}},
        }
    else:
        questions = {
            "yes": Noul(instructions=instructions, criteria={"true": description, "false": None}),
            "label": Choice(instructions=instructions, criteria={"a": description, "b": None}),
            "rating": Score(instructions=instructions, criteria={0: description}),
        }

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = msgspec.json.decode(request.content)
        assert body["state"] == state
        assert body["questions"] == {
            "yes": {"type": "noul", "instructions": instructions, "criteria": {"true": description, "false": None}},
            "label": {"type": "choice", "instructions": instructions, "criteria": {"a": description, "b": None}},
            "rating": {"type": "score", "instructions": instructions, "criteria": [description]},
        }
        return httpx2.Response(200, json={"model": "jev-latest", "usage": {}, "answers": {}})

    await system_one(clients(handler), state=state, questions=questions)


async def test_raw_optional_fields_preserve_explicit_null(clients: ClientFactory) -> None:
    questions: Questions = {
        "yes": {"type": "noul", "instructions": None, "criteria": None},
        "label": {"type": "choice", "instructions": None, "criteria": {"a": None}},
        "rating": {"type": "score", "instructions": None, "criteria": ["good"]},
    }

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert msgspec.json.decode(request.content)["questions"] == questions
        return httpx2.Response(200, json={"model": "jev-latest", "usage": {}, "answers": {}})

    await system_one(clients(handler), state="x", questions=questions)


async def test_explicitly_nullable_json_values(clients: ClientFactory) -> None:
    state: dict[str, JSONValue | None] = {"missing": None, "items": [None, {"nested": None}]}
    instructions: dict[str, JSONValue | None] = {"text": "Classify", "extra": None}

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = msgspec.json.decode(request.content)
        assert body["state"] == state
        assert body["questions"] == {
            "yes": {"type": "noul", "instructions": instructions, "criteria": {"true": {"extra": None}}},
            "label": {"type": "choice", "instructions": instructions, "criteria": {"a": None, "b": {"extra": None}}},
            "rating": {"type": "score", "instructions": instructions, "criteria": [{"extra": None}]},
        }
        return httpx2.Response(200, json={"model": "jev-latest", "usage": {}, "answers": {}})

    client = clients(handler)
    questions = {
        "yes": Noul(instructions=instructions, criteria={"true": {"extra": None}}),
        "label": Choice(instructions=instructions, criteria={"a": None, "b": {"extra": None}}),
        "rating": Score(instructions=instructions, criteria=[{"extra": None}]),
    }
    if isinstance(client, AsyncTypeSafeClient):
        await client.system_one(state, questions)
    else:
        client.system_one(state, questions)
