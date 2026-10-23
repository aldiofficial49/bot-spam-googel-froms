from engine.form_parser import Question
from engine.validator import validate_answer


def test_multiple_choice_must_be_an_available_option() -> None:
    question = Question(id="Q1", type="multiple_choice", label="Pick", options=["A", "B"])
    assert validate_answer(question, "A") == (True, "valid")
    assert validate_answer(question, "C")[0] is False


def test_checkbox_values_must_be_available() -> None:
    question = Question(id="Q1", type="checkbox", label="Pick", options=["A", "B"], required=True)
    assert validate_answer(question, ["A", "B"])[0] is True
    assert validate_answer(question, ["C"])[0] is False
    assert validate_answer(question, [])[0] is False


def test_scale_and_required_text() -> None:
    scale = Question(id="Q1", type="scale", label="Scale", min_value=1, max_value=5)
    required_text = Question(id="Q2", type="short_answer", label="Text", required=True)
    assert validate_answer(scale, 5)[0] is True
    assert validate_answer(scale, 6)[0] is False
    assert validate_answer(required_text, " ")[0] is False


def test_text_lengths_are_bounded_by_question_type() -> None:
    short = Question(id="Q1", type="short_answer", label="Short")
    paragraph = Question(id="Q2", type="paragraph", label="Long")
    assert validate_answer(short, "x" * 120)[0] is True
    assert validate_answer(short, "x" * 121)[0] is False
    assert validate_answer(paragraph, "x" * 5001)[0] is False
