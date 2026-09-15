"""Question objects and raw input models."""

from collections.abc import Mapping, Sequence
from typing import Literal, TypeAlias

from typing_extensions import NotRequired, TypedDict

from typesafe_sdk._core.json_types import JSONContent, JSONValue
from typesafe_sdk._schemas import models as wire


class NoulCriteria(TypedDict, total=False, extra_items=JSONValue | None):
    """Optional descriptions of the yes and no outcomes.

    See the [noul primitive](https://docs.typesafe.ai/primitives/noul) for details.
    """

    true: JSONContent | None
    """Description of the yes outcome as text, a JSON object, or an array; `None` leaves it undescribed."""
    false: JSONContent | None
    """Description of the no outcome as text, a JSON object, or an array; `None` leaves it undescribed."""


class NoulModel(TypedDict, extra_items=JSONValue | None):
    """A yes/no question dictionary with `type="noul"`, allowing extra JSON fields.

    See the [noul primitive](https://docs.typesafe.ai/primitives/noul) for details.
    """

    type: Literal["noul"]
    instructions: NotRequired[JSONContent | None]
    """The question to ask, expressed as text, a JSON object, or an array; optional."""
    criteria: NotRequired[NoulCriteria | None]
    """Optional descriptions of the yes and no outcomes."""


class ChoiceModel(TypedDict, extra_items=JSONValue | None):
    """A choice question dictionary with `type="choice"`, allowing extra JSON fields.

    See the [choice primitive](https://docs.typesafe.ai/primitives/choice) for details.
    """

    type: Literal["choice"]
    instructions: NotRequired[JSONContent | None]
    """The question to ask, expressed as text, a JSON object, or an array; optional."""
    criteria: Mapping[str, JSONContent | None]
    """Labels mapped to text, object, or array descriptions, or `None` for undescribed labels."""


class ScoreModel(TypedDict, extra_items=JSONValue | None):
    """A score question dictionary with `type="score"`, allowing extra JSON fields.

    See the [score primitive](https://docs.typesafe.ai/primitives/score) for details.
    """

    type: Literal["score"]
    instructions: NotRequired[JSONContent | None]
    """The question to ask, expressed as text, a JSON object, or an array; optional."""
    criteria: Sequence[JSONContent]
    """A nonempty, ordered list of text, object, or array descriptions, one per score from zero."""


class Noul(wire.NoulQuestion, kw_only=True, omit_defaults=True):
    """A yes/no question with optional descriptions for either outcome.

    See the [noul primitive](https://docs.typesafe.ai/primitives/noul) for details.
    """

    instructions: JSONContent | None = None  # pyrefly: ignore[bad-override-mutable-attribute]
    """The question to ask, expressed as text, a JSON object, or an array; optional."""
    criteria: NoulCriteria | None = None  # pyrefly: ignore[bad-override-mutable-attribute]
    """Optional descriptions of the yes and no outcomes."""


class Choice(wire.ChoiceQuestion, kw_only=True, omit_defaults=True):
    """A question that selects between named alternatives.

    See the [choice primitive](https://docs.typesafe.ai/primitives/choice) for details.
    """

    criteria: Mapping[str, JSONContent | None]  # pyrefly: ignore[bad-override-mutable-attribute]
    """Labels mapped to text, object, or array descriptions, or `None` for undescribed labels."""
    instructions: JSONContent | None = None  # pyrefly: ignore[bad-override-mutable-attribute]
    """The question to ask, expressed as text, a JSON object, or an array; optional."""


class Score(wire.ScoreQuestion, kw_only=True, omit_defaults=True):
    """A question that assigns a score using an ordered rubric.

    See the [score primitive](https://docs.typesafe.ai/primitives/score) for details.
    """

    criteria: Sequence[JSONContent]  # pyrefly: ignore[bad-override-mutable-attribute]
    """A nonempty, ordered list of text, object, or array descriptions, one per score from zero."""
    instructions: JSONContent | None = None  # pyrefly: ignore[bad-override-mutable-attribute]
    """The question to ask, expressed as text, a JSON object, or an array; optional."""


QuestionModel: TypeAlias = NoulModel | ChoiceModel | ScoreModel
"""A question dictionary identified by its `type` key."""
Question: TypeAlias = Noul | Choice | Score | QuestionModel
"""A question object or question dictionary."""
Questions: TypeAlias = Mapping[str, Question]
"""Question inputs keyed by the names used to identify their answers."""
