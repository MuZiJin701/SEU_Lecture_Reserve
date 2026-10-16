# Usage and maintenance guide

[Back to README](../README.en.md) · [中文](usage.md)

## Full configuration

Edit the project-root `.env`, then restart. The file loads automatically; existing process environment variables take precedence. You can also configure everything through environment variables without `.env`. See [.env.example](../.env.example) for all defaults.

| Variable | Purpose and default |
| --- | --- |
| `SEU_CARD_NUMBER`, `SEU_PASSWORD` | Required campus card number and password |
| `SEU_VPN_IP` | Optional university VPN backup IPv4/IPv6 address; blank by default, normal DNS first, at most one fallback after an eligible initial-login network failure |
| `SEU_PREFERRED_LECTURES` | Exact title array; defaults to `[]` for normal filtering |
| `SEU_REQUIRED_CATEGORIES` | Category allowlist; five defaults listed in the example; an empty array matches no category |
| `SEU_PREFERRED_CAMPUS` | Campus allowlist; defaults to `[]`, excluding offline lectures |
| `SEU_ENABLE_OFFLINE`, `SEU_ENABLE_ONLINE` | Allow offline / online reservations; both default to `true` |
| `SEU_TIMEOUT_PAGE_LOAD` | Extra delay after login navigation or an error-recovery reload; default 0.5 seconds |
| `SEU_TIMEOUT_ELEMENT_WAIT` | Default timeout for navigation, element actions, and reservation confirmation; default 3 seconds |
| `SEU_TIMEOUT_LOGIN_REDIRECT` | Maximum wait to return to the reservation page after login; default 2 seconds, use 60 for manual SMS verification |
| `SEU_TIMEOUT_SCAN_INTERVAL` | Extra delay after each scan; default 0.05 seconds, not the full scan duration |
| `SEU_TIMEOUT_RETRY_DELAY` | Delay between retries; default 0.05 seconds |
| `SEU_TIMEOUT_ACTION_CONFIRM` | Initial delay after submission; default 0.2 seconds, followed by a target-button check within the element timeout |

Lists are JSON arrays enclosed in single quotes in `.env`. Switches use `true` / `false`, for example:

```dotenv
SEU_PREFERRED_CAMPUS='["无锡校区"]'
SEU_PREFERRED_LECTURES='[]'
SEU_ENABLE_OFFLINE=true
SEU_ENABLE_ONLINE=true
SEU_TIMEOUT_LOGIN_REDIRECT=60
```

Quote credentials containing spaces or `#`. Unset optional variables use defaults; blank lists, switches, or numbers are rejected. Wait times must be finite and non-negative, and the scan interval must be positive. Invalid configuration is reported before browser creation.

Times are configured in seconds and converted to Playwright milliseconds. A zero wait timeout becomes 1 ms to avoid unlimited waits. Increase `SEU_TIMEOUT_ELEMENT_WAIT` for slow networks; increasing `SEU_TIMEOUT_PAGE_LOAD` does not extend the navigation timeout.

## Network diagnostics and backup IP

Leave `SEU_VPN_IP` blank on a working network. If you have verified an available university VPN address, enter a single IPv4 or IPv6 literal in `.env`, then restart. Surrounding whitespace is allowed. Hostnames, URLs, ports, IPv6 scope identifiers, and invalid input fail before browser creation without echoing the input. Existing environment variables still take precedence.

Both entries initially use normal DNS. Only a failed initial login with an unrecovered main-frame navigation failure for the university VPN, using `ERR_NAME_NOT_RESOLVED`, `ERR_CONNECTION_CLOSED`, or `ERR_CONNECTION_RESET`, can close the original browser and restart once with the backup IP. Login starts again from the lecture entry; state is not transferred, and SMS verification may be required again. A failed backup attempt exits. A successful login, missing backup address, certificate error, ordinary wait timeout, credential or SMS failure, or a failed subresource, child frame, or other domain does not trigger fallback.

Console diagnostics use `host=university-domain reason=safe-error-type`. Unknown hosts and errors use fixed categories. Full redirect URLs, tickets, cookies, credentials, and raw Playwright call logs are omitted. A closed or reset connection does not establish a DNS fault.

The override only affects this program's `vpn.seu.edu.cn` resolution and retains the HTTPS domain and certificate checks. It does not change system DNS, Clash, or routes for other sites, and does not discover IPs. The address may expire and cannot fix every network or authentication failure. Explicit proxies that resolve domains remotely may ignore this local override; the program does not automatically bypass them.

After initial login, scanning, reservations, CAPTCHA collection, and existing re-login paths only gain network diagnostics. They do not automatically switch IPs or restart Chrome. Existing reservation retries and confirmation rules are unchanged; check uncertain submission results in the university system.

## Filtering and confirmation

Normal mode filters by category, campus, online/offline switches, and time conflicts with reservations on the current page. Titles containing “线上” are considered online lectures. They bypass the campus allowlist but still obey the category and online switch, among other filters.

When `SEU_PREFERRED_LECTURES` is non-empty, an exact title match with a “预约” button passes immediately, bypassing category, campus, online/offline switches, and time conflict checks. Keep `[]` when those checks are needed.

Each scan attempts only the first sorted candidate. Each call allows up to three attempts, then scanning continues. Success requires the target button to change to “取消预约”. Ambiguous duplicate titles are skipped. The program exits after confirming one reservation; check the final result in the university system.

Current limits:

- Conflicts only cover the current page. Unparseable lectures may be skipped, and conflict-check errors count as no conflict.
- Online lectures precede offline lectures. The campus list order does not define priority.
- A repeatedly failing first candidate may block others. An expired session may appear as an empty list.
- Confirmation depends on an updated target card. Site changes, network conditions, and available seats affect results. OCR accuracy and scan performance have not been remeasured.

## Troubleshooting

| Situation | What to do |
| --- | --- |
| Chrome cannot be found | Install or repair Google Chrome; ChromeDriver and an extra Playwright Chromium download are not needed |
| Not enough time for SMS verification | Set `SEU_TIMEOUT_LOGIN_REDIRECT` to 60 or longer, restart, and complete verification in the visible browser |
| Navigation or element timeout | Check your network and increase `SEU_TIMEOUT_ELEMENT_WAIT` as needed |
| VPN DNS failure, closed or reset connection | Check the safe network diagnostic and your network/Clash. A verified `SEU_VPN_IP` allows one restart during initial login. Keep certificate checks enabled |
| No lectures found repeatedly | Check campuses, categories, and switches; selected titles must match exactly. If the browser has returned to login, stop and restart |
| Login fails | Distinguish network diagnostics from the browser's authentication state. Local `error_page_source.html` and `error_login.png` can help; do not upload authentication information |

## Browser and stopping

Both entries share `browser.py` and Playwright's synchronous API, using installed Chrome. Windows supplements discovery through registry App Paths, including registered Scoop installations. Other platforms use the Chrome channel's standard locations. Startup excludes `--enable-logging`.

The browser is visible by default. If manual verification is unnecessary, set `headless` to `True` in `browser.py`; this affects both entries. Headless mode does not provide background persistence. Minimizing the terminal keeps it running; closing it usually stops the process, and forced termination may leave browser processes. `Ctrl+C` attempts browser cleanup. Stopping does not cancel successfully submitted reservations.

## Helper scripts and development

| Command | Purpose |
| --- | --- |
| `uv run captcha_ocr.py` | Logs into the real system and collects CAPTCHAs into `image_dataset/`; opens a browser |
| `uv run captcha_fetch.py` | Evaluates OCR offline using images in `image/`, named with their expected answers |
| `uv run --locked python -m unittest discover -s tests -v` | Full regression checks; requires installed Chrome, uses only blank and in-memory pages, and blocks page requests to external resources |
| `uv run --locked python -m unittest discover -s tests -p test_config.py -v` | Configuration-only checks without a browser, using temporary environment files rather than your real `.env` |

uv selects Python 3.11 from `.python-version`, downloads it if needed, and installs dependencies into `.venv`. Manual environment activation is unnecessary. Dependencies are declared in `pyproject.toml` and locked in `uv.lock`; `uv run --locked main.py` additionally checks lockfile consistency. There is no `requirements.txt` installation workflow.

`main.py` handles reservations, `browser.py` shares startup and login, and `config.py` loads configuration. Importing `main.py` / `captcha_ocr.py` does not load configuration, initialize OCR, or start a browser. Both OCR entries disable promotional output; the main program displays the maintainer and project URL.

Regression checks cover configuration, startup cleanup, login waits, initial-login backup IP recovery, safe network diagnostics, and simulated reservation pages. Real login, SMS verification, and reservations have not been fully validated; macOS/Linux have not been tested.

Keep `.env`, diagnostic pages/screenshots, generated samples, and caches local. Legacy ChromeDriver files can be deleted. Preserve project assets in `image/` and `images/`, and keep real credentials out of `.env.example`.

## Engineering documentation and credits

- [Project instructions](../AGENTS.md), [Issue tracker](agents/issue-tracker.md), [triage labels](agents/triage-labels.md)
- [Domain documentation](agents/domain.md), [glossary](../GLOSSARY.md), [design assessment](design-assessment.md) (Chinese)
- [Initial-login network recovery spec](network-recovery-requirements.md) (Chinese), [GitHub Issue #1](https://github.com/MuZiJin701/SEU_Lecture_Reserve/issues/1)

Maintained by [MuZiJin701](https://github.com/MuZiJin701), with work on uv, configuration, Playwright, regression tests, dependency cleanup, and documentation. Based on [ApricityWang's project](https://github.com/ApricityWang/SEU_Lecture_Reserve), retaining attribution for the original author and historical contributors.

This project is for learning Python automation. Follow university rules, avoid destructive actions, and do not use it commercially. The developers are not responsible for consequences of use.
