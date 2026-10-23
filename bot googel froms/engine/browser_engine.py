import os
import re
import time
from pathlib import Path
from typing import Any, Callable

from config import BROWSERS_DIR
from engine.form_parser import FormDefinition, Question

if BROWSERS_DIR.exists() and "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(BROWSERS_DIR)


class BrowserEngineError(RuntimeError):
    """A safe browser test or remote operation could not be completed."""


class LocalBrowserEngine:
    """Fill a local fixture for inspection; deliberately never submits it."""

    def fill(self, html_path: Path, form: FormDefinition, answers: list[dict[str, Any]]) -> None:
        resolved = html_path.resolve()
        if not resolved.is_file() or resolved.suffix.lower() not in {".html", ".htm"}:
            raise BrowserEngineError("Browser automation accepts only an existing local HTML fixture.")

        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserEngineError(
                "Playwright is not installed. Install requirements and run "
                "'playwright install chromium'."
            ) from exc

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.goto(resolved.as_uri(), wait_until="load", timeout=15000)
                    for item in answers:
                        question = next(q for q in form.questions if q.id == item["question_id"])
                        group = page.get_by_role("group", name=question.label, exact=True)
                        answer = item["answer"]
                        if question.type == "multiple_choice":
                            radios = group.locator("input[type=radio]")
                            if radios.count():
                                option = group.get_by_label(answer, exact=True)
                                option.check()
                                if not option.is_checked():
                                    raise BrowserEngineError(f"Could not verify the selected answer for {question.id}.")
                            else:
                                select = group.locator("select")
                                select.select_option(label=answer)
                                selected = group.locator("option:checked").inner_text()
                                if selected != answer:
                                    raise BrowserEngineError(f"Could not verify the selected answer for {question.id}.")
                        elif question.type == "checkbox":
                            for option in answer:
                                group.get_by_label(option, exact=True).check()
                                if not group.get_by_label(option, exact=True).is_checked():
                                    raise BrowserEngineError(f"Could not verify checkbox value for {question.id}.")
                        elif question.type == "scale":
                            control = group.locator("input[type=number]")
                            control.fill(str(answer))
                            if control.input_value() != str(answer):
                                raise BrowserEngineError(f"Could not verify scale value for {question.id}.")
                        elif question.type == "paragraph":
                            control = group.locator("textarea")
                            control.fill(answer)
                            if control.input_value() != answer:
                                raise BrowserEngineError(f"Could not verify text value for {question.id}.")
                        else:
                            control = group.locator("input[type=text]")
                            control.fill(answer)
                            if control.input_value() != answer:
                                raise BrowserEngineError(f"Could not verify text value for {question.id}.")
                finally:
                    browser.close()
        except PlaywrightError as exc:
            raise BrowserEngineError(f"Local browser fixture test failed: {exc}") from exc


class RemoteBrowserEngine:
    """Fill and optionally submit a remote Google Form via Playwright browser automation."""

    def fill_and_submit(
        self,
        url: str,
        form: FormDefinition,
        answers: list[dict[str, Any]],
        *,
        submit: bool = False,
        headless: bool = True,
        timeout: float = 30000.0,
    ) -> dict[str, Any]:
        results = self.run_submissions(
            url=url,
            form=form,
            scenarios=[{"answers": answers, "scenario_id": "TEST-001"}],
            submit=submit,
            headless=headless,
            timeout=timeout,
            delay=0,
        )
        return results[0]

    def run_submissions(
        self,
        url: str,
        form: FormDefinition,
        scenarios: list[dict[str, Any]],
        *,
        submit: bool = False,
        headless: bool = True,
        timeout: float = 30000.0,
        delay: float = 1.0,
        callback: Callable[[int, int, dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        normalized_url = url.strip()
        if not (
            normalized_url.startswith("https://")
            or normalized_url.startswith("http://")
            or normalized_url.startswith("file://")
        ):
            raise BrowserEngineError("Remote browser automation requires an HTTP/HTTPS or local test file URL.")

        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserEngineError(
                "Playwright is not installed. Install requirements and run "
                "'playwright install chromium'."
            ) from exc

        results = []
        try:
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
                    page.set_default_timeout(timeout)

                    for index, item in enumerate(scenarios):
                        scenario_id = item.get("scenario_id", f"TEST-{index + 1:03d}")
                        answers = item.get("answers", [])
                        started = time.monotonic()
                        res = self._fill_and_submit_page(
                            page, normalized_url, form, answers, submit=submit, timeout=timeout
                        )
                        duration = round(time.monotonic() - started, 2)
                        res["scenario_id"] = scenario_id
                        res["duration_seconds"] = duration
                        results.append(res)

                        if callback:
                            callback(index + 1, len(scenarios), res)

                        if delay > 0 and index < len(scenarios) - 1:
                            time.sleep(delay)
                finally:
                    browser.close()
        except PlaywrightError as exc:
            raise BrowserEngineError(f"Remote browser automation failed: {exc}") from exc

        return results

    def _fill_and_submit_page(
        self,
        page: Any,
        url: str,
        form: FormDefinition,
        answers: list[dict[str, Any]],
        *,
        submit: bool = False,
        timeout: float = 30000.0,
    ) -> dict[str, Any]:
        from playwright.sync_api import Error as PlaywrightError

        last_error = None
        for attempt in range(3):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                if "chrome-error://" in getattr(page, "url", ""):
                    time.sleep(1.0)
                    continue
                page.wait_for_selector("form", timeout=min(timeout, 10000))
                last_error = None
                break
            except PlaywrightError as exc:
                last_error = exc
                time.sleep(1.0)

        if last_error is not None:
            try:
                page.goto(url, wait_until="load", timeout=timeout)
            except PlaywrightError as exc:
                raise BrowserEngineError(f"Remote navigation failed: {exc}") from exc

        # Check for permission/login requirement
        body_text = page.locator("body").inner_text()
        if any(
            phrase in body_text
            for phrase in [
                "You need permission",
                "Perlu izin",
                "Sign in to your Google Account",
            ]
        ):
            raise BrowserEngineError("Google Form requires authentication or permission to access.")

        # Check if form is closed
        if any(
            phrase in body_text
            for phrase in [
                "no longer accepting responses",
                "tidak lagi menerima tanggapan",
            ]
        ):
            raise BrowserEngineError("Google Form is closed and no longer accepting responses.")

        # Check for CAPTCHA presence
        if page.locator('iframe[src*="recaptcha"]').count() > 0:
            raise BrowserEngineError(
                "CAPTCHA detected on Google Form. Automated filling blocked by CAPTCHA protection."
            )

        # Fill each question
        for item in answers:
            question = next(
                (q for q in form.questions if q.id == item["question_id"]),
                None,
            )
            if question is None:
                continue
            container = self._find_question_container(page, question)
            self._fill_question(container, question, item["answer"])

        if submit:
            self._submit_form(page)
            return {
                "status": "submitted",
                "submitted": True,
                "filled_count": len(answers),
                "url": url,
            }

        return {
            "status": "filled",
            "submitted": False,
            "filled_count": len(answers),
            "url": url,
        }

    def _find_question_container(self, page: Any, question: Question) -> Any:
        # Match standard Google Forms listitem
        listitems = page.locator('div[role="listitem"]').filter(has_text=question.label)
        if listitems.count() > 0:
            return listitems.first

        # Match by fieldset or group role
        groups = page.get_by_role("group", name=question.label, exact=False)
        if groups.count() > 0:
            return groups.first

        # Match by question title heading
        headings = page.get_by_role("heading", name=question.label, exact=False)
        if headings.count() > 0:
            parent = headings.first.locator("xpath=ancestor::div[@role='listitem']")
            if parent.count() > 0:
                return parent.first
            ancestor_block = headings.first.locator("xpath=ancestor::div[contains(@class, 'Qr7Oae')]")
            if ancestor_block.count() > 0:
                return ancestor_block.first

        # Match by data-question-id attribute
        by_id = page.locator(f'[data-question-id="{question.id}"]')
        if by_id.count() > 0:
            return by_id.first

        return page

    def _fill_question(self, container: Any, question: Question, answer: Any) -> None:
        if question.type == "short_answer":
            field = container.locator('input[type="text"]:visible')
            if not field.count():
                field = container.locator('input:not([type="hidden"]):visible')
            if not field.count():
                field = container.locator('input[type="text"]')
            if not field.count():
                raise BrowserEngineError(f"Could not find text input for '{question.label}'.")
            target = field.first
            target.scroll_into_view_if_needed()
            target.fill(str(answer))
            if target.input_value() != str(answer):
                raise BrowserEngineError(f"Could not verify text input value for '{question.label}'.")

        elif question.type == "paragraph":
            field = container.locator('textarea:visible')
            if not field.count():
                field = container.locator('textarea')
            if not field.count():
                raise BrowserEngineError(f"Could not find textarea for '{question.label}'.")
            target = field.first
            target.scroll_into_view_if_needed()
            target.fill(str(answer))
            if target.input_value() != str(answer):
                raise BrowserEngineError(f"Could not verify textarea value for '{question.label}'.")

        elif question.type == "multiple_choice":
            radio = container.locator(f'div[role="radio"][data-value="{answer}"]')
            if not radio.count():
                radio = container.locator('div[role="radio"]').filter(has_text=str(answer))
            if not radio.count():
                radio = container.get_by_role("radio", name=str(answer), exact=True)
            if not radio.count():
                radio = container.locator(f'input[type="radio"][value="{answer}"]')
            if not radio.count():
                radio = container.get_by_text(str(answer), exact=True)
            if not radio.count():
                raise BrowserEngineError(f"Could not find option '{answer}' for '{question.label}'.")
            target = radio.first
            target.scroll_into_view_if_needed()
            target.click()

        elif question.type == "checkbox":
            options = answer if isinstance(answer, list) else [answer]
            for opt in options:
                cb = container.locator(f'div[role="checkbox"][data-value="{opt}"]')
                if not cb.count():
                    cb = container.locator('div[role="checkbox"]').filter(has_text=str(opt))
                if not cb.count():
                    cb = container.get_by_role("checkbox", name=str(opt), exact=True)
                if not cb.count():
                    cb = container.locator(f'input[type="checkbox"][value="{opt}"]')
                if not cb.count():
                    cb = container.get_by_text(str(opt), exact=True)
                if not cb.count():
                    raise BrowserEngineError(f"Could not find checkbox option '{opt}' for '{question.label}'.")
                target = cb.first
                target.scroll_into_view_if_needed()
                if target.get_attribute("aria-checked") != "true":
                    target.click()

        elif question.type == "scale":
            val = str(answer)
            radio = container.locator(f'div[role="radio"][data-value="{val}"]')
            if not radio.count():
                radio = container.locator('div[role="radio"]').filter(has_text=val)
            if not radio.count():
                radio = container.get_by_role("radio", name=val, exact=True)
            if not radio.count():
                radio = container.get_by_text(val, exact=True)
            if not radio.count():
                raise BrowserEngineError(f"Could not find scale rating '{val}' for '{question.label}'.")
            target = radio.first
            target.scroll_into_view_if_needed()
            target.click()

    def _submit_form(self, page: Any) -> None:
        submit_pattern = re.compile(r"^(Submit|Kirim|Send|Enviar|Envoyer|Senden)$", re.IGNORECASE)
        submit_btn = page.locator('div[role="button"]').filter(has_text=submit_pattern)
        if not submit_btn.count():
            submit_btn = page.get_by_role("button", name=submit_pattern)
        if not submit_btn.count():
            submit_btn = page.locator('button[type="submit"]')
        if not submit_btn.count():
            submit_btn = page.locator('form div[role="button"]').last
        if not submit_btn.count():
            raise BrowserEngineError("Could not locate the submit button on the Google Form.")

        btn = submit_btn.first
        btn.scroll_into_view_if_needed()
        btn.click()

        try:
            page.wait_for_function(
                """() => {
                    const text = (document.body && document.body.innerText) || '';
                    const href = window.location.href || '';
                    return /recorded|direkam|formResponse|terekam/i.test(text) || href.includes('formResponse');
                }""",
                timeout=15000,
            )
        except Exception:
            alerts = page.locator('div[role="alert"], div.RHiDh, span.j03rae')
            if alerts.count():
                msg = alerts.first.inner_text().strip()
                raise BrowserEngineError(f"Submission failed with validation error: {msg}")
            raise BrowserEngineError("Form submitted but confirmation was not received within timeout.")
