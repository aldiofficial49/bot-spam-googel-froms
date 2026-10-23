import argparse
import os
import sys
import time
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.table import Table

from config import AppConfig, FIXTURE_PATH, OUTPUT_DIR
from engine.browser_engine import (
    BrowserEngineError,
    LocalBrowserEngine,
    RemoteBrowserEngine,
)
from engine.exporter import export_results
from engine.form_parser import FormDefinition, load_form, parse_local_html
from engine.google_forms_reader import GoogleFormsReadError, GoogleFormsReader
from engine.llm_client import OllamaClient, OllamaError
from engine.logger import ResultLogger
from engine.response_engine import generate_response, generate_scenario_responses
from engine.submission_controller import SubmissionController, _synthetic_answer
from engine.variation_engine import create_scenarios


console = Console()


def _config() -> AppConfig:
    return AppConfig(
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        model_name=os.getenv("MODEL_NAME", "qwen2.5-coder:1.5b"),
        request_timeout=float(os.getenv("REQUEST_TIMEOUT", "60")),
        max_iterations=int(os.getenv("MAX_ITERATIONS", "10")),
        temperature=float(os.getenv("TEMPERATURE", "0.7")),
        seed=int(os.getenv("SEED", "42")),
    )


def _client(config: AppConfig) -> OllamaClient:
    return OllamaClient(
        config.ollama_url,
        config.model_name,
        config.request_timeout,
        config.max_retries,
    )


def _load_fixture(path: Path) -> FormDefinition:
    if path.suffix.lower() == ".json":
        return load_form(path)
    if path.suffix.lower() in {".html", ".htm"}:
        return parse_local_html(path)
    raise ValueError("Fixture must be a local .json or .html file.")


def _show_results(form_title: str, results: list[dict]) -> None:
    table = Table(title=f"{form_title} - synthetic test preview")
    table.add_column("Scenario")
    table.add_column("Question")
    table.add_column("Answer")
    for result in results:
        for item in result["answers"]:
            table.add_row(
                result["scenario_id"],
                item["question_id"],
                str(item["answer"]),
            )
    console.print(table)


def _show_form(form: FormDefinition) -> None:
    table = Table(title=f"{form.form_title} - read-only questions")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Required")
    table.add_column("Question / options")
    for question in form.questions:
        details = question.label
        if question.options:
            details += "\n" + "\n".join(f"- {option}" for option in question.options)
        elif question.type == "scale":
            details += f"\nRange: {question.min_value} to {question.max_value}"
        table.add_row(question.id, question.type, "Yes" if question.required else "No", details)
    console.print(table)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local-first form QA tool with remote Google Forms fill & submit capabilities."
    )
    parser.add_argument("--check", action="store_true", help="Check Ollama and configured model.")
    parser.add_argument("--dry-run", action="store_true", help="Generate synthetic answers preview.")
    parser.add_argument("--local-test", action="store_true", help="Run bounded deterministic tests against a local fixture.")
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=1,
        help="Number of scenarios to fill/submit (1 to configured maximum).",
    )
    parser.add_argument(
        "--continuous",
        "--loop",
        action="store_true",
        help="Run submissions continuously in an endless loop until stopped (Ctrl+C).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between consecutive submissions (default: 1.0).",
    )
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH, help="Local JSON/HTML fixture path.")
    parser.add_argument(
        "--url",
        help="Target public Google Forms viewform URL.",
    )
    parser.add_argument(
        "--browser-fill",
        action="store_true",
        help="Fill form in a browser (local HTML fixture or remote Google Form).",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit the form in the browser after filling (remote forms only).",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser visibly (default is headless in background).",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Disable AI (Ollama) generation and use heuristic moral personas.",
    )
    parser.add_argument("--export", choices=("json", "csv"), help="Export existing run results.")
    args = parser.parse_args(argv)

    try:
        if args.dry_run and args.local_test:
            raise ValueError("Choose only one of --dry-run or --local-test.")
        if args.url and args.local_test:
            raise ValueError("A Google Forms URL cannot be used with --local-test.")
        if not args.url and args.submit:
            raise ValueError("Submitting is only supported for remote Google Forms (--url).")
        if not args.url and args.continuous:
            raise ValueError("--continuous mode is only supported for remote Google Forms (--url).")
        if args.url and args.fixture != FIXTURE_PATH:
            raise ValueError("Choose either --url or --fixture, not both.")

        config = _config()
        if not args.continuous:
            if args.iterations < 1 or args.iterations > config.max_iterations:
                raise ValueError(f"Iterations must be between 1 and {config.max_iterations}.")
            if args.url and not args.browser_fill and not args.submit and args.dry_run and args.iterations != 1:
                raise ValueError("Public Google Forms previews are limited to exactly one scenario.")

        client = _client(config)
        if args.check:
            ok, message = client.check_status()
            console.print(message, style="green" if ok else "red")
            return 0 if ok else 1

        logger = ResultLogger(OUTPUT_DIR)
        if args.export:
            destination = export_results(logger, args.export)
            console.print(f"Exported current-session results to {destination}")
            return 0

        remote_form = bool(args.url)
        if remote_form:
            form = GoogleFormsReader(timeout=config.request_timeout).read(args.url)
            console.print(
                f"Read {len(form.questions)} question(s) from the public form: '{form.form_title}'."
            )
            if not args.dry_run and not args.browser_fill and not args.submit and not args.continuous:
                _show_form(form)
                return 0

            fixture = None
            if args.continuous or args.submit:
                mode = "remote-submit"
            elif args.browser_fill:
                mode = "remote-fill"
            else:
                mode = "dry-run"

            if args.dry_run:
                console.print(
                    "[yellow]Answers are generated using Ollama AI profile dry-run.[/yellow]"
                )
        elif not args.dry_run and not args.local_test:
            console.print("Mode: [bold]LOCAL TEST[/bold] (safe default)")
            console.print("Use only the bundled/local fixture. Remote form URLs are not supported.")
            fixture_input = input(f"Local fixture path [{args.fixture}]: ").strip()
            fixture = Path(fixture_input).expanduser() if fixture_input else args.fixture
            mode = "local-test"
        else:
            fixture = args.fixture
            mode = "dry-run" if args.dry_run else "local-test"

        if not remote_form:
            form = _load_fixture(fixture)

        iterations = args.iterations
        client_for_controller = None
        if not args.no_ai:
            ok, message = client.check_status()
            if mode == "dry-run":
                if not ok:
                    raise OllamaError(message)
                console.print(message)
                client_for_controller = client
            elif ok:
                console.print(
                    f"[bold cyan]AI Model terhubung: {config.model_name} (Ollama). "
                    "Jawaban dianalisis secara moral & beragam.[/bold cyan]"
                )
                client_for_controller = client
            else:
                if remote_form and (args.submit or args.browser_fill or args.continuous):
                    console.print(
                        f"[yellow]Ollama offline/model tidak siap ({message}). "
                        "Menggunakan generator cerdas berbasis profil moral pelajar.[/yellow]"
                    )
        else:
            if mode == "dry-run":
                raise ValueError("Mode --dry-run membutuhkan AI. Jangan gunakan bersama --no-ai.")
            console.print("[yellow]Mode non-AI aktif (--no-ai). Menggunakan generator cerdas berbasis profil moral pelajar.[/yellow]")

        effective_max = max(config.max_iterations, iterations)
        controller = SubmissionController(
            max_iterations=effective_max,
            logger=logger,
            client=client_for_controller,
            model_name=config.model_name,
            temperature=config.temperature,
            seed=config.seed,
        )

        if remote_form and args.continuous:
            remote_browser = RemoteBrowserEngine()
            headless = not args.headful
            console.print(
                f"[bold cyan]Running continuous submissions on '{form.form_title}'. "
                "Press Ctrl+C to stop safely.[/bold cyan]"
            )
            submitted_count = 0
            scenario_index = 0
            try:
                from playwright.sync_api import sync_playwright

                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=headless)
                    try:
                        context = browser.new_context(
                            viewport={"width": 1280, "height": 900},
                            user_agent=(
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/124.0.0.0 Safari/537.36"
                            ),
                        )
                        page = context.new_page()
                        page.set_default_timeout(config.request_timeout * 1000)

                        while True:
                            scenario_index += 1
                            scenario_id = f"LOOP-{scenario_index:04d}"
                            started = time.monotonic()
                            scenario_data = create_scenarios(1, seed=config.seed + scenario_index)[0]
                            scenario_data["scenario_id"] = scenario_id

                            if client_for_controller is not None:
                                answers = generate_scenario_responses(
                                    client_for_controller,
                                    form.form_title,
                                    form.questions,
                                    scenario_id,
                                    scenario_data["context"],
                                    {
                                        "profile_id": scenario_data["profile"],
                                        "synthetic": "true",
                                        "persona": scenario_data.get("persona"),
                                    },
                                    persona=scenario_data.get("persona"),
                                    temperature=config.temperature,
                                    seed=config.seed + scenario_index,
                                    allow_fallback=True,
                                )
                            else:
                                answers = []
                                for q_idx, q in enumerate(form.questions):
                                    ans = _synthetic_answer(
                                        q, scenario_data, scenario_index * len(form.questions) + q_idx
                                    )
                                    answers.append(
                                        {
                                            "question_id": q.id,
                                            "answer": ans,
                                            "scenario_id": scenario_id,
                                            "synthetic": True,
                                            "validation_status": "valid",
                                        }
                                    )

                            action_result = remote_browser._fill_and_submit_page(
                                page, args.url, form, answers, submit=True, timeout=config.request_timeout * 1000
                            )
                            duration = round(time.monotonic() - started, 2)
                            submitted_count += 1

                            record = {
                                "scenario_id": scenario_id,
                                "model": config.model_name
                                if client_for_controller
                                else "heuristic-moral-generator",
                                "question_count": len(answers),
                                "valid_count": len(answers),
                                "invalid_count": 0,
                                "browser_status": "passed",
                                "submission_status": action_result["status"],
                                "browser_error": "",
                                "duration_seconds": duration,
                                "status": "passed",
                                "mode": "remote-submit",
                                "answers": answers,
                            }
                            logger.add(record)
                            console.print(
                                f"[green][OK] [#{submitted_count}] {scenario_id}: Remote form successfully submitted in browser ({duration}s)[/green]"
                            )

                            if args.delay > 0:
                                time.sleep(args.delay)
                    finally:
                        try:
                            browser.close()
                        except Exception:
                            pass
            except ImportError:
                console.print(
                    "[bold red][FAIL] Playwright tidak terpasang di environment Python saat ini.[/bold red]\n"
                    "Pasang dengan: python -m pip install -r requirements.txt\n"
                    "Atau aktifkan virtual environment: .\\.venv\\Scripts\\Activate.ps1"
                )
                return 1
            except KeyboardInterrupt:
                console.print(
                    f"\n[yellow]Continuous submission stopped safely by user. Total completed: {submitted_count}[/yellow]"
                )
                json_path = logger.export_json()
                logger.export_csv()
                console.print(f"Logged test results to {json_path}")
                return 0
            except Exception as exc:
                console.print(f"[bold red][FAIL] Continuous submission error: {exc}[/bold red]")
                if submitted_count > 0:
                    json_path = logger.export_json()
                    logger.export_csv()
                    console.print(f"Logged test results to {json_path}")
                return 1

        results = controller.run(form, mode=mode, iterations=iterations)

        if remote_form and (args.browser_fill or args.submit):
            remote_browser = RemoteBrowserEngine()
            headless = not args.headful

            def on_progress(current: int, total: int, res: dict[str, Any]) -> None:
                dur_str = f" ({res.get('duration_seconds', 0)}s)" if "duration_seconds" in res else ""
                console.print(
                    f"[green][OK] [{current}/{total}] Scenario {res['scenario_id']}: Remote form successfully "
                    f"{'submitted' if args.submit else 'filled'} in browser{dur_str}.[/green]"
                )

            action_results = remote_browser.run_submissions(
                args.url,
                form,
                results,
                submit=args.submit,
                headless=headless,
                timeout=config.request_timeout * 1000,
                delay=args.delay,
                callback=on_progress,
            )
            for record, action_result in zip(logger.records[-len(results):], action_results):
                record["browser_status"] = "passed"
                record["submission_status"] = action_result["status"]
            logger.export_json()
            logger.export_csv()
        elif not remote_form and args.browser_fill:
            if mode != "local-test":
                raise ValueError("--browser-fill can only be used with --local-test.")
            if fixture.suffix.lower() not in {".html", ".htm"}:
                raise ValueError("--browser-fill requires a local HTML fixture.")
            browser = LocalBrowserEngine()
            for result, record in zip(results, logger.records[-len(results):]):
                try:
                    browser.fill(fixture, form, result["answers"])
                    record["browser_status"] = "passed"
                except BrowserEngineError as exc:
                    record["browser_status"] = "failed"
                    record["browser_error"] = str(exc)
                    logger.export_json()
                    logger.export_csv()
                    raise
            logger.export_json()

        _show_results(form.form_title, results)
        json_path = logger.export_json()
        logger.export_csv()
        console.print(f"Logged test results to {json_path}")
        return 0
    except KeyboardInterrupt:
        console.print("\nStopped safely by user.", style="yellow")
        return 130
    except (ValueError, OSError, OllamaError, BrowserEngineError, GoogleFormsReadError) as exc:
        console.print(f"Error: {exc}", style="red")
        return 1


if __name__ == "__main__":
    sys.exit(main())
