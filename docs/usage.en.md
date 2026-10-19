# Configuration and Troubleshooting

[Back to README](../README.en.md) · [中文](usage.md)

Use the README for first-time installation and background startup. This page covers configuration, status and troubleshooting. Business constraints and outstanding validation are in the [browser specification](browser-upgrade-requirements.md) (Chinese).

## Command reference

| Command | Purpose |
| --- | --- |
| `uv run main.py` | Start or resume real reservations, showing the browser by default |
| `uv run main.py --headless` | Run without a window; also works with `--check` |
| `uv run main.py --check` | Log in and validate personal records and lectures; no submissions, email or task creation/changes |
| `uv run main.py --status` | Inspect local status and process lock; no browser or university credentials required |
| `uv run main.py --test-mail` | Send one real test email; no university login or task creation |
| `uv run main.py --new-task` | Compatibility option to recheck a completed goal; does not reset active or unconfirmed tasks |

Normal startup always checks university progress, even after local completion; `--new-task` is unnecessary. `--check` does not open reservation dialogs or validate OCR or real submissions. `captcha_ocr.py` collects CAPTCHA samples and also shows a window by default, with optional `--headless`; `captcha_fetch.py` is for offline evaluation.

## Configuration

The project loads its root `.env`; process environment variables take precedence. Restart after changes. Merge only needed settings and preserve credentials. See the commented [.env.example](../.env.example).

| Environment variable | Meaning and default |
| --- | --- |
| `SEU_CARD_NUMBER`, `SEU_PASSWORD` | University credentials; required for reservations and read-only checks |
| `SEU_PREFERRED_LECTURES` | Exact title array; default `[]` allows all titles, with other filters still applied |
| `SEU_REQUIRED_CATEGORIES` | Candidate categories and order: mental health, law, art, other; nonempty and unique; salons excluded |
| `SEU_PREFERRED_CAMPUS` | In-person campus allowlist; default `[]` excludes in-person lectures |
| `SEU_ENABLE_OFFLINE`, `SEU_ENABLE_ONLINE` | In-person/online switches; both default to `true` |
| `SEU_STATE_DIR` | Private state directory; defaults to `state` under the project, or an absolute path |
| `SEU_VPN_IP` | Initial-login fallback IPv4/IPv6; empty in code, historical `121.249.14.2` in the template |
| `SEU_TIMEOUT_PAGE_LOAD` | Extra wait after login navigation; default 0.5 seconds |
| `SEU_TIMEOUT_ELEMENT_WAIT` | Page, data, action and displayed-result timeout; 3 seconds in code, 15 in the template |
| `SEU_TIMEOUT_LOGIN_REDIRECT` | Authentication redirect timeout; 30 seconds in code, 60 in the template |
| `SEU_TIMEOUT_SCAN_INTERVAL` | Normal scan and unconfirmed-result query interval; default 10 seconds, must be positive |
| `SEU_TIMEOUT_ACTION_CONFIRM` | Base wait after submission; default 0.2 seconds, followed by activity-ID verification |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Full sending address and authorization code/app password |
| `SMTP_HOST`, `SMTP_PORT` | Host can be inferred from the email domain; default implicit TLS port 465 |
| `MAIL_FROM`, `MAIL_TO` | Sender and one recipient; defaults to sending to yourself |

Use single-quoted JSON arrays, such as `SEU_PREFERRED_CAMPUS='["无锡校区"]'`; switches accept only `true/false`. Single-quote passwords, especially those containing spaces or `#`. Times are finite, nonnegative seconds; zero Playwright timeouts become 1 millisecond rather than unlimited waits.

Legacy `SEU_HEADLESS` is ignored; the command line controls browser mode. `SEU_TIMEOUT_RETRY_DELAY` is read only for compatibility; business failures use backoff. An old 0.05-second scan setting does not update itself to 10 seconds. Update or clear stale fallback IPs; longer waits cannot fix disconnections or blocked authentication.

## Email setup

Use your own sending account, one at a time. Keep authorization codes private. Empty mail fields disable notifications; `SMTP_PORT=465` alone also keeps mail disabled. Incomplete attempted configuration prevents startup.

### Obtain a sending password

| Sender domain | Automatic host | `SMTP_PASSWORD` |
| --- | --- | --- |
| `qq.com` | `smtp.qq.com` | SMTP authorization code |
| `163.com` | `smtp.163.com` | SMTP authorization password |
| `126.com` | `smtp.126.com` | SMTP authorization password |
| `gmail.com` | `smtp.gmail.com` | App password |

**QQ**: sign in to [QQ Mail](https://mail.qq.com/), find SMTP/client services in Settings, enable the service and complete verification to generate an authorization code. Use your full QQ address and that code. See [Tencent's SMTP example](https://cloud.tencent.com/document/api/876/129350).

**163/126**: sign in to [163 Mail](https://mail.163.com/) or [126 Mail](https://mail.126.com/). Open Settings → POP3/SMTP/IMAP, enable SMTP and select “新增授权密码” (add authorization password). Complete verification, then use the full mailbox address and generated password. See [NetEase's authorization-password guide](https://help.mail.126.com/faqDetail.do?code=d7a5dc8471cd0c0e8b4b8f4f8e49998b374173cfe9171305fa1ce630d7f67ac286624f309a1a7089).

**Gmail**:

1. Sign in to [Google Account security settings](https://myaccount.google.com/security) and enable 2-Step Verification.
2. Open [App passwords](https://myaccount.google.com/apppasswords) and create one for this project, for example named `SEU Lecture Reserve`.
3. Copy the 16 characters without grouping spaces. Set the full Gmail address as the username and the generated password as `SMTP_PASSWORD`.

Gmail app passwords are shown once; generate a replacement if lost or after changing your Google login password. If the option is missing, check the account and 2-Step Verification settings. Organization restrictions, Advanced Protection or security-key-only verification may affect availability; see [Google's explanation](https://support.google.com/accounts/answer/185833). Use another sender or disable email if unavailable.

### Configure and test

```dotenv
SMTP_USERNAME=your-address@qq.com
SMTP_PASSWORD='your-authorization-code'
SMTP_HOST=
SMTP_PORT=465
MAIL_FROM=
MAIL_TO=
```

An empty `SMTP_HOST` uses the table's case-insensitive domain mapping; an explicit host takes precedence. Other domains, aliases or self-hosted mailboxes require a provider hostname without a URL scheme, port or path. Clear or update the old host when switching accounts. `MAIL_FROM` defaults to the sending account; overrides require provider permission. `MAIL_TO` defaults to yourself and can specify one other mailbox, such as `recipient@gmail.com`.

Save `.env`, stop the old instance, run `uv run main.py --test-mail` and confirm inbox delivery before resuming reservations. `event=test_mail_accepted` means only SMTP acceptance, not delivery. Test-mail errors appear in the terminal and do not update task state.

The implementation uses certificate-verified `SMTP_SSL`, default port 465, and also supports TLS relays without authentication. STARTTLS, plaintext SMTP and OAuth are unsupported; do not simply change the port to 587. Gmail API, webmail sending and SSH mail forwarding are not integrated.

### Notification rules

- Notifications cover a confirmed reservation, goal completion, manual authentication, unconfirmed submissions and catchable exits. Three consecutive query/processing failures trigger an alert; a complete recovery triggers one recovery notice. Normal polling is quiet.
- Unresolved authentication, submission and query alerts are deduplicated across restarts. Failed or uncertain sends are not automatically retried; disabled email does not consume new alert allowance. Query-failure alerts are at least 15 minutes apart, including across restarts.
- A daily report runs at 20:00 Asia/Shanghai, at most one attempt per state directory per day. Starting after 20:00 attempts today's report at the first wait, without catching up earlier dates. Page actions may delay sending; reports do not shorten business backoff or continue after stop/completion.
- Messages include the latest verified aggregate progress, data time, safe error codes and next-check plan. Missing data is marked unknown. Credentials, lecture details and full personal records are excluded. Query recovery while confirming a submission does not mean reservation success.
- Mail sends synchronously on the main thread, reconnecting and authenticating each time. The 20-second timeout applies to network operations, not total message duration. Mail failure does not change reservation results; use the duration field below to assess scan delays.

## Status and selection reasons

Run `uv run main.py --status`. It shows a local snapshot rather than current university records; some fields may stay unchanged during query failures or attendance waits.

| Field | Meaning |
| --- | --- |
| `process_running`, `phase` | Whether a process runs and its phase; after stopping, `last_phase` retains the previous phase |
| `last_query_at`, `last_error`, `failure_count` | Latest successful query, safe business error code and consecutive failure count |
| `next_check_at` | Next planned check time |
| `selection_updated_at`, `activity_details` | Latest selection time, per-activity title, first matching reason and reservation window; missing/unvalidated times are `null` |
| `mail_status`, `last_mail_status` | Current mail state and latest attempt; `accepted` is SMTP acceptance, `sending` uncertain, `failed` unsuccessful, `never` no record |
| `last_mail_at`, `last_mail_error` | Latest runtime mail attempt and error category; `none` on a new attempt/success, `unknown` for old failures without a category |
| `last_mail_event`, `last_mail_duration_seconds` | Latest runtime notification event and duration; duration is `unknown` for old or unfinished attempts |

Mail history survives restart and disabling email; lost historical evidence cannot be reconstructed. Task states `scanning/pending/done` alone do not prove health. Activity details stay in private state rather than event logs or mail; keep terminal output containing them private.

| Selection reason | Meaning |
| --- | --- |
| `candidate` | Passed filters; not yet a successful reservation |
| `reservation_not_started`, `capacity_full` | University marks booking as not open/full |
| `not_reservable` | No reservable marker; exact cause unknown |
| `already_reserved` | Already reserved in university records |
| `category_not_allowed`, `category_not_needed` | Outside configured categories/not currently needed |
| `title_not_selected`, `campus_not_selected` | Title/in-person campus mismatch |
| `online_disabled`, `offline_disabled` | Corresponding lecture mode disabled |
| `time_conflict`, `cooldown` | Conflict with a valid reservation/CAPTCHA cooldown |

## Troubleshooting

1. Use `--status` to inspect the process, query time and errors; read-only check output also helps. Stop the old instance and keep `state/`.
2. Follow the relevant case below, changing one setting at a time.
3. Run `uv run main.py --check` after fixing the problem; add `--headless` on servers. Wait for `read_only_complete` before real reservations. Test email separately with `--test-mail`.

### Login or page failures

If Chromium is missing, repeat the README's browser installation command. On Linux, `uv run playwright install-deps chromium` installs only missing runtime libraries. Browsers live in the installation account's cache; showing a window requires a graphical environment.

For blank/loading pages, `page_not_ready` or `history_navigation_failed`, check whether you can manually load the university site and switch to “我的活动／全部”, then inspect network and proxy logs. For slow pages, try the template's 15-second element and 60-second authentication waits. Disconnections or page structure changes cannot be fixed solely by longer timeouts.

`activity_schema_unknown` means a target-category record lacks required fields, valid times or an explicit 【线上】/【线下】 title prefix. New submissions pause; the program does not infer lecture mode from the title body. Explicitly non-target categories can be excluded first; personal records remain fully validated.

Initial login uses normal DNS first. Only a failed login with VPN main-frame `ERR_NAME_NOT_RESOLVED`, `ERR_CONNECTION_CLOSED` or `ERR_CONNECTION_RESET` can restart once using `SEU_VPN_IP`. Ordinary timeouts, certificate/credential errors and other resources do not trigger fallback; later business activity does not switch IPs. System DNS and Clash remain unchanged; remote proxy resolution may ignore the mapping.

`host=<unknown>` only means the host is outside the university log allowlist. Sangfor local-client probe failures are summarized and do not establish university query failure. Expired sessions may attempt login again. Blocked manual authentication preserves the task and exits; SMS sending/input and remote desktops are unsupported.

`browser_closed` means browser disconnection or page closure. The task is preserved, an optional alert is attempted, and the program exits. A submission in progress keeps `pending` for verification after restart. Use the README's systemd setup on servers; ignoring hangups in Python alone does not protect the browser process tree.

### Email failures

| `reason` / `last_mail_error` | What to check |
| --- | --- |
| `dns_failed` | SMTP hostname resolution |
| `connection_failed`, `network_failed` | Host, port and route; disconnection does not prove the message was not accepted |
| `tls_failed` | Port, certificates, proxy and upstream; includes EOF and does not imply a wrong password |
| `timeout` | A network operation timed out; this alone cannot identify TCP, TLS or SMTP stage |
| `authentication_failed` | Account and authorization code/app password |
| `sender_refused`, `recipient_refused`, `message_rejected` | Addresses, provider permissions and content restrictions |
| `smtp_failed`, `unknown` | Other protocol errors or missing classification; do not infer causes from old logs |

Working HTTPS pages do not prove SMTP access. Test on the actual runtime network, comparing campus Wi-Fi, a hotspot and proxy settings if needed. Switching providers does not guarantee a working route. SMTP does not automatically read `HTTP_PROXY`, `HTTPS_PROXY` or `ALL_PROXY`; TUN can still intercept connections.

To isolate failures, start with anonymous DNS, TCP, TLS and SMTP-greeting checks without authentication or sending. When comparing routes to the same IP, retain the SMTP domain's TLS identity and certificate validation. Inspect the running proxy and logs: closing its window may leave the core active, and Fake-IP alone does not prove DNS failure. Restore temporary network changes; keep certificate verification enabled.

### Old background instances and recovery

For an old `nohup` instance, first inspect the PID, command and working directory:

```bash
reserve_pid=$(cat state/runner.pid)
ps -p "$reserve_pid" -o pid,args
readlink "/proc/$reserve_pid/cwd"
```

Run `kill "$reserve_pid"` only after confirming this project's process. Do not terminate stale or unrelated PIDs. Then confirm `process_running=false` with `uv run main.py --status`, keep state, complete a read-only check and start systemd using the README.

Locks cover only the same state directory. Stop the old instance before changing machines; a new machine can read university records without migrating state, but cross-machine submission deduplication is not guaranteed. Local recovery should retain pending submissions, cooldowns and backoff. `runner.log` and `events.log` keep growing, so monitor disk space. Stopping systemd allows up to 60 seconds for cleanup before forced termination.

## Development checks

```shell
uv sync --locked
uv run playwright install chromium
uv run --locked python -m unittest discover -s tests -v
```

On Linux, install browser libraries as described in the README. For configuration only, run `uv run --locked python -m unittest discover -s tests -p test_config.py -v`. Tests use temporary configuration and local constructed pages with external requests blocked; they do not read the real `.env`. Imports do not start business activity. Do not launch reservation or sample-collection entry points just to check documentation.

[Glossary](../GLOSSARY.md) · [Architecture decision](adr/0001-browser-only-reservations.md) · [Specification and validation limits](browser-upgrade-requirements.md) (Chinese)
