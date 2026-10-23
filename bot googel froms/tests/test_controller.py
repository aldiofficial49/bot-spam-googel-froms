from pathlib import Path

import pytest

from engine.form_parser import FormDefinition, Question, load_form
from engine.llm_client import OllamaClient
from engine.logger import ResultLogger
from engine.submission_controller import SubmissionController


ROOT = Path(__file__).resolve().parents[1]


def test_local_test_runs_bounded_synthetic_scenarios(tmp_path: Path) -> None:
    form = load_form(ROOT / "fixtures" / "sample_form.json")
    logger = ResultLogger(tmp_path)
    controller = SubmissionController(max_iterations=3, logger=logger)
    results = controller.run(form, mode="local-test", iterations=3)
    assert len(results) == 3
    assert all(answer["synthetic"] for result in results for answer in result["answers"])
    assert len(logger.records) == 3
    assert (tmp_path / "results.json").exists()


def test_controller_rejects_unbounded_and_remote_modes(tmp_path: Path) -> None:
    form = load_form(ROOT / "fixtures" / "sample_form.json")
    controller = SubmissionController(max_iterations=2, logger=ResultLogger(tmp_path))
    with pytest.raises(ValueError, match="between 1 and 2"):
        controller.run(form, mode="local-test", iterations=3)
    with pytest.raises(ValueError, match="remote submission is disabled"):
        controller.run(form, mode="authorized-test", iterations=1)


def test_exports_json_and_csv(tmp_path: Path) -> None:
    logger = ResultLogger(tmp_path)
    logger.add({"scenario_id": "TEST-001", "status": "passed"})
    json_path = logger.export_json()
    csv_path = logger.export_csv()
    assert "TEST-001" in json_path.read_text(encoding="utf-8")
    assert "scenario_id" in csv_path.read_text(encoding="utf-8")


def test_logger_loads_prior_records(tmp_path: Path) -> None:
    first = ResultLogger(tmp_path)
    first.add({"scenario_id": "TEST-001"})
    second = ResultLogger(tmp_path)
    assert len(second.records) == 1


def test_failed_model_answer_is_recorded(tmp_path: Path) -> None:
    class InvalidClient(OllamaClient):
        def __init__(self) -> None:
            super().__init__()

        def chat_json(self, prompt: str, **kwargs: object) -> dict[str, object]:
            return {"answer": "not listed"}

    form = FormDefinition(
        form_title="Choice form",
        questions=[
            Question(id="Q1", type="multiple_choice", label="Choose", options=["A"])
        ],
    )
    logger = ResultLogger(tmp_path)
    controller = SubmissionController(
        max_iterations=1,
        logger=logger,
        client=InvalidClient(),
    )
    with pytest.raises(ValueError, match="correction attempts"):
        controller.run(form, mode="dry-run")
    assert logger.records[0]["status"] == "failed"
    assert logger.records[0]["invalid_count"] == 1


def test_controller_runs_remote_fill_and_submit_modes(tmp_path: Path) -> None:
    form = FormDefinition(
        form_title="Remote QA Form",
        questions=[
            Question(id="Q1", type="short_answer", label="Name"),
            Question(id="Q2", type="multiple_choice", label="Role", options=["Dev", "QA"]),
        ],
    )
    logger = ResultLogger(tmp_path)
    controller = SubmissionController(max_iterations=5, logger=logger)

    # Test remote-fill
    fill_results = controller.run(form, mode="remote-fill", iterations=2)
    assert len(fill_results) == 2
    assert fill_results[0]["mode"] == "remote-fill"
    assert len(fill_results[0]["answers"]) == 2

    # Test remote-submit
    submit_results = controller.run(form, mode="remote-submit", iterations=1)
    assert len(submit_results) == 1
    assert submit_results[0]["mode"] == "remote-submit"
    assert len(submit_results[0]["answers"]) == 2


def test_controller_generates_diverse_moral_answers(tmp_path: Path) -> None:
    form = FormDefinition(
        form_title="Survei Opini Siswa",
        questions=[
            Question(
                id="Q1",
                type="multiple_choice",
                label="Tindakan terhadap bullying",
                options=[
                    "Membela korban dan melapor ke guru",
                    "Diam saja dan mengikuti arus kelompok",
                    "Merasa kasihan tapi takut ikut dijadikan target",
                ],
            ),
            Question(
                id="Q2",
                type="paragraph",
                label="Saran pencegahan bullying di sekolah",
            ),
        ],
    )
    logger = ResultLogger(tmp_path)
    controller = SubmissionController(max_iterations=5, logger=logger)
    results = controller.run(form, mode="local-test", iterations=3)

    assert len(results) == 3
    q1_answers = [res["answers"][0]["answer"] for res in results]
    q2_answers = [res["answers"][1]["answer"] for res in results]

    # Check answers are valid Indonesian moral responses
    assert all(ans in form.questions[0].options for ans in q1_answers)
    assert all(len(ans) > 20 for ans in q2_answers)
    # Check diversity across scenarios
    assert len(set(q2_answers)) >= 2 or len(set(q1_answers)) >= 2
