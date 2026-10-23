# Qwen Forms Autoloop V1

A small, local-first QA utility for generating synthetic form test data and
checking local form fixtures. It also reads publicly available Google Forms
question metadata without filling or submitting the form. The app supports an
Ollama-backed dry-run and a bounded, deterministic local test mode.

## Safety and scope

- `--url` reads question metadata from a publicly accessible Google Forms
  `viewform` URL. It does not access authenticated forms or bypass CAPTCHA.
- Remote browser automation (`RemoteBrowserEngine`) allows filling (`--browser-fill`)
  and optional submission (`--submit`) of remote public Google Forms via Playwright Chromium.
- Runs in background headless mode by default; add `--headful` to view the browser window.
- All submissions are recorded in `output/results.json` and `output/results.csv`.
- Every generated profile and answer is synthetic for testing purposes. Do not use this tool
  to impersonate respondents or manipulate survey results.

## Requirements and installation

Python 3.11 or newer is recommended.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
playwright install chromium chromium-headless-shell
```

Ollama is optional for local tests. For AI dry-runs, install Ollama, then:

```powershell
ollama pull qwen2.5-coder:1.5b
```

`.env.example` documents supported environment variables. Set them in the
shell if defaults need to change; the app intentionally does not load an
unlisted `.env` file or store credentials.

## Commands

```powershell
# Aktifkan virtual environment (agar Playwright & Ollama terdeteksi):
.\.venv\Scripts\Activate.ps1
# Atau jalankan langsung: .\.venv\Scripts\python.exe main.py ...

python main.py --help
python main.py --check
python main.py --dry-run
python main.py --dry-run --fixture fixtures\sample_form.json

# Remote Google Forms (read-only questions & preview)
python main.py --url "https://docs.google.com/forms/d/FORM_ID/viewform"
python main.py --dry-run --url "https://docs.google.com/forms/d/FORM_ID/viewform"

# Remote Google Forms (Browser Fill - headless background)
python main.py --url "https://docs.google.com/forms/d/FORM_ID/viewform" --browser-fill

# Remote Google Forms (Browser Fill & Submit - headless background)
python main.py --url "https://docs.google.com/forms/d/FORM_ID/viewform" --submit

# Remote Google Forms (Visible browser window)
python main.py --url "https://docs.google.com/forms/d/FORM_ID/viewform" --browser-fill --headful

# Multiple submissions (misal: 10 atau 50 tanggapan)
python main.py --url "https://docs.google.com/forms/d/FORM_ID/viewform" --submit --iterations 10 --delay 1.0

# Continuous / Loop terus-menerus (berhenti dengan menekan Ctrl+C)
python main.py --url "https://docs.google.com/forms/d/17SM7ORmzUMZuwJpDSNAPPl_ARes_v1WmXBWC0OMaCE4/viewform" --continuous --delay 1.5

# Continuous dengan jendela browser terlihat
python main.py --url "https://docs.google.com/forms/d/17SM7ORmzUMZuwJpDSNAPPl_ARes_v1WmXBWC0OMaCE4/viewform" --continuous --headful

# Local fixture tests
python main.py --local-test --iterations 5
python main.py --local-test --iterations 2 --fixture fixtures\sample_form.html
python main.py --local-test --iterations 2 --fixture fixtures\sample_form.html --browser-fill

# Results export
python main.py --export json
python main.py --export csv
```

`--check` verifies the local Ollama endpoint and configured model. `--dry-run`
generates and validates synthetic answers without opening a browser or submitting.
`--url` reads public form questions. Combined with `--browser-fill`, it uses
Playwright Chromium to fill fields in the background. Combined with `--submit`,
it automatically clicks the submit button and verifies recorded confirmation.
`--iterations` (alias `-n`) controls the number of submissions.
`--continuous` (alias `--loop`) sends responses continuously until stopped with Ctrl+C.
`--delay` sets the pause between consecutive submissions in seconds (default: 1.0s).
`--headful` disables headless mode so the browser window is visible.

## Tests

```powershell
python -m pytest
```

Tests cover fixture parsing, answer validation, scenario variation and
duplicate detection, local controller bounds, output export, and mocked Ollama
responses. They do not require a running Ollama service or a browser install.
