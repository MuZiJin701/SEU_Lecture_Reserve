# SEU Lecture Auto Reservation

[中文](README.md)

Automatically find lectures, read CAPTCHAs, reserve places and verify results. The goal is **8 attended series lectures or SEU Coffee Salon activities, including at least one each in law, art and mental health**. Once reservations cover the plan, the program waits for attendance and exits when the goal is met. Test activities and ticket announcements are excluded; university records determine recognition.

![Read-only check, test email and headless startup example](docs/images/使用截图.png)

Follow these five steps. Run commands inside the project folder; keep using the original directory for an existing checkout.

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

Use the same account for installation and operation. Reinstall the browser after updating Playwright.

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

Email is optional and alerts only on major problems. Leave mail fields empty to disable it, or enter your full sending address and authorization code:

```dotenv
SMTP_USERNAME=your-address@qq.com
SMTP_PASSWORD='your-authorization-code'
```

Use an SMTP authorization code for QQ, 163 or 126, or a Gmail app password. Do not use your web-login password. Mail goes to yourself by default; see [email setup](docs/usage.en.md#email-setup).

Restart after configuration changes. Existing environment variables override `.env`.

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

First run `uv run main.py --status`. Confirm `process_running=false` and that no other machine is running the same account. Then run this from the project folder to continue after SSH disconnects:

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

To restart or update, stop the old instance, confirm `process_running=false`, and keep `state/`. Complete the checks in step 3, then start using step 4 and confirm `last_query_at` keeps advancing.

There are no automatic restarts or boot startup; start again after a server restart or program exit. A stopped service may be reported as missing; local logs and state remain available.

## How it runs

- Title, category, campus and time filters all apply. Activities conflicting with existing reservations are skipped; see [filter settings](docs/usage.en.md#configuration).
- Scanning speeds up around booking openings. University response times and competition still affect results; a place is not guaranteed.
- After an uncertain submission, two fresh checks finding no original reservation automatically resume booking. Delayed university records can cause duplicate submissions, conflicts or excess bookings; the program does not cancel reservations automatically. See [recovery rules](docs/usage.en.md#before-booking-opens-and-success-limits).
- Email alerts only on blocked authentication, fatal exits or five minutes without a valid query. Each unresolved issue gets one alert. Success notices and daily reports are disabled; check progress with `--status`.
- Keep `state/` for recovery. Do not upload `.env`, `state/` or authentication data.

[Configuration and troubleshooting](docs/usage.en.md) · [Browser specification](docs/browser-upgrade-requirements.md) (Chinese) · [Independent HTTPS project](https://github.com/MuZiJin701/seu-lecture-reserve-http)

Maintained by [MuZiJin701](https://github.com/MuZiJin701), based on [ApricityWang's original project](https://github.com/ApricityWang/SEU_Lecture_Reserve), retaining original and historical attribution. Goal, state and email logic comes from the maintainer's HTTPS project.
