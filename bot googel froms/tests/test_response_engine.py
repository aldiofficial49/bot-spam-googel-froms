from typing import Any

from engine.form_parser import Question
from engine.response_engine import generate_response


class FakeClient:
    def __init__(self, answers: list[Any]) -> None:
        self.answers = answers
        self.calls = 0

    def chat_json(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        answer = self.answers[self.calls]
        self.calls += 1
        return {"answer": answer}


def test_response_engine_retries_invalid_model_answer_once() -> None:
    client = FakeClient(["not an option", "Standard"])
    question = Question(
        id="Q1",
        type="multiple_choice",
        label="Choose a path",
        options=["Standard", "Alternative"],
        required=True,
    )
    result = generate_response(
        client, question, "TEST-001", "baseline", {"synthetic": "true"}, {}
    )
    assert result["answer"] == "Standard"
    assert result["synthetic"] is True
    assert client.calls == 2


def test_response_engine_fails_after_bounded_correction() -> None:
    client = FakeClient(["wrong", "still wrong", "wrong again"])
    question = Question(
        id="Q1",
        type="multiple_choice",
        label="Choose a path",
        options=["Standard"],
    )
    try:
        generate_response(
            client, question, "TEST-001", "baseline", {"synthetic": "true"}, {}
        )
    except ValueError as exc:
        assert "after 2 correction attempts" in str(exc)
    else:
        raise AssertionError("Expected invalid model answer to fail after the retry.")
    assert client.calls == 3


def test_response_engine_allows_two_bounded_corrections() -> None:
    client = FakeClient(["wrong", "still wrong", "Standard"])
    question = Question(
        id="Q1",
        type="multiple_choice",
        label="Choose a path",
        options=["Standard"],
    )
    result = generate_response(
        client, question, "TEST-001", "baseline", {"synthetic": "true"}, {}
    )
    assert result["answer"] == "Standard"
    assert result["validation_attempts"] == 3
