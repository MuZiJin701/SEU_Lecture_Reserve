# SEU Lecture Auto Reservation

[中文](README.md)

Use a browser to find lectures, read image CAPTCHAs, reserve places and verify results. The program's goal is **8 attended series lectures or SEU Coffee Salon activities, including at least one each in law, art and mental health**. Test activities and ticket announcements do not count and are excluded from automatic reservations; university recognition follows university rules. Once reservations cover the plan, the program waits for attendance and exits when the goal is met.

![Read-only check, test email and headless startup example](docs/images/使用截图.png)

The screenshot shows a completed read-only check, SMTP acceptance of a test email, and successful headless login.

For first-time setup, follow these steps in order. Run all project commands inside the `seu_lecture_reserve` folder; existing checkouts can keep their original folder names.

## 1. Install

**Windows**: install [Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/getting-started/installation/), then reopen PowerShell.

**Ubuntu 24.04 server**: connect over SSH with an account that has sudo access and install the tools. Omit `sudo` when running as root. Skip tools already installed.

```bash
sudo apt update
sudo apt install git curl nano
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
```

On either system, download the project and prepare Python 3.11 and dependencies. If already installed, enter the existing folder instead.

```shell
cd ~
git clone https://github.com/MuZiJin701/seu_lecture_reserve.git
cd seu_lecture_reserve
uv sync --locked
```

Install the project's Chromium browser. Continue after installation succeeds:

- Windows: `uv run playwright install chromium`
- Ubuntu: `uv run playwright install --with-deps chromium`; this may request your sudo password.

Use the same account for installation and operation. The first download needs internet access; reinstall the browser after updating Playwright.

## 2. Configure

For first-time setup, copy `.env.example` to `.env` in the same folder. **If `.env` already exists, skip copying and edit it directly to preserve your credentials.**

On Windows, run in PowerShell:

```powershell
Copy-Item .env.example .env
notepad .env
```

On Ubuntu:

```bash
cp -n .env.example .env
chmod 600 .env
nano .env
```

In nano, press `Ctrl+O`, then Enter to save, and `Ctrl+X` to exit. Enter your university credentials and choose campuses as needed:

```dotenv
SEU_CARD_NUMBER="your-card-number"
SEU_PASSWORD='your-password'
SEU_PREFERRED_CAMPUS='[]'
```

An empty campus list selects only online lectures. To include in-person lectures, use exact university campus names, such as `'["无锡校区"]'`; online lectures remain enabled. See [configuration](docs/usage.en.md#configuration) for other filters and timeouts.

Email is optional; leave the template's mail fields empty to disable it. To enable it, enter your full sending address and authorization code, for example:

```dotenv
SMTP_USERNAME=your-address@qq.com
SMTP_PASSWORD='your-authorization-code'
```

QQ, 163 and 126 use an authorization code generated after enabling SMTP; Gmail uses an app password. Do not use your web-login password. Mail goes to yourself by default. See [email setup](docs/usage.en.md#email-setup) for obtaining passwords, choosing a recipient and switching accounts.

Restart after saving changes. Existing process environment variables override `.env`; updating the template does not update your existing configuration.

## 3. Check before reserving

First check university login and lecture data, **without submitting reservations or sending email**:

- Windows: `uv run main.py --check`
- A server without a desktop: `uv run main.py --check --headless`

`event=read_only_complete` means the read-only check completed. If it fails, follow [troubleshooting](docs/usage.en.md#troubleshooting) first. The program cannot complete required manual university authentication for you.

If email is configured, run `uv run main.py --test-mail` and confirm inbox delivery. This sends real email; skip it if notifications are disabled.

## 4. Start reservations

**These startup commands submit real reservations. Run only one instance per account across all machines and both projects.**

### Windows locally

```shell
uv run main.py
```

The browser window is shown by default; add `--headless` to hide it. Press `Ctrl+C` to stop. Existing reservations remain in place.

### Ubuntu in the background

First run `uv run main.py --status`. Confirm `process_running=false` and that no other machine is running the same account. From the project folder, start the browser process tree as a systemd service so it can continue after SSH disconnects:

```bash
mkdir -p state
chmod 700 state
touch state/runner.log
chmod 600 state/runner.log
sudo systemd-run --unit=seu-lecture-reserve --collect --service-type=exec \
  --uid="$(id -un)" --working-directory="$PWD" \
  --property=Restart=no --property=UMask=0077 --property=TimeoutStopSec=60 \
  --property="StandardOutput=append:$PWD/state/runner.log" \
  --property=StandardError=inherit \
  "$(command -v uv)" run --locked main.py --headless
```

Use the installation account; omit `sudo` when running as root. Keep configuration in the project's `.env`. The service does not inherit configuration or proxy variables exported only in SSH. Adjust log paths if using a custom state directory.

## 5. Inspect, stop and restart

On Windows, open another PowerShell and enter the project folder. On Ubuntu, reconnect over SSH and enter the original project folder.

```shell
uv run main.py --status
```

`process_running=true` means a local instance is running; `last_query_at` is the latest successful query time. On Ubuntu, also inspect the service and logs:

```bash
sudo systemctl status seu-lecture-reserve.service --no-pager
tail -f state/runner.log
```

Before closing SSH, confirm the query time has updated; reconnect and confirm it keeps advancing. Here, `Ctrl+C` only ends log viewing. To stop background reservations:

```bash
sudo systemctl stop seu-lecture-reserve.service
uv run main.py --status
```

Wait for `process_running=false` before restarting. Code or configuration updates do not change a running process: keep `state/`, stop the old instance, complete a read-only check, then start it using step 4 and confirm `last_query_at` keeps advancing. There are no automatic restarts or boot startup. After a server restart, program exit or authentication stop, fix the problem and repeat step 4. A stopped service may be collected and reported as missing; local logs and state remain available.

## Before use

- Titles, categories, campuses, online/in-person settings and time constraints all apply. Touching endpoints count as time conflicts. Equal activity start/end times are treated as a single point without guessing duration; verify the actual duration yourself, as later conflicts may go undetected.
- Invalid individual booking candidates are skipped and logged locally while other activities remain eligible. Check `invalid_activity_data` in `--status` and local diagnostics. Personal reservation records remain fully validated; missing or reversed times still pause submissions.
- In-person campuses are extracted from the university location field and matched exactly; online mode requires an initial `【线上】` title marker. Venues and cities do not imply a campus. Ticket announcements remain excluded even in allowed categories; see [campus identification and targeted tests](docs/usage.en.md#campus-identification-and-explicitly-targeted-tests).
- Normal scans wait 10 seconds after each round. Known opening times trigger a one-second whole-round target from 30 seconds before to 10 minutes after opening, capped by the deadline, even when full. Navigation, page-wait and preflight errors retry after one extra second in this window, including during pending verification. Short retries do not inflate later ordinary backoff; rate limits, authentication and invalid data retain their waits.
- After an uncertain submission, two consecutive fresh, validated personal-record queries missing the original reservation, separated by one second, automatically release pending and resume normal selection, including retrying that activity. Restarts require new checks; success still requires the original activity ID. **This favors booking opportunities: delayed university records can cause duplicate submissions, conflicts or temporary excess bookings.** Keep `state/`; the program does not cancel university reservations. See [recovery rules](docs/usage.en.md#before-booking-opens-and-success-limits).
- Normal startup loads OCR once before login. Opening scans may reuse personal history less than 10 seconds old while refreshing activities every round. Finding a candidate forces a new history query and activity scan before filtering again; pending submissions always use fresh history.
- Email is limited to blocked authentication, fatal exits, or five minutes without a valid query. Each unresolved issue gets one attempt across restarts. Routine problems, brief pending checks, reservation success, goal completion, query recovery and daily reports do not send mail; local logs retain the events.
- Keep `.env`, `state/` and authentication data private. University records determine reservations and attendance.
- Chromium login and read-only queries on Windows and Linux have recorded passes. An explicitly authorized ticket-activity test on Linux verified OCR, a successful reservation and cancellation, preserving existing reservations. Sustained automatic booking of ordinary lectures and long-running operation remain unverified; see [validation limits](docs/browser-upgrade-requirements.md#验证边界) (Chinese).

[Configuration and troubleshooting](docs/usage.en.md) · [Browser specification](docs/browser-upgrade-requirements.md) (Chinese) · [Independent HTTPS project](https://github.com/MuZiJin701/seu-lecture-reserve-http)

Maintained by [MuZiJin701](https://github.com/MuZiJin701), based on [ApricityWang's original project](https://github.com/ApricityWang/SEU_Lecture_Reserve), retaining original and historical attribution. Goal, state and email logic comes from the maintainer's HTTPS project.
