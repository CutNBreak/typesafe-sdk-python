import copy
import inspect
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, cast

import httpx2
import msgspec
import pytest

from tests.conftest import ClientFactory
from typesafe_sdk import (
    AsyncTypeSafeClient,
    Choice,
    ChoiceModel,
    Noul,
    NoulCriteria,
    NoulModel,
    Question,
    Questions,
    Score,
    ScoreModel,
    TypeSafeError,
)
from typesafe_sdk._core.questions import normalize_questions
from typesafe_sdk._schemas import models as wire


def test_normalization_preserves_objects_except_score_maps() -> None:
    questions = {
        "noul": Noul(instructions="Spam?"),
        "choice": Choice(instructions="Tone?", criteria={"calm": None}),
        "score": Score(instructions="Quality?", criteria={1: "good", 0: "bad"}),
        "list_score": Score(criteria=["bad", "good"]),
    }
    result = normalize_questions(questions)
    assert result["noul"] is questions["noul"]
    assert result["choice"] is questions["choice"]
    assert result["list_score"] is questions["list_score"]
    assert result["score"] is not questions["score"]
    assert isinstance(result["score"], Score)
    assert questions["score"].criteria == {1: "good", 0: "bad"}
    assert msgspec.json.decode(msgspec.json.encode(result)) == {
        "noul": {"type": "noul", "instructions": "Spam?"},
        "choice": {"type": "choice", "instructions": "Tone?", "criteria": {"calm": None}},
        "score": {"type": "score", "instructions": "Quality?", "criteria": ["bad", "good"]},
        "list_score": {"type": "score", "criteria": ["bad", "good"]},
    }


@pytest.mark.parametrize(
    "raw",
    [
        {"type": "noul", "instructions": "Spam?", "weight": 3, "criteria": {"future": "kept"}},
        {"type": "future", "nested": {"k": None}},
        {"type": "score", "criteria": {0: "good"}, "weight": 3},
        {"type": "score", "criteria": ["good"], "weight": 3},
    ],
)
def test_normalization_preserves_raw_questions(raw: dict[str, Any]) -> None:
    before = copy.deepcopy(raw)
    questions = cast(Questions, {"raw": raw, "typed": Noul(instructions="Spam?")})
    result = normalize_questions(questions)
    expected = {**raw, "criteria": ["good"]} if raw["type"] == "score" else raw
    assert isinstance(result["typed"], wire.NoulQuestion)
    assert msgspec.to_builtins(result) == {"raw": expected, "typed": {"type": "noul", "instructions": "Spam?"}}
    assert raw == before
    if not isinstance(raw.get("criteria"), dict) or raw["type"] != "score":
        assert result["raw"] is raw


@pytest.mark.parametrize(
    "invalid",
    [
        {},
        {"instructions": "Missing type"},
        {"type": "choice"},
        {"type": "score"},
        {"type": ""},
        {"type": None},
        {"type": 1},
        {"type": ["future"]},
        "noul",
        None,
    ],
)
def test_raw_questions_require_structural_keys(invalid: object) -> None:
    with pytest.raises(TypeSafeError, match='Question "invalid"'):
        normalize_questions(cast(Questions, {"invalid": invalid}))


@pytest.mark.parametrize(
    "question,expected",
    [
        (Noul(), {"type": "noul"}),
        (Choice(criteria={"a": None}), {"type": "choice", "criteria": {"a": None}}),
        (Score(criteria=["good"]), {"type": "score", "criteria": ["good"]}),
        (Noul(instructions="", criteria={}), {"type": "noul", "instructions": "", "criteria": {}}),
        (Noul(instructions=[], criteria={"true": None}), {"type": "noul", "instructions": [], "criteria": {"true": None}}),
    ],
)
def test_direct_encoding_omits_only_default_fields(question: Noul | Choice | Score, expected: dict[str, Any]) -> None:
    assert msgspec.json.decode(msgspec.json.encode(question)) == expected
    assert msgspec.to_builtins(question) == expected


def test_score_mutations_are_normalized_when_sending() -> None:
    score = Score(criteria=["initial"])
    score.criteria = {1: "good", 0: "bad"}
    assert msgspec.to_builtins(normalize_questions({"q": score})) == {"q": {"type": "score", "criteria": ["bad", "good"]}}
    assert score.criteria == {1: "good", 0: "bad"}
    score.criteria[3] = "gap"
    with pytest.raises(TypeSafeError, match="no gaps"):
        normalize_questions({"q": score})


def test_discriminators_are_automatic() -> None:
    noul = Noul(instructions="Spam?")
    choice = Choice(instructions="Tone?", criteria={"calm": None})
    score = Score(instructions="Quality?", criteria=["good"])
    for question, wire_type, tag in (
        (noul, wire.NoulQuestion, "noul"),
        (choice, wire.ChoiceQuestion, "choice"),
        (score, wire.ScoreQuestion, "score"),
    ):
        assert isinstance(question, msgspec.Struct)
        assert isinstance(question, wire_type)
        assert question.__struct_config__.tag == tag
        assert question.__struct_config__.tag_field == "type"
        assert msgspec.to_builtins(question)["type"] == tag
        assert msgspec.json.decode(msgspec.json.encode(question))["type"] == tag
        assert not hasattr(question, "type")
        assert not hasattr(question, "__dict__")
        signature = inspect.signature(type(question))
        assert "type" not in signature.parameters
        assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in signature.parameters.values())
        with pytest.raises(TypeError):
            cast(Any, type(question))("Spam?")
        with pytest.raises(AttributeError):
            cast(Any, question).type = "other"
        question.instructions = "Updated?"
        assert msgspec.to_builtins(question)["instructions"] == "Updated?"


@pytest.mark.parametrize("raw", [False, True])
@pytest.mark.parametrize(
    "criteria",
    [
        None,
        {},
        {"true": "Yes"},
        {"false": "No"},
        {"true": "Yes", "false": "No"},
        {"true": {"summary": "Unsolicited", "examples": ["Buy now"]}},
    ],
)
def test_optional_noul_criteria(raw: bool, criteria: NoulCriteria | None) -> None:
    expected: NoulModel = {"type": "noul", "instructions": "Spam?"}
    if criteria is not None:
        expected["criteria"] = criteria
    question: Question
    if raw:
        question = expected.copy()
    else:
        question = Noul(instructions="Spam?", criteria=criteria)
    assert msgspec.to_builtins(normalize_questions({"q": question})) == {"q": expected}


@pytest.mark.parametrize("raw", [False, True])
@pytest.mark.parametrize("criteria", [[], {}, {0: "bad", 2: "good"}, {-1: "bad"}, {False: "bad"}, {0: "bad", True: "good"}])
def test_score_validation_preserves_inputs(raw: bool, criteria: list[str] | dict[int, str]) -> None:
    model = cast(ScoreModel, {"type": "score", "instructions": "Quality?", "criteria": criteria})
    question = model if raw else Score(instructions=model["instructions"], criteria=model["criteria"])
    before = copy.deepcopy(criteria)
    with pytest.raises(TypeSafeError, match='"rating"'):
        normalize_questions({"rating": question})
    assert criteria == before


async def test_covariant_question_mappings(clients: ClientFactory) -> None:
    nouls = {"q": Noul(instructions="Spam?")}
    choices = {"q": Choice(instructions="Tone?", criteria={"calm": None})}
    scores = {"q": Score(instructions="Quality?", criteria={0: "good"})}
    raw_nouls: dict[str, NoulModel] = {"q": {"type": "noul", "instructions": "Spam?"}}
    raw_choices: dict[str, ChoiceModel] = {"q": {"type": "choice", "instructions": "Tone?", "criteria": {"calm": None}}}
    raw_scores: dict[str, ScoreModel] = {"q": {"type": "score", "instructions": "Quality?", "criteria": {0: "good"}}}
    read_only: Mapping[str, Choice] = MappingProxyType(choices)
    mixed: Questions = {"one": nouls["q"], "two": raw_choices["q"], "three": scores["q"]}
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        assert msgspec.json.decode(request.content)["questions"]
        return httpx2.Response(200, json={"model": "jev-latest", "usage": {}, "answers": {}})

    client = clients(handler)
    if isinstance(client, AsyncTypeSafeClient):
        await client.system_one("x", nouls)
        await client.system_one("x", choices)
        await client.system_one("x", scores)
        await client.system_one("x", raw_nouls)
        await client.system_one("x", raw_choices)
        await client.system_one("x", raw_scores)
        await client.system_one("x", read_only)
        await client.system_one("x", mixed)
        await client.system_one("x", {"q": {"type": "choice", "instructions": "Tone?", "criteria": {"calm": None}}})
    else:
        client.system_one("x", nouls)
        client.system_one("x", choices)
        client.system_one("x", scores)
        client.system_one("x", raw_nouls)
        client.system_one("x", raw_choices)
        client.system_one("x", raw_scores)
        client.system_one("x", read_only)
        client.system_one("x", mixed)
        client.system_one("x", {"q": {"type": "choice", "instructions": "Tone?", "criteria": {"calm": None}}})
    assert calls == 9
    assert scores["q"].criteria == {0: "good"}
    assert raw_scores["q"]["criteria"] == {0: "good"}
    assert read_only["q"] is choices["q"]
