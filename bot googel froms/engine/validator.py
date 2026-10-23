from engine.form_parser import Question


def validate_answer(question: Question, answer: object) -> tuple[bool, str]:
    if answer is None or answer == "" or answer == [] or (
        isinstance(answer, str) and not answer.strip()
    ):
        return (not question.required, "required answer is missing" if question.required else "valid")

    if question.type == "multiple_choice":
        valid = isinstance(answer, str) and answer in question.options
    elif question.type == "checkbox":
        valid = (
            isinstance(answer, list)
            and all(isinstance(item, str) and item in question.options for item in answer)
        )
    elif question.type == "scale":
        valid = isinstance(answer, int) and not isinstance(answer, bool)
        if valid and question.min_value is not None:
            valid = answer >= question.min_value
        if valid and question.max_value is not None:
            valid = answer <= question.max_value
    else:
        valid = isinstance(answer, str) and bool(answer.strip())
        if valid and question.type == "short_answer":
            valid = len(answer.strip()) <= 120
        if valid and question.type == "paragraph":
            valid = len(answer.strip()) <= 5000

    return (
        valid,
        "valid"
        if valid
        else f"answer does not match {question.type} requirements (text limits: short 120, paragraph 5000 characters)",
    )
