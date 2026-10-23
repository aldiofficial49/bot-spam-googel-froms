from pathlib import Path
import pytest
from main import main


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "--browser-fill" in captured.out
    assert "--submit" in captured.out
    assert "--continuous" in captured.out
    assert "--delay" in captured.out
    assert "--headful" in captured.out


def test_cli_rejects_submit_without_url(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--submit"])
    assert code == 1
    captured = capsys.readouterr()
    assert "Submitting is only supported for remote Google Forms" in captured.out


def test_cli_rejects_continuous_without_url(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--continuous"])
    assert code == 1
    captured = capsys.readouterr()
    assert "--continuous mode is only supported for remote Google Forms" in captured.out


def test_cli_rejects_iterations_out_of_bounds(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--iterations", "0"])
    assert code == 1
    captured = capsys.readouterr()
    assert "Iterations must be between" in captured.out


def test_cli_rejects_url_with_local_test(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--url", "https://docs.google.com/forms/d/TEST/viewform", "--local-test"])
    assert code == 1
    captured = capsys.readouterr()
    assert "cannot be used with --local-test" in captured.out


def test_cli_rejects_no_ai_with_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--dry-run", "--no-ai"])
    assert code == 1
    captured = capsys.readouterr()
    assert "Mode --dry-run membutuhkan AI" in captured.out
