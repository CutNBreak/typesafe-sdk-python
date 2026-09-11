from typing import Any, cast

import httpx2
import msgspec
import pytest
from typing_extensions import assert_type

from tests.conftest import ClientFactory
from tests.helpers import system_one
from tests.test_clients import RESULT
from typesafe_sdk import (
    Answer,
    ChoiceAnswer,
    NoulAnswer,
    ScoreAnswer,
    SystemOneResponse,
    TypeSafeAPIResponseValidationError,
    TypeSafeError,
    Usage,
)


@pytest.mark.parametrize(
    "answers,field_path",
    [
        ({}, "model"),
        ({"n": {"type": "noul"}}, "answers.n.noul"),
        ({"c": {"type": "choice", "choice": "a", "probabilities": {}}}, "answers.c.confidence"),
        ({"c": {"type": "choice", "confidence": 0.5, "probabilities": {}}}, "answers.c.choice"),
        ({"s": {"type": "score", "score": 1.0, "confidence": 1.0, "legend": [], "probabilities": {}}}, "answers.s.legend"),
        ({"s": {"type": "score", "score": 1.0, "confidence": 1.0, "legend": {"x": "bad"}, "probabilities": {}}}, "answers.s.legend"),
        ({"c": "not-a-mapping"}, "answers.c.type"),
    ],
)
async def test_malformed_response_raises_validation_error(clients: ClientFactory, answers: dict[str, Any], field_path: str) -> None:
    body: dict[str, Any] = {"usage": {"input_tokens": 1, "output_tokens": 1}, "answers": answers}
    if field_path != "model":
        body["model"] = "test"

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=body, headers={"x-typesafe-request-id": "req-123"})

    with pytest.raises(TypeSafeAPIResponseValidationError) as caught:
        await system_one(clients(handler), state="x", questions={"q": {"type": "noul", "instructions": "?"}})
    assert caught.value.field_path == field_path
    assert caught.value.status == 200
    assert caught.value.request_id == "req-123"
    assert caught.value.body == body


async def test_response_carries_request_id(clients: ClientFactory) -> None:
    result = await system_one(
        clients(lambda request: httpx2.Response(200, json=RESULT, headers={"x-typesafe-request-id": "req-42"})),
        state="text",
        questions={"q": {"type": "noul", "instructions": "?"}},
    )
    assert result.request_id == "req-42"


async def test_response_carries_raw_http_response(clients: ClientFactory) -> None:
    result = await system_one(
        clients(lambda request: httpx2.Response(200, json=RESULT, headers={"x-typesafe-request-id": "req-42"})),
        state="text",
        questions={"q": {"type": "noul", "instructions": "?"}},
    )
    assert result.raw_http_response.status_code == 200
    assert result.raw_http_response.headers["x-typesafe-request-id"] == "req-42"
    assert result.raw_http_response.json() == RESULT


def test_missing_raw_raises_on_access() -> None:
    result = SystemOneResponse(model="test", usage=Usage(), answers={})
    with pytest.raises(TypeSafeError, match="raw HTTP response"):
        _ = result.raw_http_response


async def test_missing_request_id_raises_on_access(clients: ClientFactory) -> None:
    result = await system_one(
        clients(lambda request: httpx2.Response(200, json=RESULT)),
        state="text",
        questions={"q": {"type": "noul", "instructions": "?"}},
    )
    with pytest.raises(TypeSafeError, match="request ID"):
        _ = result.request_id


async def test_unknown_extra_fields_tolerated(clients: ClientFactory) -> None:
    body = {
        "model": "test",
        "usage": {"input_tokens": 1, "output_tokens": 1, "reasoning_tokens": 9, "billing_units": 1},
        "answers": {"spam": {"type": "noul", "noul": 0.9, "explanation": "spammy"}},
    }
    result = await system_one(
        clients(lambda request: httpx2.Response(200, json=body)),
        state="x",
        questions={"q": {"type": "noul", "instructions": "?"}},
    )
    assert result.nouls["spam"].noul == 0.9
    assert not hasattr(result.usage, "billing_units")
    assert msgspec.to_builtins(result.usage) == {"input_tokens": 1, "output_tokens": 1}


async def test_unknown_answer_type_ignored(clients: ClientFactory) -> None:
    body = {
        "model": "test",
        "usage": {"input_tokens": 1, "output_tokens": 1},
        "answers": {
            "spam": {"type": "noul", "noul": 0.9},
            "mystery": {"type": "aurora", "value": 3},
        },
    }
    result = await system_one(
        clients(lambda request: httpx2.Response(200, json=body, headers={"x-typesafe-request-id": "req-9"})),
        state="text",
        questions={"q": {"type": "noul", "instructions": "?"}},
    )
    # A future answer type this SDK version does not model is skipped, not raised.
    assert set(result.answers) == {"spam"}
    assert result.nouls["spam"].noul == 0.9
    # The unknown answer is still available in the raw response.
    assert result.raw_http_response.json()["answers"]["mystery"]["type"] == "aurora"


def test_response_preserves_nested_json() -> None:
    original = ScoreAnswer(
        score=0.0,
        confidence=1.0,
        legend={0: {"examples": ["a", {"note": None}]}},
        probabilities={0: 1.0},
    )
    result = SystemOneResponse(
        model="test",
        usage=Usage(input_tokens=1, output_tokens=1),
        answers={"q": original},
    )
    assert not result.choices
    answer = result.scores["q"]
    assert answer is original
    assert answer is result.answers["q"]
    assert isinstance(result.usage, Usage)
    assert answer.probabilities == {0: 1.0}
    entry = answer.legend[0]
    assert isinstance(entry, dict)
    assert entry["examples"] == ["a", {"note": None}]
    examples = entry["examples"]
    assert isinstance(examples, list)
    assert isinstance(examples[1], dict)

    exported = msgspec.to_builtins(answer)
    assert exported == {
        "type": "score",
        "score": 0.0,
        "confidence": 1.0,
        "legend": {0: {"examples": ["a", {"note": None}]}},
        "probabilities": {0: 1.0},
    }
    # to_builtins returns an independent deep copy: mutating it leaves the struct untouched.
    exported["legend"][0]["examples"].append("new")
    exported["probabilities"][0] = 0.5
    assert examples == ["a", {"note": None}]
    assert answer.probabilities == {0: 1.0}


def test_answer_attributes_and_dictionary_types() -> None:
    noul = NoulAnswer(noul=0.98)
    choice = ChoiceAnswer(choice="billing", confidence=0.9, probabilities={"billing": 0.9, "support": 0.1})
    assert_type(noul.noul, float)
    assert_type(choice.choice, str)
    assert_type(choice.confidence, float)
    assert_type(choice.probabilities, dict[str, float])
    assert msgspec.to_builtins(noul) == {"type": "noul", "noul": 0.98}
    assert msgspec.to_builtins(choice) == {
        "type": "choice",
        "choice": "billing",
        "confidence": 0.9,
        "probabilities": {"billing": 0.9, "support": 0.1},
    }


@pytest.mark.parametrize(
    "answer",
    [
        NoulAnswer(noul=0.98),
        ChoiceAnswer(choice="billing", confidence=1.0, probabilities={"billing": 1.0}),
        ScoreAnswer(score=0.0, confidence=1.0, legend={0: "bad"}, probabilities={0: 1.0}),
    ],
)
def test_answer_fields_are_frozen_and_slotted(answer: Answer) -> None:
    assert not hasattr(answer, "__dict__")
    with pytest.raises(AttributeError):
        cast(Any, answer).type = "other"


@pytest.mark.parametrize("group", ["nouls", "choices", "scores"])
def test_cached_groups_cannot_be_reassigned(group: str) -> None:
    result = SystemOneResponse(model="test", usage=Usage(), answers={})
    with pytest.raises(AttributeError):
        setattr(result, group, {})
    cached = getattr(result, group)
    assert getattr(result, group) is cached
    with pytest.raises(AttributeError):
        setattr(result, group, {})
