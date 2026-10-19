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
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Full sending address and authorization code/app password; sufficient for QQ, 163, 126 and Gmail |
| `SMTP_HOST`, `SMTP_PORT` | Empty host selects by those four domains; explicit host takes precedence; default implicit TLS port 465 |
| `MAIL_FROM`, `MAIL_TO` | Explicit sender/recipient; default to the mailbox, sending to yourself |

Lists are JSON arrays, e.g. `SEU_PREFERRED_CAMPUS='["无锡校区"]'`. Switches use `true/false`; quote passwords with spaces or `#`. Waits must be finite and non-negative; zero Playwright timeouts become 1 ms. Legacy `SEU_TIMEOUT_RETRY_DELAY` is accepted but business failures use backoff. Old 0.05-second scan settings are not changed automatically: update them to ten seconds.

`.env.example` uses Chinese comments and presets page/element and authentication redirect waits to 15 and 60 seconds for slow networks; other waits retain their built-in defaults. Merge changes into an existing `.env` manually and restart, preserving credentials; process variables still take precedence. The backup VPN IP is a historically verified value: update or clear it when stale. The template contains no personal campus selection, account or mail credentials.

## Browser operations and rules

Playwright controls Chromium to log in, refresh, click My Activities / All, read attendance and reservations, refresh lectures, locate a stable ID, click exactly Reserve, read/fill the CAPTCHA, click Confirm, then verify the same ID in My Activities / All.

Only existing Vue page data is read. There are no direct Vue business calls, injected fetch/XHR or separate HTTP clients. Loaded school time, error state, the All filter and matching model/card counts are checked. There is no historical total; `count` means unread notifications. Complete historical coverage remains unproven.

The goal is eight attended, non-breached, non-cancelled series lectures counted under the conflict rule, including law, art and mental health. Attendance plus upcoming reservations occupies remaining places, with priority and room for missing categories. Covered plans wait for attendance. Cancellation/breach reopens places; ended records with unknown attendance outcomes pause new reservations.

Titles, categories, campuses, online/offline and conflicts all apply. Within selected categories, only explicit 【线上】 or 【线下】 prefixes at the start of a title determine the mode; “线上” elsewhere in a title is ignored. Missing markers pause new reservations with `activity_schema_unknown`. There is no independent Boolean field; naming changes require revalidation. All valid reservations block conflicting candidates, including touching endpoints. Existing overlaps are counted locally by attendance first, missing category, earlier finish, then ID; no school reservation is cancelled. Excluded records still block conflicts.

Missing categories precede configured category order, online lectures and earlier starts. Explicit wrong CAPTCHAs allow three replacement images after the initial one, then five-minute cooling. Pending state is saved before clicking Submit. Even visible success requires ID verification. Timeouts and unknown results never count as CAPTCHA rejection. Persistent uncertainty only queries and notifies once, without another submission or terminal Enter.

## Runtime diagnostics

`--check` shares activity validation and selection with normal scans. Activities with a valid, nonblank category outside the configured selection are first excluded as `category_not_allowed`, without requiring complete mode markers, locations, IDs or times. Their titles are left empty if missing; reservation windows are not validated and appear as `null`. Missing, non-string or blank categories still fail. Within selected categories, missing titles, locations, activity IDs or explicit online/offline markers, invalid lecture times, and invalid supplied reservation windows fail the check, including for unavailable activities. Personal reservation validation and conflict checks are unchanged. It prints `activity_details` without creating or changing tasks, using task cooldown records, opening reservation dialogs, running OCR or testing real submissions.

Normal scans save the latest per-activity results in private `state/task.json`. Use `uv run main.py --status` to inspect `selection_updated_at` and `activity_details`. Each entry contains the title, first matching selection reason, and school-provided reservation start/end in Beijing time (`null` when absent or not validated). A candidate still needs preflight and submission confirmation. Snapshots survive restarts and may remain old during failures, pending-result confirmation or attendance waits; they are not necessarily current school results. Activity details do not enter event logs or emails. Keep state files and terminal output containing details private.

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

`last_mail_error` retains the latest attempt's safe error classification across restarts and disabling mail. It becomes `none` when a new attempt starts or succeeds. Old failed records without a classification use `unknown` rather than guessing a cause.

`last_mail_event` identifies the latest runtime notification, and `last_mail_duration_seconds` records its actual attempt duration in seconds, on both success and failure. Both survive restarts. Unrecoverable legacy events use `unknown`, and no attempt uses `none`; missing or unfinished durations use `unknown`. Each completed attempt also writes a local `event=notification_finished mail_event=... duration_seconds=...` entry without personal data.

## Email notifications

Email is optional. Each user configures their own sending account; no shared notification backend is needed. Never share app passwords. Unset/empty mail fields disable email; `SMTP_PORT=465` alone also means disabled. Partial or invalid configuration stops startup.

QQ, 163, 126 and Gmail need only `SMTP_USERNAME` and `SMTP_PASSWORD`. Full creation and setup steps are in the [README configuration section](../README.en.md#2-configure-account-campus-and-email). QQ, 163 and 126 use an authorization code/password generated after enabling SMTP. Gmail uses a 16-character app password created after enabling 2-Step Verification, omitting grouping spaces. Use the full sending address as the username and the authorization code/app password as the password; do not use a web-login password or SMS code. Gmail app passwords are shown once; generate a replacement if lost or after changing the Google login password. Stop the old instance, verify with `uv run main.py --test-mail` and confirm inbox delivery before resuming reservations.

If App passwords is unavailable, check that the correct account is signed in and 2-Step Verification is enabled. Security-key-only verification, organizational restrictions or Advanced Protection may prevent access; see [Google's official explanation](https://support.google.com/accounts/answer/185833). Use another sender supporting SMTP SSL/TLS or clear the mail settings to disable notifications when unavailable.

Messages go to yourself by default. Optional `MAIL_TO` selects one recipient, including another provider. An empty `SMTP_HOST` maps `qq.com`, `163.com`, `126.com` and `gmail.com` to `smtp.qq.com`, `smtp.163.com`, `smtp.126.com` and `smtp.gmail.com`, ignoring domain case. Other domains/aliases require an explicit host. Explicit host and port settings take precedence; the default port is 465. Clear or update the old host when switching accounts. Only one sender is used, with no automatic rotation. `MAIL_FROM` defaults to the sending account, and overrides must be allowed by the provider. Certificate-verified `SMTP_SSL` and unauthenticated TLS relays are supported; STARTTLS, plaintext SMTP and Outlook.com's OAuth requirements are not. Changing providers does not guarantee SMTP connectivity on campus Wi-Fi or through Clash; test each route separately.

Single success, completed goals, required authentication, uncertain results and catchable failures produce local events and optional email. Three consecutive query/processing failures notify once, resetting after recovery. Normal scans stay quiet. Email includes a Chinese explanation and suggested action, plus the latest verified attended/planned counts, category gaps, data timestamps, consecutive failures, safe business error codes and the next planned check. Reservation-success mail uses progress verified in that round. Missing data or plans are explicitly unknown/not scheduled. School credentials, titles, full personal records and tickets are excluded.

Authentication-required, pending-reservation and consecutive-query-failure alerts are saved before sending. Each unresolved issue gets one attempt across restarts, with no automatic resend after failure or an uncertain outcome. Successful authentication, confirmation of the original reservation or full query recovery clears the corresponding alert. Disabled email does not consume new persistent alert attempts; read-only checks do not change alert history.

After a consecutive-failure alert, the first fully successful query/processing round for the current mode records `query_recovered` and attempts one “查询已恢复” message, including for an alert saved before a restart. Login or partial reads alone do not count. Pending-result mode only needs a successful check of the original reservation; recovery does not establish reservation success. Fewer than three failures or no recorded alert means no recovery mail. Failed recovery messages are not retried.

When queries repeatedly recover and fail again, consecutive query alerts are at least 15 minutes apart. A continuing incident still produces only one alert. A new failure that starts during cooldown and continues past its end is reported on a subsequent failed check. The interval survives restarts and does not delay school queries/backoff or limit authentication and pending-reservation alerts.

With email enabled, the running program reports attendance, upcoming reservations, missing categories (including planned coverage), progress timestamp, latest successful query and pending issues at 20:00 Asia/Shanghai each day. Waiting and backoff wake for email without making early school requests. Page operations or SMTP waits may delay the report. Query failures retain the latest verified progress with its timestamp; unavailable data is marked unknown, never zero. Progress not yet rebuilt after restarting a pending submission is also unknown.

There is at most one report attempt per day per state directory, saved before SMTP. Starting after 20:00 sends the day's report at the first wait, without catching up earlier days. Disabled email, read-only checks, stopped programs and completed tasks send no further daily reports. Failed reports and other notifications are not retried automatically. Sending remains synchronous on the main thread, with a new connection and authentication per message. The 20-second network-operation timeout is not a total message deadline. Use the recorded duration to determine whether a sending thread is needed; this change adds no background queue or catch-up jobs.

Mail failure records `event=notification_failed reason=<code>` without resending, changing reservation results or repeating bookings. SMTP acceptance does not prove inbox delivery. Forced termination, power loss or an unavailable mail service cannot guarantee notifications.

`--test-mail` and runtime notifications share these fixed classifications without raw exceptions, email addresses, SMTP response text or credentials. `--test-mail` displays its classification directly without writing task state.

| Code | Meaning |
| --- | --- |
| `dns_failed` | SMTP name resolution failed |
| `connection_failed` | Connection refused, interrupted or closed by SMTP; this does not prove the message was unaccepted |
| `tls_failed` | TLS handshake, certificate or encrypted-connection error, including EOF caused by an early close; not necessarily a certificate error |
| `timeout` | Network operation timed out; this classification alone does not locate the TCP, TLS or later SMTP stage |
| `authentication_failed` | SMTP authentication rejected |
| `sender_refused`, `recipient_refused` | Sender or recipient rejected |
| `message_rejected` | SMTP rejected the message submission |
| `smtp_failed`, `network_failed` | Other SMTP protocol or operating-system network error |
| `unknown` | Unrecognized exception or old failed record without classification |

### SMTP, HTTP and HTTPS

SMTP submits and forwards email; HTTP accesses websites and APIs; HTTPS protects HTTP with TLS encryption and server authentication. SMTP can also use TLS, so SMTP does not imply plaintext transport.

| Protocol or connection | Purpose | Common ports and encryption |
| --- | --- | --- |
| SMTP | Email submission and forwarding | 25 commonly carries mail between servers; 465 uses TLS from connection start; 587 typically upgrades with STARTTLS |
| HTTP | Websites and APIs | 80; the protocol itself does not encrypt traffic |
| HTTPS | Websites and APIs | 443; encrypted with TLS |

The current script submits mail to Gmail's SMTP server using `SMTP_SSL`. The Gmail API instead submits it to Google over HTTPS, after which Gmail still sends the message. These are separate entry points: unavailable SMTP ports do not establish an unavailable HTTPS API. Gmail SMTP currently uses an app password; the API requires OAuth authorization and cannot simply reuse `SMTP_PASSWORD`. See [Google SMTP settings](https://support.google.com/a/answer/176600?hl=en), the [Gmail API send method](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send) and [Python SMTP_SSL](https://docs.python.org/3.11/library/smtplib.html#smtplib.SMTP_SSL).

### Gmail connection troubleshooting

Stop the running instance and remove grouping spaces from the Gmail app password. `uv run main.py --test-mail` performs real authentication and attempts delivery; use anonymous DNS, TCP, TLS and SMTP greeting checks first when only diagnosing connectivity. Follow the `reason` classification; old logs containing only `notification_failed` cannot identify the cause. For `tls_failed`, check the SMTP host, port, routing rules and node support before blaming the password. A proxy can accept the local connection, fail upstream and close it, leaving the client with EOF during TLS; correlate this with proxy logs.

TUN may already capture the connection. Check the actual core mode, TUN state and connection logs: closing a window may leave the core running, and UI or disk configuration may differ from active state. Record original settings before temporary network changes, then restore and verify them. Direct connections can still time out after the proxy fully exits; that alone establishes neither a proxy defect nor a DNS error. Resolution may succeed while TCP to the returned IP fails; even after TCP succeeds, TLS or later SMTP operations can time out.

SMTP connections do not automatically use `HTTP_PROXY`, `HTTPS_PROXY` or `ALL_PROXY`; an SSH reverse-forwarded proxy port does not automatically capture mail traffic either. Successful server email alone therefore does not prove it used the local proxy. To distinguish DNS from proxy-path failures, compare direct and proxied handshakes to the same destination IP and port without authentication or sending mail, retaining the SMTP hostname for TLS SNI and certificate verification. A Fake-IP address alone does not establish a DNS error; if the real IP still fails through the proxy, adding a backup IP alone cannot fix that path.

HTTPS on port 443 proves only that HTTPS path works, not SMTP on 465/587. Machines can have different exits, DNS answers and ISP routes; a successful handshake also does not establish sustained availability. Do not obscure an undiagnosed problem by disabling certificate verification, only increasing timeouts or only pinning an IP. The current code does not support STARTTLS: setting `SMTP_PORT=587` alone does not change the protocol.

### Alternative sending paths

| Path | Current support and tradeoffs |
| --- | --- |
| Another sending provider, with Gmail receiving | Existing configuration supports another provider's `SMTP_SSL` account with `MAIL_TO` pointing to Gmail; verify that SMTP path and actual delivery first |
| Run the project on an existing server | Existing deployment path; reuse a verified server exit without local forwarding |
| Forward local SMTP through SSH to a server, then to Gmail | Candidate, not integrated; separate the local connection endpoint from the TLS identity `smtp.gmail.com` rather than simply setting `SMTP_HOST=127.0.0.1`; requires a live tunnel |
| Gmail API over HTTPS 443 | Candidate, not implemented; retains the Gmail sender but requires API setup, OAuth/token refresh and sending-code changes; `gmail.send` is sufficient without mailbox-read permission |
| Another network or an SMTP-capable proxy exit | Start with anonymous handshake comparisons; working HTTPS or low node latency does not establish SMTP availability, and actual delivery still needs verification |

Consider the Gmail API when the sender must remain Gmail without relying on your own server. If only receipt in Gmail matters, another reachable SMTP sender usually needs fewer changes. These options do not introduce API, tunnel or automatic fallback-IP configuration in this project. See [OpenSSH local forwarding](https://man.openbsd.org/ssh#L), [Google desktop-app OAuth](https://developers.google.com/identity/protocols/oauth2/native-app) and [Gmail API scopes](https://developers.google.com/workspace/gmail/api/auth/scopes).

See the current [notification requirements](notification-requirements.md) (Chinese).

## Server setup

The [README](../README.en.md#1-install) contains the complete tool installation, browser setup, account/email configuration and checks. The server path targets Ubuntu 24.04 using an existing account with sudo or root access. The project uses Python 3.11.

Install the browser with `uv run playwright install chromium`. On Ubuntu, use `uv run playwright install --with-deps chromium` to prepare system libraries too. Use the same account for installation and operation to keep browser caches consistent. If only system libraries are missing, use `uv run playwright install-deps chromium`.

Playwright stores browsers in its user cache. The default install also downloads a headless shell; this project uses full Chromium in both modes. Initial downloads need internet access. Reinstall after updating Playwright; startup never downloads browsers automatically. See [Playwright's browser documentation](https://playwright.dev/python/docs/browsers).

Headless mode needs no desktop; windowed mode needs a graphical environment. Add `--headless` to server checks and reservations. After installing uv, follow its PATH instructions or reconnect over SSH.

## Background operation and recovery

Complete commands for starting a system-level transient systemd service, inspecting logs, stopping and migrating old instances are in the [README's Ubuntu background section](../README.en.md#ubuntu-background-operation). The default directory is `state/`; adjust log paths when using a custom state directory. Create the service as the account used to install dependencies and browsers. The startup command fixes the working directory and uv path; the service reads the project's `.env` rather than inheriting configuration or proxy variables exported only in SSH.

`nohup` is no longer recommended: Python ignoring SIGHUP does not prevent the Playwright driver from handling that signal and closing Chromium. During the 2026-10-18 incident, SSH logout and Chromium exit occurred in the same second. Offline comparisons reproduced the surviving parent and closed browser; a detached session was unaffected by the original process group's hangup. A system-level transient service starts under systemd, detaching the whole runtime process tree from SSH without `--user`, `--scope`, `--pty` or `--pipe`. It uses `Restart=no` and no boot startup. Restart manually after a server reboot, program exit or authentication stop.

`uv run main.py --status` distinguishes task state from the current process. `scanning/pending/done` alone does not establish health: inspect `process_running`, `phase`, successful-query timestamps and errors. `manual_required` means blocked authentication. After stopping, `phase=stopped` and `last_phase` preserves the previous phase. `runner.log` holds terminal output and `events.log` holds events. Logs keep growing; maintain them according to disk usage.

Stop with `sudo systemctl stop seu-lecture-reserve.service`, allowing up to 60 seconds for cleanup before forced termination; do not signal service processes individually. `--collect` unloads stopped or failed transient services, so `systemctl status` may no longer find them, but `state/runner.log`, `events.log` and task state remain available. To stop an old `nohup` instance, follow the README's PID, command and working-directory checks to avoid signaling an unrelated process. Always wait for `process_running=false` before restarting.

Locks cover one state directory only. Run one instance per account across all machines and both projects; stop the old instance before switching machines. Keep the original state directory to restore pending results, cooldowns and backoff. Never delete state to bypass pending-result protection. A new machine needs no state transfer to read school records, but submission deduplication across machines is not guaranteed.

## Network and authentication

Initial login starts with DNS. Only unrecovered VPN main-frame `ERR_NAME_NOT_RESOLVED`, `ERR_CONNECTION_CLOSED` or `ERR_CONNECTION_RESET` permits one backup-IP restart. Ordinary timeouts, certificate/credential errors, other domains and subresources do not. Business operations never switch IPs automatically. Domain certificate checks remain enabled; system DNS/Clash is unchanged. Remote-resolving proxies may ignore the mapping.

Legacy school HTTP callbacks receive a local browser 307 to HTTPS on the same host; the original HTTP request is never sent, while nested service identifiers remain unchanged. Other HTTP requests are blocked. Credentials are filled only on trusted school HTTPS origins. Diagnostics omit raw Playwright logs; authentication HTML/screenshots are not automatically saved.

`host=<unknown>` means the request domain is outside the three school domains allowed in diagnostics, not a DNS-resolution failure. Confirmed Sangfor local-client probe failures produce one notice per browser launch: only non-navigation HTTPS XHR requests to `127.0.0.1` on ports `54630/54641/54652` with `ERR_CONNECTION_REFUSED`, or to `localhost.sangfor.com.cn` on ports `54631/54642/54653` with `ERR_ABORTED` or `ERR_CONNECTION_REFUSED`, qualify. Later reloads in the same browser do not repeat the notice. Other requests, ports and errors (including certificate errors) remain individually logged. This notice does not establish a school login or query failure.

Neither a failed subresource nor successful login establishes a working query round. For blank/loading pages, `page_not_ready` or `history_navigation_failed`, stop with `Ctrl+C`, keep `state/`, inspect browser errors and manually verify page loading and My Activities / All navigation, then check proxy logs. Use the template's 15-second element wait for slow loading; longer timeouts alone cannot fix persistent connection failures or incompatible page structure. After changes, run `uv run main.py --check` and require `event=read_only_complete` before resuming reservations; test email separately.

Expired sessions first try login again. Incomplete authentication preserves the task, stops business actions and optionally emails. SMS sending/input and remote desktop are not implemented. Automatic operation depends on the school not requiring human intervention.

A closed page or disconnected browser records `event=browser_closed`, saves `last_error=browser_closed` and `last_phase=failed`, optionally sends `task_failed`, and exits instead of entering ordinary network backoff. If this happens during submission, the original activity ID and `pending` state remain; restarting queries that reservation before any further submission. Ordinary loading, connection and data-validation errors retain existing backoff. Setting only `handle_sighup=False` did not keep the driver and browser alive in local hangup comparisons; isolate the whole runtime process tree instead.

## Development and acceptance

2026-10-19 SMTP provider update: all 105 offline tests passed, covering QQ/163/126/Gmail host selection, domain case, explicit host/port precedence, unknown-domain rejection, temporary `.env` loading and disabled template defaults. Bilingual tutorials and field comments are synchronized. Tests did not visit the university, read the real `.env` or send email. Actual delivery for each provider on campus Wi-Fi, a hotspot and Clash remains unverified; see the user-reported network comparison in [notification requirements (Chinese)](notification-requirements.md#smtp-多邮箱方案确认2026-10-19).

Gmail network diagnosis on 2026-10-19 (specific to this environment and sampling times): HTTPS controls succeeded on three proxy nodes, while fixed-IP Gmail 465 handshakes all ended with TLS EOF and port 587 closed before the SMTP greeting. Local direct tests both succeeded and reproduced a 20-second TCP timeout after successful resolution, plus a separate TLS timeout. This does not establish a DNS error or the precise blocking point. Native server handshakes succeeded, while forcing traffic back through the reverse-forwarded local proxy failed; successful server email does not prove use of that proxy port. Switching TUN to Mixed retained working HTTPS and failing SMTP, so the workaround in the related [GitHub report](https://github.com/clash-verge-rev/clash-verge-rev/issues/7644#issuecomment-5149144851) was not adopted as a fix here. An anonymous Gmail API HTTPS request returned the expected `401`, establishing endpoint reachability only, not authorization or delivery. One authorized `--test-mail` invocation failed while establishing the connection, before authentication or message submission; the other diagnostics neither authenticated nor sent mail. Temporary network settings were restored and verified; no implementation or candidate path was enabled. Stable local delivery remains unresolved.

Probe logging and category filtering fixes on 2026-10-19: all 102 offline tests passed, covering exclusion of incomplete activities outside selected categories, continued rejection of invalid selected activities and personal records, merged Sangfor probes and preserved other network errors. A real headless read-only check passed on Windows. Linux validation loaded the fixed sources only in memory, merging the original 12 probe failures into one notice without changing deployed files. Both checks excluded one system-test activity, identified six activities whose reservation windows had not opened, and returned `read_only_complete`. No reservations or emails were sent.

SSH hangup and disconnect fixes on 2026-10-18: all 98 offline tests passed under Linux Xvfb, adding closed-page, closure-during-refresh, browser-disconnect, immediate exit/alert, read-only error classification and pending-reservation recovery checks. Bilingual startup commands, Bash syntax, local link targets, lockfile and installed dependency compatibility passed. With the README's service parameters, a temporary directory and synthetic local pages, the test service ran in `system.slice` with `Restart=no` and a 0600 log; Chromium page heartbeats continued after SIGHUP to the launcher session. The test service was removed. The real background instance was not migrated; no school access or email occurred. Actual SSH disconnection, reservations and long-running operation remain unverified.

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

Mail-notification improvements on 2026-10-18: important messages share progress and safe error context, alerts deduplicate and recover across restarts, query alerts are at least 15 minutes apart, and status records the latest mail event and actual duration. All 93 offline tests passed under Linux Xvfb, covering continuing failures after cooldown, disabled mail preserving alert attempts, legacy state and no resend after failure. Installed dependency compatibility passed. No school access or real mail occurred; the process remains stopped. The actual impact of synchronous SMTP on scans still needs runtime measurements.

Goal, state and email code comes from the maintainer's HTTPS project at `96b9c5c`. Repositories have no runtime dependency and the source is unchanged. Chinese documentation: [requirements](browser-upgrade-requirements.md), [README and deployment conventions](readme-deployment-requirements.md), [ADR 0001](adr/0001-browser-only-reservations.md), [glossary](../GLOSSARY.md), [historical assessment](design-assessment.md), [historical network specification](network-recovery-requirements.md).
