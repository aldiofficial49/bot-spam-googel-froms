from pathlib import Path

import pytest

from engine.browser_engine import BrowserEngineError, LocalBrowserEngine
from engine.form_parser import FormDefinition, Question


def test_browser_engine_rejects_nonlocal_fixture_before_playwright() -> None:
    form = FormDefinition(
        form_title="Fixture",
        questions=[Question(id="Q1", type="short_answer", label="Name")],
    )
    with pytest.raises(BrowserEngineError, match="local HTML fixture"):
        LocalBrowserEngine().fill(
            Path("https://example.invalid/form"),
            form,
            [{"question_id": "Q1", "answer": "test"}],
        )


def test_remote_browser_engine_rejects_invalid_url_scheme() -> None:
    from engine.browser_engine import RemoteBrowserEngine

    form = FormDefinition(
        form_title="Test",
        questions=[Question(id="Q1", type="short_answer", label="Name")],
    )
    engine = RemoteBrowserEngine()
    with pytest.raises(BrowserEngineError, match="HTTP/HTTPS or local test file URL"):
        engine.fill_and_submit(
            "ftp://invalid.com",
            form,
            [{"question_id": "Q1", "answer": "test"}],
        )


def test_remote_browser_engine_detects_permission_required(tmp_path: Path) -> None:
    from engine.browser_engine import RemoteBrowserEngine

    page_path = tmp_path / "permission.html"
    page_path.write_text(
        "<html><body><h1>Perlu izin</h1><p>Sign in to your Google Account</p></body></html>",
        encoding="utf-8",
    )
    form = FormDefinition(
        form_title="Private Form",
        questions=[Question(id="Q1", type="short_answer", label="Name")],
    )
    engine = RemoteBrowserEngine()
    with pytest.raises(BrowserEngineError, match="authentication or permission"):
        engine.fill_and_submit(
            page_path.as_uri(),
            form,
            [{"question_id": "Q1", "answer": "Alice"}],
            headless=True,
        )


def test_remote_browser_engine_detects_closed_form(tmp_path: Path) -> None:
    from engine.browser_engine import RemoteBrowserEngine

    page_path = tmp_path / "closed.html"
    page_path.write_text(
        "<html><body><p>Formulir ini tidak lagi menerima tanggapan</p></body></html>",
        encoding="utf-8",
    )
    form = FormDefinition(
        form_title="Closed Form",
        questions=[Question(id="Q1", type="short_answer", label="Name")],
    )
    engine = RemoteBrowserEngine()
    with pytest.raises(BrowserEngineError, match="closed and no longer accepting"):
        engine.fill_and_submit(
            page_path.as_uri(),
            form,
            [{"question_id": "Q1", "answer": "Alice"}],
            headless=True,
        )


def test_remote_browser_engine_fills_and_submits_google_form_structure(tmp_path: Path) -> None:
    from engine.browser_engine import RemoteBrowserEngine

    mock_form_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Mock Google Form</title></head>
    <body>
        <form id="mG61Hd">
            <div role="listitem">
                <div role="heading">Nama Lengkap</div>
                <input type="text" class="whsOnd" aria-label="Nama Lengkap" />
            </div>
            <div role="listitem">
                <div role="heading">Feedback Lengkap</div>
                <textarea class="KHxj8b" aria-label="Feedback Lengkap"></textarea>
            </div>
            <div role="listitem">
                <div role="heading">Seberapa Sering?</div>
                <div role="radio" data-value="Sering" aria-checked="false"><span>Sering</span></div>
                <div role="radio" data-value="Jarang" aria-checked="false"><span>Jarang</span></div>
            </div>
            <div role="listitem">
                <div role="heading">Minat</div>
                <div role="checkbox" data-value="AI" aria-checked="false"><span>AI</span></div>
                <div role="checkbox" data-value="Security" aria-checked="false"><span>Security</span></div>
            </div>
            <div role="listitem">
                <div role="heading">Kepuasan</div>
                <div role="radio" data-value="1" aria-checked="false"><span>1</span></div>
                <div role="radio" data-value="5" aria-checked="false"><span>5</span></div>
            </div>
            <div role="button" jscontroller="submitBtn" onclick="document.body.innerHTML='<h1>Tanggapan Anda telah direkam</h1>';">
                <span>Kirim</span>
            </div>
        </form>
    </body>
    </html>
    """
    page_path = tmp_path / "mock_form.html"
    page_path.write_text(mock_form_html, encoding="utf-8")

    form = FormDefinition(
        form_title="Mock Google Form",
        questions=[
            Question(id="q1", type="short_answer", label="Nama Lengkap"),
            Question(id="q2", type="paragraph", label="Feedback Lengkap"),
            Question(id="q3", type="multiple_choice", label="Seberapa Sering?", options=["Sering", "Jarang"]),
            Question(id="q4", type="checkbox", label="Minat", options=["AI", "Security"]),
            Question(id="q5", type="scale", label="Kepuasan", min_value=1, max_value=5),
        ],
    )

    answers = [
        {"question_id": "q1", "answer": "Budi Santoso"},
        {"question_id": "q2", "answer": "Sangat bagus dan intuitif"},
        {"question_id": "q3", "answer": "Sering"},
        {"question_id": "q4", "answer": ["AI", "Security"]},
        {"question_id": "q5", "answer": 5},
    ]

    engine = RemoteBrowserEngine()

    # Test 1: Fill only (submit=False)
    fill_result = engine.fill_and_submit(
        page_path.as_uri(),
        form,
        answers,
        submit=False,
        headless=True,
    )
    assert fill_result["status"] == "filled"
    assert fill_result["submitted"] is False
    assert fill_result["filled_count"] == 5

    # Test 2: Fill and submit (submit=True)
    submit_result = engine.fill_and_submit(
        page_path.as_uri(),
        form,
        answers,
        submit=True,
        headless=True,
    )
    assert submit_result["status"] == "submitted"
    assert submit_result["submitted"] is True
    assert submit_result["filled_count"] == 5
