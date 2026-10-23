from pathlib import Path

from engine.form_parser import load_form, parse_local_html


ROOT = Path(__file__).resolve().parents[1]


def test_load_json_fixture() -> None:
    form = load_form(ROOT / "fixtures" / "sample_form.json")
    assert form.form_title == "Local QA Sample Form"
    assert len(form.questions) == 5
    assert form.questions[0].options == ["Standard", "Alternative", "Boundary"]


def test_parse_html_fixture() -> None:
    form = parse_local_html(ROOT / "fixtures" / "sample_form.html")
    assert form.form_title == "Local QA Sample Form"
    assert form.questions[0].options == ["Standard", "Alternative", "Boundary"]
    assert form.questions[2].min_value == 1
    assert form.questions[2].max_value == 5


def test_reject_html_without_questions(tmp_path: Path) -> None:
    path = tmp_path / "empty.html"
    path.write_text("<title>Empty</title>", encoding="utf-8")
    try:
        parse_local_html(path)
    except ValueError as exc:
        assert "no question fieldsets" in str(exc)
    else:
        raise AssertionError("Expected fixture with no questions to be rejected.")
