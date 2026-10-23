import json
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from pydantic import ValidationError

from engine.form_parser import FormDefinition, Question


MAX_PAGE_BYTES = 4 * 1024 * 1024
MAX_REDIRECTS = 5
QUESTION_TYPES = {
    0: "short_answer",
    1: "paragraph",
    2: "multiple_choice",
    3: "multiple_choice",
    4: "checkbox",
    5: "scale",
}


class GoogleFormsReadError(ValueError):
    """A public Google Form could not safely be read as a question fixture."""


def _normalize_form_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as exc:
        raise GoogleFormsReadError(f"Invalid Google Forms URL: {exc}") from exc

    if (
        parts.scheme.lower() != "https"
        or parts.hostname != "docs.google.com"
        or parts.username is not None
        or parts.password is not None
        or port not in (None, 443)
        or not re.fullmatch(r"/forms/d/(?:e/)?[A-Za-z0-9_-]+/viewform/?", parts.path)
    ):
        raise GoogleFormsReadError(
            "Only public https://docs.google.com/forms/d/.../viewform URLs are supported."
        )

    return urlunsplit(("https", "docs.google.com", parts.path, "", ""))


def _extract_json_array(source: str) -> object:
    marker = "FB_PUBLIC_LOAD_DATA_"
    marker_position = source.find(marker)
    if marker_position < 0:
        raise GoogleFormsReadError(
            "Google Forms question data is not available. The form may require login "
            "or may not be a public viewform."
        )

    start = source.find("[", marker_position + len(marker))
    if start < 0:
        raise GoogleFormsReadError("Google Forms returned malformed public question data.")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(source[start : index + 1])
                except json.JSONDecodeError as exc:
                    raise GoogleFormsReadError(
                        f"Google Forms returned invalid question data: {exc}"
                    ) from exc

    raise GoogleFormsReadError("Google Forms returned incomplete public question data.")


def _parse_question(raw: object, index: int) -> Question:
    if not isinstance(raw, list) or len(raw) < 5:
        raise GoogleFormsReadError(f"Question {index} has an unsupported data structure.")

    question_id, label, question_type = raw[0], raw[1], raw[3]
    if not isinstance(question_id, (int, str)) or not isinstance(label, str):
        raise GoogleFormsReadError(f"Question {index} is missing its id or label.")
    if question_type not in QUESTION_TYPES:
        raise GoogleFormsReadError(
            f"Question '{label}' uses unsupported Google Forms type {question_type}."
        )

    metadata_container = raw[4]
    if not isinstance(metadata_container, list) or not metadata_container:
        raise GoogleFormsReadError(f"Question '{label}' has unsupported answer metadata.")
    metadata = (
        metadata_container[0]
        if isinstance(metadata_container[0], list)
        else metadata_container
    )
    if not isinstance(metadata, list):
        raise GoogleFormsReadError(f"Question '{label}' has unsupported answer metadata.")

    required = len(metadata) > 2 and metadata[2] == 1
    normalized_type = QUESTION_TYPES[question_type]
    options: list[str] = []
    min_value = None
    max_value = None

    if normalized_type in {"multiple_choice", "checkbox"}:
        if len(metadata) < 2 or not isinstance(metadata[1], list):
            raise GoogleFormsReadError(f"Question '{label}' has no readable answer options.")
        for option in metadata[1]:
            if isinstance(option, list) and option and isinstance(option[0], str):
                options.append(option[0])
        if not options:
            raise GoogleFormsReadError(f"Question '{label}' has no readable answer options.")
    elif normalized_type == "scale":
        bounds = metadata[3] if len(metadata) > 3 else None
        if (
            not isinstance(bounds, list)
            or len(bounds) != 2
            or not all(isinstance(value, int) for value in bounds)
        ):
            raise GoogleFormsReadError(f"Scale bounds could not be read for question '{label}'.")
        min_value, max_value = bounds

    try:
        return Question(
            id=str(question_id),
            type=normalized_type,
            label=label,
            options=options,
            required=required,
            min_value=min_value,
            max_value=max_value,
        )
    except ValidationError as exc:
        raise GoogleFormsReadError(
            f"Question '{label}' failed validation: {exc}"
        ) from exc


def parse_google_form_html(source: str) -> FormDefinition:
    data = _extract_json_array(source)
    if not isinstance(data, list) or len(data) < 2:
        raise GoogleFormsReadError("Google Forms returned an unexpected form data structure.")

    form_data = data[1]
    if not isinstance(form_data, list) or len(form_data) < 9:
        raise GoogleFormsReadError("Google Forms returned incomplete form metadata.")

    raw_questions = form_data[1]
    title = form_data[8]
    if not isinstance(raw_questions, list) or not isinstance(title, str):
        raise GoogleFormsReadError("Google Forms returned unreadable form title or questions.")

    questions = []
    for item in raw_questions:
        if (
            isinstance(item, list)
            and len(item) > 3
            and isinstance(item[0], (int, str))
            and isinstance(item[1], str)
            and item[1].strip()
            and isinstance(item[3], int)
        ):
            questions.append(_parse_question(item, len(questions) + 1))

    try:
        return FormDefinition(form_title=title, questions=questions)
    except ValidationError as exc:
        raise GoogleFormsReadError(f"Google Forms question validation failed: {exc}") from exc


class GoogleFormsReader:
    """Read public form question metadata only; never fill or submit a form."""

    def __init__(
        self,
        *,
        timeout: float = 20,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.timeout = timeout
        self.transport = transport

    def read(self, url: str) -> FormDefinition:
        current_url = _normalize_form_url(url)
        try:
            with httpx.Client(
                timeout=self.timeout,
                follow_redirects=False,
                headers={"User-Agent": "QwenFormsAutoloop/1.0 (read-only form metadata)"},
                transport=self.transport,
            ) as client:
                for redirect_count in range(MAX_REDIRECTS + 1):
                    with client.stream("GET", current_url) as response:
                        if response.is_redirect:
                            if redirect_count == MAX_REDIRECTS:
                                raise GoogleFormsReadError("Too many redirects while opening the form.")
                            location = response.headers.get("location")
                            if not location:
                                raise GoogleFormsReadError("Google Forms returned a redirect without a destination.")
                            current_url = _normalize_form_url(urljoin(current_url, location))
                            continue

                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "")
                        if "text/html" not in content_type.lower():
                            raise GoogleFormsReadError(
                                f"Expected an HTML form page, received '{content_type or 'unknown content type'}'."
                            )

                        content = bytearray()
                        for chunk in response.iter_bytes():
                            content.extend(chunk)
                            if len(content) > MAX_PAGE_BYTES:
                                raise GoogleFormsReadError(
                                    f"Google Forms page exceeds the {MAX_PAGE_BYTES // (1024 * 1024)} MB read limit."
                                )

                        encoding = response.encoding or "utf-8"
                        return parse_google_form_html(content.decode(encoding, errors="replace"))
        except GoogleFormsReadError:
            raise
        except (httpx.HTTPError, UnicodeError) as exc:
            raise GoogleFormsReadError(f"Could not read the public Google Form: {exc}") from exc

        raise GoogleFormsReadError("Could not read the public Google Form.")
