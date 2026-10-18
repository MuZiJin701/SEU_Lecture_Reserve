# Usage and maintenance

[Back to README](../README.en.md) · [中文](usage.md)

> Implementation follows the [specification](browser-upgrade-requirements.md) (Chinese): headed by default on every platform, explicit `--headless`, and fresh school-record checks without state migration. Offline checks do not establish real reservation or long-running acceptance.

## Commands

| Command | Behavior |
| --- | --- |
| `uv run main.py --check` | Browser login, All history and lecture lists, record validation; no reservation dialog, submission, email or task creation |
| `uv run main.py` | Start or resume real reservations |
| `uv run main.py --headless` | Reserve without a window; also works with `--check` |
| `uv run main.py --status` | Local task and process lock, without browser or school credentials |
| `uv run main.py --test-mail` | Send one real email without school login or task creation |
| `uv run main.py --new-task` | Recheck a completed goal; cannot reset active or unconfirmed tasks |

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
| `SEU_TIMEOUT_ELEMENT_WAIT` | Page, data, element and visible-result timeout; built-in default 3 seconds, template preset 15 |
| `SEU_TIMEOUT_LOGIN_REDIRECT` | Authentication redirect budget; built-in default 30 seconds, template preset 60; no SMS input |
| `SEU_TIMEOUT_SCAN_INTERVAL` | Normal scan and confirmation-query interval, default 10 seconds, positive |
| `SEU_TIMEOUT_ACTION_CONFIRM` | Initial post-submit wait, default 0.2 seconds; ID verification still required |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Mailbox and app password; sufficient for Gmail |
| `SMTP_HOST`, `SMTP_PORT` | Explicit SMTP host and TLS port; Gmail defaults to `smtp.gmail.com:465` |
| `MAIL_FROM`, `MAIL_TO` | Explicit sender/recipient; default to the mailbox, sending to yourself |

Lists are JSON arrays, e.g. `SEU_PREFERRED_CAMPUS='["无锡校区"]'`. Switches use `true/false`; quote passwords with spaces or `#`. Waits must be finite and non-negative; zero Playwright timeouts become 1 ms. Legacy `SEU_TIMEOUT_RETRY_DELAY` is accepted but business failures use backoff. Old 0.05-second scan settings are not changed automatically: update them to ten seconds.

`.env.example` uses Chinese comments and presets page/element and authentication redirect waits to 15 and 60 seconds for slow networks; other waits retain their built-in defaults. Merge changes into an existing `.env` manually and restart, preserving credentials; process variables still take precedence. The backup VPN IP is a historically verified value: update or clear it when stale. The template contains no personal campus selection, account or mail credentials.

## Browser operations and rules

Playwright controls Chromium to log in, refresh, click My Activities / All, read attendance and reservations, refresh lectures, locate a stable ID, click exactly Reserve, read/fill the CAPTCHA, click Confirm, then verify the same ID in My Activities / All.

Only existing Vue page data is read. There are no direct Vue business calls, injected fetch/XHR or separate HTTP clients. Loaded school time, error state, the All filter and matching model/card counts are checked. There is no historical total; `count` means unread notifications. Complete historical coverage remains unproven.

The goal is eight attended, non-breached, non-cancelled series lectures counted under the conflict rule, including law, art and mental health. Attendance plus upcoming reservations occupies remaining places, with priority and room for missing categories. Covered plans wait for attendance. Cancellation/breach reopens places; ended records with unknown attendance outcomes pause new reservations.

Titles, categories, campuses, online/offline and conflicts all apply. Only explicit 【线上】 or 【线下】 prefixes at the start of a title determine the mode; “线上” elsewhere in a title is ignored. Missing markers pause new reservations with `activity_schema_unknown`. There is no independent Boolean field; naming changes require revalidation. All valid reservations block conflicting candidates, including touching endpoints. Existing overlaps are counted locally by attendance first, missing category, earlier finish, then ID; no school reservation is cancelled. Excluded records still block conflicts.

Missing categories precede configured category order, online lectures and earlier starts. Explicit wrong CAPTCHAs allow three replacement images after the initial one, then five-minute cooling. Pending state is saved before clicking Submit. Even visible success requires ID verification. Timeouts and unknown results never count as CAPTCHA rejection. Persistent uncertainty only queries and notifies once, without another submission or terminal Enter.

## Runtime diagnostics

`--check` shares activity validation and selection with normal scans. Missing titles, categories, locations, activity IDs or explicit online/offline markers, invalid lecture times, and invalid supplied reservation windows fail the check, including for unavailable activities. It prints `activity_details` without creating or changing tasks, using task cooldown records, opening reservation dialogs, running OCR or testing real submissions.

Normal scans save the latest per-activity results in private `state/task.json`. Use `uv run main.py --status` to inspect `selection_updated_at` and `activity_details`. Each entry contains the title, first matching selection reason, and school-provided reservation start/end in Beijing time (`null` when absent). A candidate still needs preflight and submission confirmation. Snapshots survive restarts and may remain old during failures, pending-result confirmation or attendance waits; they are not necessarily current school results. Activity details do not enter event logs or emails. Keep state files and terminal output containing details private.

| Reason | Meaning |
| --- | --- |
| `candidate` | Passed current filters; not a confirmed reservation |
| `reservation_not_started` | School page marks booking as not yet open |
| `capacity_full` | School page marks capacity as full |
| `not_reservable` | No reservable marker; exact cause unknown, not proof of full capacity or a passed deadline |
| `already_reserved` | Already reserved in school records |
| `category_not_allowed` / `category_not_needed` | Category excluded by configuration / not currently needed for the goal |
| `title_not_selected` | Does not match the configured exact titles |
| `online_disabled` / `offline_disabled` | This teaching mode is disabled |
| `campus_not_selected` | Offline location is outside the campus allowlist |
| `time_conflict` | Overlaps or touches an existing reservation |
| `cooldown` | CAPTCHA-failure cooldown is still active |

`last_mail_at` and `last_mail_status` retain the latest mail attempt and outcome across restarts. `accepted` means SMTP acceptance only, `failed` means sending failed, `sending` means the outcome is unconfirmed, and `never` means no recoverable record. Disabling mail sets `mail_status=disabled` while retaining history. Old state restores only existing mail evidence; daily-report deduplication timestamps do not prove delivery, and previously lost results cannot be recovered.

## Email notifications

Email is optional. Each user configures their own sending account; no shared notification backend is needed. Never share app passwords. Unset/empty mail fields disable email; `SMTP_PORT=465` alone also means disabled. Partial or invalid configuration stops startup.

Gmail needs only `SMTP_USERNAME` and `SMTP_PASSWORD`. Full creation and setup steps are in the [README configuration section](../README.en.md#2-configure-account-campus-and-email). Use your full Gmail address and a 16-character app password created after enabling 2-Step Verification, omitting grouping spaces. Do not enter a Google login password or SMS code. The password is shown once; generate another if lost. Changing your Google login password revokes existing app passwords: create a replacement and update `.env`. Stop any running instance, verify with `uv run main.py --test-mail`, then resume reservations.

If App passwords is unavailable, check that the correct account is signed in and 2-Step Verification is enabled. Security-key-only verification, organizational restrictions or Advanced Protection may prevent access; see [Google's official explanation](https://support.google.com/accounts/answer/185833). Use another sender supporting SMTP SSL/TLS or clear the mail settings to disable notifications when unavailable.

Messages go to yourself by default. Optional `MAIL_TO` selects one recipient, including another provider. Other sending providers also require `SMTP_HOST` and their specified credentials; the default port is 465. `MAIL_FROM` defaults to the sending account, and overrides must be allowed by the provider. Certificate-verified `SMTP_SSL` and unauthenticated TLS relays are supported; STARTTLS and plaintext SMTP are not.

Single success, completed goals, required authentication, uncertain results and catchable failures produce local events and optional email. Three consecutive query/processing failures notify once, resetting after recovery. Normal scans stay quiet. Email includes a Chinese explanation and suggested action, without school credentials, titles, full personal records or tickets.

With email enabled, the running program reports attendance, upcoming reservations, missing categories (including planned coverage), progress timestamp, latest successful query and pending issues at 20:00 Asia/Shanghai each day. Waiting and backoff wake for email without making early school requests. Page operations or SMTP waits may delay the report. Query failures retain the latest verified progress with its timestamp; unavailable data is marked unknown, never zero. Progress not yet rebuilt after restarting a pending submission is also unknown.

There is at most one report attempt per day per state directory, saved before SMTP. Starting after 20:00 sends the day's report at the first wait, without catching up earlier days. Disabled email, read-only checks, stopped programs and completed tasks send no further daily reports. Failed reports and other notifications are not retried automatically.

Mail failure records `notification_failed` without resending, changing reservation results or repeating bookings. SMTP acceptance does not prove inbox delivery. Forced termination, power loss or an unavailable mail service cannot guarantee notifications.

To troubleshoot, stop the running instance, remove grouping spaces from the Gmail app password, then run `uv run main.py --test-mail`. `notification_failed` alone does not distinguish network, TLS, authentication or sender/recipient errors. If a connection probe confirms a TLS handshake failure, check the SMTP host, port, proxy rules and node support for that port before blaming the password; web browsing does not establish SMTP connectivity. TUN may already route the connection through the proxy: inspect proxy connection logs and compare another node. Keep certificate validation enabled and do not simply switch to unsupported port 587 STARTTLS.

See the current [notification requirements](notification-requirements.md) (Chinese).

## Server setup

The [README](../README.en.md#1-install) contains the complete tool installation, browser setup, account/email configuration and checks. The server path targets Ubuntu 24.04 using an existing account with sudo or root access. The project uses Python 3.11.

Install the browser with `uv run playwright install chromium`. On Ubuntu, use `uv run playwright install --with-deps chromium` to prepare system libraries too. Use the same account for installation and operation to keep browser caches consistent. If only system libraries are missing, use `uv run playwright install-deps chromium`.

Playwright stores browsers in its user cache. The default install also downloads a headless shell; this project uses full Chromium in both modes. Initial downloads need internet access. Reinstall after updating Playwright; startup never downloads browsers automatically. See [Playwright's browser documentation](https://playwright.dev/python/docs/browsers).

Headless mode needs no desktop; windowed mode needs a graphical environment. Add `--headless` to server checks and reservations. After installing uv, follow its PATH instructions or reconnect over SSH.

## Background operation and recovery

Complete commands for starting, creating logs, saving the PID, inspecting and stopping a process are kept together in the [README's Ubuntu background section](../README.en.md#ubuntu-background-operation). The default directory is `state/`; adjust log and PID paths when using a custom state directory.

`nohup`, `&` and redirected input/output keep the process running after terminal disconnection. They do not provide crash recovery or boot startup. Restart manually after a server reboot, program exit or authentication stop. Servers with logout cleanup policies need an actual SSH-disconnect check. See [GNU's nohup manual](https://www.gnu.org/software/coreutils/manual/html_node/nohup-invocation.html).

`uv run main.py --status` distinguishes task state from the current process. `scanning/pending/done` alone does not establish health: inspect `process_running`, `phase`, successful-query timestamps and errors. `manual_required` means blocked authentication. After stopping, `phase=stopped` and `last_phase` preserves the previous phase. `runner.log` holds terminal output and `events.log` holds events. Logs keep growing; maintain them according to disk usage.

Check the PID's command and working directory before stopping, since stale PIDs may belong to other processes. The default `kill` signal is SIGTERM; on Unix, uv forwards it to Python so the program saves state and closes the browser. Wait for `process_running=false` before restarting. See [uv's signal handling](https://docs.astral.sh/uv/concepts/projects/run/#signal-handling).

Locks cover one state directory only. Run one instance per account across all machines and both projects; stop the old instance before switching machines. Keep the original state directory to restore pending results, cooldowns and backoff. Never delete state to bypass pending-result protection. A new machine needs no state transfer to read school records, but submission deduplication across machines is not guaranteed.

## Network and authentication

Initial login starts with DNS. Only unrecovered VPN main-frame `ERR_NAME_NOT_RESOLVED`, `ERR_CONNECTION_CLOSED` or `ERR_CONNECTION_RESET` permits one backup-IP restart. Ordinary timeouts, certificate/credential errors, other domains and subresources do not. Business operations never switch IPs automatically. Domain certificate checks remain enabled; system DNS/Clash is unchanged. Remote-resolving proxies may ignore the mapping.

Legacy school HTTP callbacks receive a local browser 307 to HTTPS on the same host; the original HTTP request is never sent, while nested service identifiers remain unchanged. Other HTTP requests are blocked. Credentials are filled only on trusted school HTTPS origins. Diagnostics omit raw Playwright logs; authentication HTML/screenshots are not automatically saved.

`host=<unknown>` means the request domain is outside the three school domains allowed in diagnostics, not a DNS-resolution failure. Neither a failed subresource nor successful login establishes a working query round. For blank/loading pages, `page_not_ready` or `history_navigation_failed`, stop with `Ctrl+C`, keep `state/`, inspect browser errors and manually verify page loading and My Activities / All navigation, then check proxy logs. Use the template's 15-second element wait for slow loading; longer timeouts alone cannot fix persistent connection failures or incompatible page structure. After changes, run `uv run main.py --check` and require `event=read_only_complete` before resuming reservations; test email separately.

Expired sessions first try login again. Incomplete authentication preserves the task, stops business actions and optionally emails. SMS sending/input and remote desktop are not implemented. Automatic operation depends on the school not requiring human intervention.

## Development and acceptance

```shell
uv run --locked python -m unittest discover -s tests -v
```

Offline tests use temporary configuration, business substitutes and synthetic pages in Playwright-managed Chromium with all page requests intercepted; they do not load the real `.env`. Coverage includes modes, missing-browser instructions, login/cleanup, local HTTPS redirects, VPN fallback, goals/conflicts, pending results, locks/restart, mail failure and stable-ID actions. `captcha_ocr.py` shares browser modes for sample collection; `captcha_fetch.py` remains an offline evaluator. Existing image assets are unchanged.

Implementation checks on 2026-10-18: all 69 offline tests passed; ten source files passed mypy (`--check-untyped-defs`), and lockfile/dependency compatibility checks passed. Regression checks cover mode arguments and fresh verification after local completion. Review found two issues, now fixed and covered: overlapping records hiding ended unresolved attendance, and non-ASCII CAPTCHA output entering pending state before submission. This implementation run did not contact the university or send real email.

Authorized read-only acceptance on 2026-10-18: Windows Chrome passed real login, All history reads and candidate validation in both modes, including HTTPS callback upgrading. No reservations/cancellations, test emails or real `.env` edits occurred. Linux, real reservations, actual OCR, human-authentication scenarios, cross-day sessions and at least 24-hour operation remain unverified.

Later browser update on 2026-10-18: as requested, all entry points now use Playwright-managed Chromium, with no system Chrome discovery and clear installation instructions when missing. All 69 offline tests passed on Windows using a temporary browser cache, including windowed and headless synthetic pages. No school access or real email occurred. The earlier Chrome acceptance record does not establish real login acceptance for Chromium.

Email update on 2026-10-18: each user optionally configures their own sender, with self-delivery by default. Chinese notifications and daily 20:00 Asia/Shanghai reports were added. All 75 offline tests passed, including cross-day scheduling, restart deduplication, reports during backoff and pending-result protection. Documentation links passed checks. No school access or real email occurred.

Documentation/deployment update on 2026-10-18: account, campus and email setup now precedes execution. The README covers Ubuntu tools, background startup, logs, stopping and recovery; runtime instructions use the same short commands. Nine browser-boundary and seven mail checks passed, along with bilingual command parity, configuration order, local links and Bash syntax. A local WSL fixture passed. Authorized checks on Ubuntu 24.04.5 LTS used existing uv 0.12.23 and a temporary fixture to verify survival after an SSH session ended, continued heartbeats, logs/PID, hangup handling, SIGTERM forwarding and cleanup. The connection used root; no regular account was created, system dependencies installed, real project browser launched, school accessed or email sent. This is not full deployment or Linux reservation acceptance.

Runtime-diagnostics fixes on 2026-10-18: strict title-prefix mode detection, shared read-only/normal selection validation, mail-history preservation across restarts, and timestamped per-activity selection snapshots. All 82 offline tests passed under Linux Xvfb, including old-state compatibility, wrong-campus rejection, unavailable-activity validation and diagnostic output. Installed dependency compatibility passed. This change did not contact the school, submit reservations or send email; the background process remains stopped. Earlier headless Linux Chromium checks completed real login and read-only list queries, which do not establish real reservation acceptance for these fixes or at least 24-hour operation.

Goal, state and email code comes from the maintainer's HTTPS project at `96b9c5c`. Repositories have no runtime dependency and the source is unchanged. Chinese documentation: [requirements](browser-upgrade-requirements.md), [README and deployment conventions](readme-deployment-requirements.md), [ADR 0001](adr/0001-browser-only-reservations.md), [glossary](../GLOSSARY.md), [historical assessment](design-assessment.md), [historical network specification](network-recovery-requirements.md).
