import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


QuestionType = Literal[
    "multiple_choice", "checkbox", "scale", "short_answer", "paragraph"
]


class Question(BaseModel):
    id: str
    type: QuestionType
    label: str
    options: list[str] = Field(default_factory=list)
    required: bool = False
    min_value: int | None = None
    max_value: int | None = None

    @field_validator("id", "label")
    @classmethod
    def required_text_fields_are_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question id and label must not be blank.")
        return value

    @field_validator("options")
    @classmethod
    def options_are_unique_and_nonblank(cls, options: list[str]) -> list[str]:
        normalized = [option.strip() for option in options]
        if any(not option for option in normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("Question options must be nonblank and unique.")
        return normalized

    @model_validator(mode="after")
    def validate_type_constraints(self) -> "Question":
        if self.type in {"multiple_choice", "checkbox"} and not self.options:
            raise ValueError(f"{self.type} questions must define at least one option.")
        if self.type == "scale":
            if self.min_value is None or self.max_value is None:
                raise ValueError("Scale questions must define minimum and maximum values.")
            if self.min_value > self.max_value:
                raise ValueError("Scale minimum must not exceed its maximum.")
        return self


class FormDefinition(BaseModel):
    form_title: str
    questions: list[Question]

    @model_validator(mode="after")
    def validate_question_ids(self) -> "FormDefinition":
        if not self.form_title.strip():
            raise ValueError("Form title must not be blank.")
        if not self.questions:
            raise ValueError("Form must contain at least one question.")
        ids = [question.id for question in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError("Question ids must be unique within a form.")
        return self


def load_form(path: Path) -> FormDefinition:
    """Load the application's explicit JSON fixture format."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return FormDefinition.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Could not load form fixture '{path}': {exc}") from exc


def parse_local_html(path: Path) -> FormDefinition:
    """Parse the deliberately small, accessible fixture HTML format.

    This parser is for local test fixtures only; it is not a Google Forms scraper.
    """
    from html.parser import HTMLParser

    class FixtureParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.title = ""
            self._in_title = False
            self.questions: list[Question] = []
            self._current: dict[str, object] | None = None
            self._label_depth = 0
            self._label_parts: list[str] = []
            self._options: list[str] = []
            self._in_option = False
            self._option_parts: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            attributes = dict(attrs)
            if tag == "title":
                self._in_title = True
            elif tag == "fieldset":
                self._current = {
                    "id": attributes.get("data-question-id", ""),
                    "type": attributes.get("data-question-type", "short_answer"),
                    "required": "required" in attributes,
                }
                self._label_parts = []
                self._options = []
            elif self._current is not None and tag == "input":
                input_type = attributes.get("type", "")
                if input_type in {"radio", "checkbox"} and attributes.get("value"):
                    self._options.append(attributes["value"])
                elif input_type == "number":
                    if attributes.get("min") is not None:
                        self._current["min_value"] = int(attributes["min"])
                    if attributes.get("max") is not None:
                        self._current["max_value"] = int(attributes["max"])
            elif self._current is not None and tag == "legend":
                self._label_depth += 1
            elif self._current is not None and tag == "option":
                self._in_option = True
                self._option_parts = []

        def handle_endtag(self, tag: str) -> None:
            if tag == "title":
                self._in_title = False
            elif tag == "legend" and self._label_depth:
                self._label_depth -= 1
            elif tag == "option" and self._in_option:
                self._options.append("".join(self._option_parts).strip())
                self._in_option = False
            elif tag == "fieldset" and self._current is not None:
                self._current["label"] = " ".join("".join(self._label_parts).split())
                self._current["options"] = self._options
                self.questions.append(Question.model_validate(self._current))
                self._current = None

        def handle_data(self, data: str) -> None:
            if self._in_title:
                self.title += data
            if self._label_depth:
                self._label_parts.append(data)
            if self._in_option:
                self._option_parts.append(data)

    parser = FixtureParser()
    try:
        parser.feed(path.read_text(encoding="utf-8"))
        parser.close()
        if not parser.questions:
            raise ValueError("HTML fixture contains no question fieldsets.")
        return FormDefinition(
            form_title=parser.title.strip() or path.stem,
            questions=parser.questions,
        )
    except (OSError, ValidationError) as exc:
        raise ValueError(f"Could not parse local HTML fixture '{path}': {exc}") from exc
