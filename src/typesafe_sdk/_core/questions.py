"""Question normalization before JSON encoding."""

from collections.abc import Mapping
from typing import cast

import msgspec

from typesafe_sdk._core.errors import TypeSafeError
from typesafe_sdk._core.json_types import JSONValue
from typesafe_sdk._core.question_types import Choice, Noul, Question, Score, ScoreModel


def normalize_questions(questions: Mapping[str, Question]) -> dict[str, Question]:
    if not questions:
        raise TypeSafeError("At least one question is required.")
    result: dict[str, Question] = {}
    for name, question in questions.items():
        result[name] = question
        if isinstance(question, Score):
            criteria = _normalize_score_criteria(name, question.criteria)
            if criteria is not question.criteria:
                result[name] = msgspec.structs.replace(question, criteria=criteria)
        elif not isinstance(question, (Noul, Choice)):
            if not isinstance(question, dict) or not isinstance(question.get("type"), str) or not question["type"]:
                raise TypeSafeError(f'Question "{name}" must be a question object or a dictionary with a nonempty string "type".')
            if question["type"] in ("choice", "score") and "criteria" not in question:
                raise TypeSafeError(f'Question "{name}" requires "criteria".')
            if question["type"] == "score":
                criteria = _normalize_score_criteria(name, question["criteria"])
                if criteria is not question["criteria"]:
                    result[name] = cast(ScoreModel, {**question, "criteria": criteria})
    return result


def _normalize_score_criteria(
    name: str,
    criteria: list[str | dict[str, JSONValue | None] | list[JSONValue | None]]
    | dict[int, str | dict[str, JSONValue | None] | list[JSONValue | None]],
) -> list[str | dict[str, JSONValue | None] | list[JSONValue | None]]:
    """Validate a score question's criteria and normalize a keyed dict into a gap-free ordered list."""
    if not criteria:
        raise TypeSafeError(f'Score question "{name}" has no criteria; at least one score is required.')
    if isinstance(criteria, dict):
        if any(type(key) is not int or key < 0 for key in criteria):
            raise TypeSafeError(f'Score question "{name}" keys must be non-negative integers.')
        if sorted(criteria) != list(range(len(criteria))):
            raise TypeSafeError(f'Score question "{name}" defines scores {sorted(criteria)}, but scores must run from 0 with no gaps.')
        return [criteria[index] for index in range(len(criteria))]
    return criteria
