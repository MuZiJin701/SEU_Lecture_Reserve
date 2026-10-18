# SEU Lecture Auto Reservation

[中文](README.md)

Use Chromium to find lectures, read image CAPTCHAs, reserve places and verify results. The goal is **8 attended series lectures, including at least one each in law, art and mental health**. Salons are excluded. When upcoming reservations cover the plan, the program waits for attendance and exits once the goal is met.

Follow installation, configuration and checks in order, then choose local or server operation.

## 1. Install

**Windows locally**: install [Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/getting-started/installation/), then reopen PowerShell.

**Ubuntu 24.04 server**: connect over SSH using an existing account with sudo or root access. When running as root, omit `sudo` from the two apt commands below. Skip tools already installed:

```bash
sudo apt update
sudo apt install git curl nano
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
```

Download the project and prepare Python 3.11 and dependencies. These commands place it in your home directory; enter the existing directory if already installed:

```shell
cd ~
git clone https://github.com/MuZiJin701/SEU_Lecture_Reserve.git
cd SEU_Lecture_Reserve
uv sync
```

Install the project's browser:

- Windows: `uv run playwright install chromium`
- Ubuntu: `uv run playwright install --with-deps chromium`

Ubuntu may request your sudo password for system libraries. Use the same account for installation and operation. The first download needs internet access. Rerun browser installation after updating Playwright.

## 2. Configure account, campus and email

For first-time setup, copy `.env.example` to `.env` in the same directory. Keep any existing file.

On Windows, copy it in File Explorer and open it in a text editor. On Ubuntu:

```bash
cp -n .env.example .env
chmod 600 .env
nano .env
```

In nano, press `Ctrl+O`, then Enter to save, and `Ctrl+X` to exit.

Edit these values in `.env`:

```dotenv
SEU_CARD_NUMBER="your-card-number"
SEU_PASSWORD='your-password'
SEU_PREFERRED_CAMPUS='[]'

# Email is optional; leave empty to disable
SMTP_USERNAME=
SMTP_PASSWORD=
```

The empty campus list selects only online lectures. To include in-person lectures, enter exact university campus names, for example `'["无锡校区"]'`.

The template has Chinese comments and presets `SEU_TIMEOUT_ELEMENT_WAIT=15` and `SEU_TIMEOUT_LOGIN_REDIRECT=60` for slow networks, keeping the scan interval at 10 seconds. Merge these settings manually into an existing `.env`; template updates do not apply automatically, and existing credentials should be preserved. Without configuration, the two built-in waits remain 3 and 30 seconds. Longer waits cannot fix disconnections, blank pages or blocked authentication; see [network troubleshooting](docs/usage.en.md#network-and-authentication).

Each user supplies their own sending account. **To obtain Gmail's `SMTP_PASSWORD`:**

1. Sign in to the sending [Google Account](https://myaccount.google.com/security). Open Security & sign-in, find How you sign in to Google, and enable 2-Step Verification by following the prompts.
2. Open [App passwords](https://myaccount.google.com/apppasswords), signing in again if requested. Create a password for this project; you can name the app `SEU Lecture Reserve`.
3. Copy the generated **16 characters**, omitting display grouping spaces, into `.env` as `SMTP_PASSWORD`. Set `SMTP_USERNAME` to the same account's full Gmail address. Replace both placeholders below:

```dotenv
SMTP_USERNAME=your-address@gmail.com
SMTP_PASSWORD='your-app-password'
```

4. Save `.env` and stop any running instance. Complete the checks and test email in the next section, confirm inbox delivery, then start or resume reservations.

The app password is shown once; generate another if lost. Changing your Google login password revokes app passwords, so generate a replacement and update `.env`. If the option is unavailable, see [Google's app-password guide](https://support.google.com/accounts/answer/185833). Use the app password for `SMTP_PASSWORD`, rather than your login password or an SMS code.

Messages go to yourself by default. Add `MAIL_TO=recipient@example.com` to use another recipient. See [email settings](docs/usage.en.md#email-notifications) for other senders.

Mail fields in the template are empty; `SMTP_PORT=465` alone keeps notifications disabled. Only `SMTP_SSL` is supported: do not simply switch to port 587 requiring STARTTLS. If the test fails, follow [email troubleshooting](docs/usage.en.md#email-notifications) to check configuration and SMTP connectivity.

Email covers important events and a daily progress report at **20:00 Asia/Shanghai** while running. Reports stop with the program, with at most one attempt per day. Restart after configuration changes; process environment variables override `.env`.

Three consecutive query/processing failures trigger one alert, deduplicated across restarts; recovery triggers one “查询已恢复” message. Query alerts are at least 15 minutes apart when failures repeatedly clear and return. Sending failures show a safe classification such as `event=notification_failed reason=tls_failed`. `uv run main.py --status` retains the latest attempt's classification in `last_mail_error`, distinguishing network, TLS and authentication failures without raw exceptions. Status also shows `last_mail_event` and `last_mail_duration_seconds`. Important notifications include the latest verified progress, safe error context and the next planned check; missing data is explicitly unknown. See [email notifications](docs/usage.en.md#email-notifications) for the full rules.

## 3. Check before starting

Check login and lecture data first, **without reservations or email**:

- Windows locally: `uv run main.py --check`
- A server without a desktop: `uv run main.py --check --headless`

Read-only checks use the same activity validation and filters as normal operation, and show each activity’s reason and reservation window. Missing explicit 【线上】/【线下】 title prefixes or required fields fail the check. Continue after `event=read_only_complete`. If email is configured, send one test message and check your inbox:

```shell
uv run main.py --test-mail
```

This sends real email; skip it when mail is disabled. Resolve any required manual authentication first. Email cannot complete school login.

## 4. Run, inspect and stop

**Normal startup submits real reservations. Run only one instance per account across all machines and both projects.**

### Windows local operation

From the project directory, show the browser window:

```shell
uv run main.py
```

Add `--headless` to hide the window. Press `Ctrl+C` to stop; existing reservations stay in place.

### Ubuntu background operation

In the project directory, first run `uv run main.py --status`. Confirm `process_running=false` and that no other machine is running the same account, then start:

```bash
mkdir -p state
chmod 700 state
nohup uv run main.py --headless >> state/runner.log 2>&1 < /dev/null &
echo $! > state/runner.pid
```

This saves the process ID and appends output to a log. Inspect it with:

```bash
uv run main.py --status
tail -f state/runner.log
```

`--status` shows the latest per-activity reasons and reservation windows in `activity_details`; check `selection_updated_at` for freshness. For example, `reservation_not_started` means booking has not opened. The latest mail time and outcome survive restarts. See [runtime diagnostics](docs/usage.en.md#runtime-diagnostics) for all reasons.

Confirm `process_running=true` and an updated `last_query_at` before disconnecting SSH. Here, `Ctrl+C` ends log viewing without stopping reservations. Reconnect using the same account, then run `cd ~/SEU_Lecture_Reserve` and use the same status and log commands.

Before stopping, check the saved process ID, command and working directory:

```bash
reserve_pid=$(cat state/runner.pid)
ps -p "$reserve_pid" -o pid,args
readlink "/proc/$reserve_pid/cwd"
```

**Only after confirming this project's process**, run:

```bash
kill "$reserve_pid"
uv run main.py --status
```

Wait for `process_running=false` before restarting. Do not send `kill` if the PID is stale or belongs to another process. Keep `state/` and repeat the background startup commands to resume. Server restarts, program exits and authentication stops all require manual startup.

## Rules and limits

- Missing required categories take priority. Titles, campuses, online/in-person settings and time constraints all apply; touching endpoints count as conflicts.
- The default wait between rounds is 10 seconds. Unknown submission results pause other submissions while the original activity is checked. Do not delete state to bypass this protection.
- `nohup` keeps the process running after terminal disconnection; it provides no crash recovery or boot startup. If the server cleans up processes on logout, verify continued operation and successful queries after an actual SSH disconnect.
- Keep `.env`, `state/` and authentication data private. University records determine reservations and attendance. Complete historical coverage remains unproven.
- Headless Chromium on Linux has completed real login and read-only queries. Windows Chromium login, actual reservations, real CAPTCHA recognition and at least 24 hours of operation remain unverified. See [configuration](docs/usage.en.md#configuration) when upgrading from an older version.

[Full configuration and troubleshooting](docs/usage.en.md) · [Requirements](docs/browser-upgrade-requirements.md) (Chinese) · [Independent HTTPS project](https://github.com/MuZiJin701/seu-lecture-reserve-http)

Maintained by [MuZiJin701](https://github.com/MuZiJin701), based on [ApricityWang's original project](https://github.com/ApricityWang/SEU_Lecture_Reserve), retaining original and historical attribution. Goal, state and email logic comes from the maintainer's HTTPS project.
