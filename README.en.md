# SEU Lecture Reservation

[中文](README.md)

An automation script for Southeast University's Humanities and Scientific Literacy lecture reservations, with CAPTCHA recognition, lecture filtering, and SMS authentication that may require manual interaction. This repository is independently maintained, based on [ApricityWang/SEU_Lecture_Reserve](https://github.com/ApricityWang/SEU_Lecture_Reserve).

## Features and execution flow

`uv run main.py` automatically loads the project-root `.env`, validates configuration, initializes OCR, and opens Chrome. It submits your credentials and waits for a login redirect or manual SMS verification. After login, it repeatedly refreshes the lecture page, filters candidates, and attempts reservations.

- Without explicitly selected lecture titles, filtering uses categories, campuses, online/offline switches, and time conflicts with reservations found on the current page.
- Scanning continues when no suitable lecture exists or an attempt fails. The program exits and closes the browser after it detects one successful reservation.
- Success detection uses page content. Confirm the actual reservation in the [SEU portal](https://ehall.seu.edu.cn/).

## Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), Chrome, and a [ChromeDriver](https://googlechromelabs.github.io/chrome-for-testing/) compatible with your browser and operating system. On Windows, place `chromedriver.exe` in the project root; on macOS/Linux, use an executable `chromedriver`. A driver on `PATH` can also be used; automatic acquisition depends on the local environment and network.

First-time setup:

```shell
git clone https://github.com/MuZiJin701/SEU_Lecture_Reserve.git
cd SEU_Lecture_Reserve
uv sync --locked
cp .env.example .env
```

uv selects Python 3.11 from `.python-version`, downloads the interpreter if necessary, and installs locked dependencies into `.venv`. No manual virtual environment activation is needed. Dependencies are declared in `pyproject.toml` and locked in `uv.lock`; `requirements.txt` is no longer used.

Edit `.env` with your credentials and filters. Preserve an existing `.env` rather than replacing it. Run from the project root:

```shell
uv run main.py
```

Git ignores `.env`, local drivers, generated CAPTCHA samples, and login-error page/screenshot files. Only commit [.env.example](.env.example) without real credentials.

## Configuration

The application uses `python-dotenv` to load `.env` beside `config.py`. Existing process variables take precedence. Launching directly with the project's virtual environment Python also loads configuration; `--env-file` is unnecessary. `uv run --locked main.py` additionally checks that the lockfile matches project configuration, failing if an update is required.

See [.env.example](.env.example) for every variable and default:

| Variable | Purpose and format |
| --- | --- |
| `SEU_CARD_NUMBER`, `SEU_PASSWORD` | Required campus card number and password; quote values containing spaces or characters such as `#` |
| `SEU_PREFERRED_LECTURES` | Exact lecture-title array; `[]` uses normal filtering |
| `SEU_REQUIRED_CATEGORIES` | Category allowlist as a JSON string array; an empty array matches no category |
| `SEU_PREFERRED_CAMPUS` | Campus allowlist, e.g. `'["无锡校区"]'`; names must match the system exactly |
| `SEU_ENABLE_OFFLINE`, `SEU_ENABLE_ONLINE` | Offline/online reservation switches using `true` or `false` |
| `SEU_TIMEOUT_PAGE_LOAD` | Basic wait after loading a page; default 0.5 seconds |
| `SEU_TIMEOUT_ELEMENT_WAIT` | Wait for page elements; default 3 seconds |
| `SEU_TIMEOUT_LOGIN_REDIRECT` | Wait after login submission; default 2 seconds, temporarily increase to 60 for manual SMS verification |
| `SEU_TIMEOUT_SCAN_INTERVAL` | Additional wait after each scan; default 0.05 seconds, not the entire scan duration |
| `SEU_TIMEOUT_RETRY_DELAY` | Retry wait; default 0.05 seconds |
| `SEU_TIMEOUT_ACTION_CONFIRM` | Wait after reservation submission; default 0.2 seconds |

Lists use JSON arrays, enclosed in single quotes in `.env`, for example:

```dotenv
SEU_PREFERRED_CAMPUS='["无锡校区"]'
SEU_PREFERRED_LECTURES='[]'
SEU_ENABLE_OFFLINE=true
SEU_ENABLE_ONLINE=true
SEU_TIMEOUT_LOGIN_REDIRECT=60
```

Unset optional variables use application defaults. Empty values are different from unset variables: blank list, boolean, and numeric values are rejected. Wait times must be finite and non-negative; the scan interval must be positive. Missing credentials or invalid configuration stop execution before browser creation. Without `.env`, system environment variables can supply the configuration.

**Explicit-title mode limitation:** when `SEU_PREFERRED_LECTURES` is non-empty, an exact title match with an available reservation status is accepted immediately, bypassing category, campus, online/offline, and time conflict checks. Keep `[]` when those filters are required.

In normal mode, the campus list defaults to empty, filtering out offline lectures. A title containing “线上” identifies an online lecture; those lectures bypass the campus allowlist but still obey category and online-switch checks.

## SMS verification, stopping, and browser behavior

- The browser is visible by default. For a first login or expired authentication, allow enough `SEU_TIMEOUT_LOGIN_REDIRECT` time to complete SMS verification manually, then restore the normal delay.
- Press `Ctrl+C` to stop; the main script attempts to close its browser. Minimizing the terminal keeps it running. Closing the hosting terminal usually terminates the process; forced closure may leave browser processes behind.
- This is a foreground process with no background persistence or scheduling. Stopping it does not cancel reservations already submitted successfully.
- Both login scripts retain automatic Chrome discovery and exclude `enable-logging` to avoid extra console windows in some Windows/Scoop environments. This reduces Chrome's internal logs; application output remains available.
- For headless operation, uncomment `chrome_options.add_argument("--headless")` in `main.py`. Keep a visible browser when manual SMS authentication is needed. Headless operation does not provide background persistence.

## Helper scripts and checks

| Command | Purpose |
| --- | --- |
| `uv run captcha_ocr.py` | Logs into the real system with the same configuration and collects CAPTCHA images into `image_dataset/`; opens a browser and is not an offline check |
| `uv run captcha_fetch.py` | Evaluates OCR against existing images in `image/`, using their filenames as expected answers; no login credentials needed |
| `uv run --locked python -m unittest discover -s tests -v` | Configuration regression checks; does not access the reservation system or read your real local `.env` |

`main.py` is the reservation entry point, `config.py` loads and validates shared configuration, and `tests/test_config.py` contains configuration tests. Update both READMEs and [.env.example](.env.example) when startup or configuration behavior changes.

## Validation and limitations

Validated: six configuration tests, lockfile and dependency consistency, local OCR inference, and the real ChromeOptions from both login scripts opening blank pages on Windows without extra consoles. Real login, SMS verification, and reservations have not been fully validated; macOS/Linux have not been tested. OCR accuracy has not been remeasured, and recognition can fail.

Page structure, network conditions, wait times, and available seats affect results. Time conflict checks only consider reservations recognized on the current page. Check your full schedule yourself, follow university rules, and choose a reasonable scan interval.

## Engineering configuration

- [Project instructions](AGENTS.md): engineering Skills entry point and safe validation conventions.
- [Issue tracker](docs/agents/issue-tracker.md): tasks and specifications live in [this repository's Issues](https://github.com/MuZiJin701/SEU_Lecture_Reserve/issues).
- [Triage labels](docs/agents/triage-labels.md): five default labels and their meanings.
- [Domain documentation](docs/agents/domain.md): a single context, with `GLOSSARY.md` and `docs/adr/` created when needed.

Edit `docs/agents/*.md` directly. Rerun the setup Skill when switching trackers or restarting configuration.

## Disclaimer

This project is for learning Python automation. The developers are not responsible for consequences of its use. By using it, you agree to follow Southeast University's rules, avoid destructive actions, and refrain from commercial use.
