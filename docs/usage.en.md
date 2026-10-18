# Usage and maintenance

[Back to README](../README.en.md) · [中文](usage.md)

> Implementation follows the [specification](browser-upgrade-requirements.md) (Chinese): headed by default on every platform, explicit `--headless`, and fresh school-record checks without state migration. Offline checks do not establish real reservation or long-running acceptance.

## Commands

| Command | Behavior |
| --- | --- |
| `uv run --locked main.py --check` | Browser login, All history and lecture lists, record validation; no reservation dialog, submission, email or task creation |
| `uv run --locked main.py` | Start or resume real reservations |
| `uv run --locked main.py --headless` | Reserve without a window; also works with `--check` |
| `uv run --locked main.py --status` | Local task and process lock, without browser or school credentials |
| `uv run --locked main.py --test-mail` | Send one real email without school login or task creation |
| `uv run --locked main.py --new-task` | Recheck a completed goal; cannot reset active or unconfirmed tasks |

The project-root `.env` loads automatically. Process variables take precedence. Restart after changes. Browser mode comes only from command-line arguments; old `SEU_HEADLESS` settings are ignored. `captcha_ocr.py` also defaults to headed and accepts `--headless`. `--new-task` remains for compatibility: normal startup already logs in and rechecks a locally completed goal without this flag. `--check` does not verify real submissions or OCR; email needs explicit `--test-mail` and an inbox check.

## Configuration

| Variable | Meaning and default |
| --- | --- |
| `SEU_CARD_NUMBER`, `SEU_PASSWORD` | Required for operation and read-only checks, not status or test email |
| `SEU_PREFERRED_LECTURES` | Exact title array, default `[]`; all other filters apply |
| `SEU_REQUIRED_CATEGORIES` | Candidate categories/order; mental health, law, art, other; cannot be empty or repeated; salons remain excluded |
| `SEU_PREFERRED_CAMPUS` | Offline campus allowlist, default `[]` excludes offline lectures |
| `SEU_ENABLE_OFFLINE`, `SEU_ENABLE_ONLINE` | Both default to `true` |
| `SEU_STATE_DIR` | Private state/events; default `state` relative to the project, absolute paths allowed |
| `SEU_VPN_IP` | Optional VPN backup IPv4/IPv6; unset is empty, example prefills `121.249.14.2`, normal DNS first |
| `SEU_TIMEOUT_PAGE_LOAD` | Extra login-navigation delay, default 0.5 seconds |
| `SEU_TIMEOUT_ELEMENT_WAIT` | Page, data, element and visible-result timeout, default 3 seconds; try 15 on slow networks |
| `SEU_TIMEOUT_LOGIN_REDIRECT` | Authentication redirect budget, default 30 seconds; no SMS input |
| `SEU_TIMEOUT_SCAN_INTERVAL` | Normal scan and confirmation-query interval, default 10 seconds, positive |
| `SEU_TIMEOUT_ACTION_CONFIRM` | Initial post-submit wait, default 0.2 seconds; ID verification still required |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Mailbox and app password; sufficient for Gmail |
| `SMTP_HOST`, `SMTP_PORT` | Explicit SMTP host and TLS port; Gmail defaults to `smtp.gmail.com:465` |
| `MAIL_FROM`, `MAIL_TO` | Explicit sender/recipient; default to the mailbox, sending to yourself |

Lists are JSON arrays, e.g. `SEU_PREFERRED_CAMPUS='["无锡校区"]'`. Switches use `true/false`; quote passwords with spaces or `#`. Waits must be finite and non-negative; zero Playwright timeouts become 1 ms. Legacy `SEU_TIMEOUT_RETRY_DELAY` is accepted but business failures use backoff. Old 0.05-second scan settings are not changed automatically: update them to ten seconds.

## Browser operations and rules

Playwright logs in, refreshes, clicks My Activities / All, reads attendance and reservations, refreshes lectures, locates a stable ID, clicks exactly Reserve, reads/fills the CAPTCHA, clicks Confirm, then verifies the same ID in My Activities / All.

Only existing Vue page data is read. There are no direct Vue business calls, injected fetch/XHR or separate HTTP clients. Loaded school time, error state, the All filter and matching model/card counts are checked. There is no historical total; `count` means unread notifications. Complete historical coverage remains unproven.

The goal is eight attended, non-breached, non-cancelled series lectures counted under the conflict rule, including law, art and mental health. Attendance plus upcoming reservations occupies remaining places, with priority and room for missing categories. Covered plans wait for attendance. Cancellation/breach reopens places; ended records with unknown attendance outcomes pause new reservations.

Titles, categories, campuses, online/offline and conflicts all apply. The browser convention identifies online lectures by “线上” in titles; no independent Boolean field exists. Naming changes require revalidation. All valid reservations block conflicting candidates, including touching endpoints. Existing overlaps are counted locally by attendance first, missing category, earlier finish, then ID; no school reservation is cancelled. Excluded records still block conflicts.

Missing categories precede configured category order, online lectures and earlier starts. Explicit wrong CAPTCHAs allow three replacement images after the initial one, then five-minute cooling. Pending state is saved before clicking Submit. Even visible success requires ID verification. Timeouts and unknown results never count as CAPTCHA rejection. Persistent uncertainty only queries and notifies once, without another submission or terminal Enter.

## Email notifications

Unset/empty mail fields disable email; `SMTP_PORT=465` alone also means disabled. Partial or invalid configuration stops startup. Gmail needs a mailbox and app password. Explicit host, port, sender and recipient override defaults. Other providers require a host. Certificate-verified `SMTP_SSL` and unauthenticated TLS relays are supported; plaintext SMTP is not.

Single success, completed goals, required authentication, uncertain results and catchable failures produce local events and optional email. Three consecutive query/processing failures notify once, resetting after recovery. Normal scans stay quiet. Mail contains event and time, without school credentials, titles, full personal records or tickets.

Mail failure records `notification_failed` without resending, changing reservation results or repeating bookings. SMTP acceptance does not prove inbox delivery. Forced termination, power loss or an unavailable mail service cannot guarantee notifications.

## Server setup

Install Chrome on Windows; registry App Paths supplements custom installations. Linux requires a supported Chrome installation and system libraries. The Chrome channel does not automatically install it; see [official Playwright documentation](https://playwright.dev/python/docs/browsers).

On supported Debian/Ubuntu systems, after an administrator installs Chrome, libraries can be prepared with:

```shell
uv run --locked python -m playwright install-deps chromium
```

This may require administrator privileges and modify system packages. This change did not run it or install/replace Chrome. Headless mode needs no remote desktop; headed Linux needs a graphical environment.

## Background operation and recovery

Before README's `nohup` command (with `--headless`), check `--status` for another runner. Locks cover one state directory only. Run one instance per account across all hosts and both projects; there is no distributed lock. A new machine can log in and read university records without transferring state. Local files support recovery on the same machine and do not guarantee deduplication across hosts.

```shell
uv run --locked main.py --status
tail -n 20 state/runner.log
tail -n 20 state/events.log
```

`scanning/pending/done` describes tasks, not health. Also inspect `process_running` (the lock), `phase`, successful-query time and errors. `manual_required` means blocked authentication. After stopping, `phase=stopped` and `last_phase` preserves the previous phase.

Check a background PID's command and directory before stopping:

```shell
reserve_pid=$(cat state/runner.pid)
ps -p "$reserve_pid" -o pid,ppid,args
readlink "/proc/$reserve_pid/cwd"
```

After confirming this project, run `kill -TERM "$reserve_pid"` and verify exit. Keep the state directory and restart with the same command; backoff and pending results survive. There is no active-task reset, automatic cancellation, background SMS input, daemon or automatic restart. Do not delete state to bypass pending-result protection. Adjust paths for custom state directories.

## Network and authentication

Initial login starts with DNS. Only unrecovered VPN main-frame `ERR_NAME_NOT_RESOLVED`, `ERR_CONNECTION_CLOSED` or `ERR_CONNECTION_RESET` permits one backup-IP restart. Ordinary timeouts, certificate/credential errors, other domains and subresources do not. Business operations never switch IPs automatically. Domain certificate checks remain enabled; system DNS/Clash is unchanged. Remote-resolving proxies may ignore the mapping.

Legacy school HTTP callbacks receive a local browser 307 to HTTPS on the same host; the original HTTP request is never sent, while nested service identifiers remain unchanged. Other HTTP requests are blocked. Credentials are filled only on trusted school HTTPS origins. Diagnostics omit raw Playwright logs; authentication HTML/screenshots are not automatically saved.

Expired sessions first try login again. Incomplete authentication preserves the task, stops business actions and optionally emails. SMS sending/input and remote desktop are not implemented. Automatic operation depends on the school not requiring human intervention.

## Development and acceptance

```shell
uv run --locked python -m unittest discover -s tests -v
```

Offline tests use temporary configuration, business substitutes and synthetic Chrome pages with all page requests intercepted; they do not load the real `.env`. Coverage includes modes, login/cleanup, local HTTPS redirects, VPN fallback, goals/conflicts, pending results, locks/restart, mail failure and stable-ID actions. `captcha_ocr.py` shares browser modes for sample collection; `captcha_fetch.py` remains an offline evaluator. Existing image assets are unchanged.

Implementation checks on 2026-10-18: all 68 offline tests passed; ten source files passed mypy (`--check-untyped-defs`), and lockfile/dependency compatibility checks passed. Regression checks cover mode arguments and fresh verification after local completion. This implementation run did not contact the university or send real email.

Authorized read-only acceptance on 2026-10-18: Windows Chrome passed real login, All history reads and candidate validation in both modes, including HTTPS callback upgrading. No reservations/cancellations, test emails or real `.env` edits occurred. Linux, real reservations, actual OCR, human-authentication scenarios, cross-day sessions and at least 24-hour operation remain unverified.

Goal, state and email code comes from the maintainer's HTTPS project at `96b9c5c`. Repositories have no runtime dependency and the source is unchanged. Chinese documentation: [requirements](browser-upgrade-requirements.md), [ADR 0001](adr/0001-browser-only-reservations.md), [glossary](../GLOSSARY.md), [historical assessment](design-assessment.md), [historical network specification](network-recovery-requirements.md).
