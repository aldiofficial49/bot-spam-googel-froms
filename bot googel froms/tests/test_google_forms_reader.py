import json

import httpx
import pytest

from engine.google_forms_reader import (
    GoogleFormsReadError,
    GoogleFormsReader,
    parse_google_form_html,
)


def _form_html() -> str:
    multiple_choice = [
        123,
        "How often?",
        "",
        2,
        [[456, [["Often"], ["Sometimes"]], 1]],
    ]
    checkbox = [124, "Which areas?", "", 4, [[457, [["Safety"], ["Support"]], 0]]]
    scale = [125, "Rate safety", "", 5, [[458, None, 1, [1, 5], ["Low", "High"]]]]
    form_data = [None] * 9
    form_data[1] = [multiple_choice, checkbox, scale]
    form_data[8] = "Public QA Form"
    html = (
        "<html><head></head><body><script>var FB_PUBLIC_LOAD_DATA_ = "
        + json.dumps([None, form_data])
        + ";</script></body></html>"
    )
    return html


def test_parse_google_form_questions_and_scale_bounds() -> None:
    form = parse_google_form_html(_form_html())
    assert form.form_title == "Public QA Form"
    assert [question.type for question in form.questions] == [
        "multiple_choice",
        "checkbox",
        "scale",
    ]
    assert form.questions[0].required is True
    assert form.questions[0].options == ["Often", "Sometimes"]
    assert form.questions[2].min_value == 1
    assert form.questions[2].max_value == 5


def test_reader_strips_query_and_reads_only_public_form_data() -> None:
    seen: list[httpx.URL] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=_form_html(),
        )

    reader = GoogleFormsReader(transport=httpx.MockTransport(respond))
    form = reader.read(
        "https://docs.google.com/forms/d/FORM_ID/viewform?entry.123=private-answer"
    )
    assert form.form_title == "Public QA Form"
    assert len(form.questions) == 3
    assert seen[0].query == b""


@pytest.mark.parametrize(
    "url",
    [
        "http://docs.google.com/forms/d/FORM_ID/viewform",
        "https://example.com/forms/d/FORM_ID/viewform",
        "https://docs.google.com/forms/d/FORM_ID/viewformResponse",
        "https://user:pass@docs.google.com/forms/d/FORM_ID/viewform",
    ],
)
def test_reader_rejects_non_public_viewform_urls(url: str) -> None:
    with pytest.raises(GoogleFormsReadError, match="Only public https"):
        GoogleFormsReader().read(url)


def test_reader_rejects_redirects_outside_google_forms() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302, headers={"location": "https://example.com/redirect"}
        )
    )
    with pytest.raises(GoogleFormsReadError, match="Only public https"):
        GoogleFormsReader(transport=transport).read(
            "https://docs.google.com/forms/d/FORM_ID/viewform"
        )


def test_reader_explains_when_public_questions_are_not_available() -> None:
    with pytest.raises(GoogleFormsReadError, match="may require login"):
        parse_google_form_html("<html><body>Login required</body></html>")
