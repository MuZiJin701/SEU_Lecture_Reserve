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

Choose one of your own sending accounts below. Configure one at a time and switch manually. These four providers need only `SMTP_USERNAME` and `SMTP_PASSWORD`; the script selects the host by email domain and defaults to port 465:

| Sender domain | Automatic SMTP host | Value for `SMTP_PASSWORD` |
| --- | --- | --- |
| `qq.com` | `smtp.qq.com` | Authorization code generated after enabling SMTP |
| `163.com` | `smtp.163.com` | Authorization password generated after enabling SMTP |
| `126.com` | `smtp.126.com` | Authorization password generated after enabling SMTP |
| `gmail.com` | `smtp.gmail.com` | App password generated after enabling 2-Step Verification |

**QQ authorization code:** sign in to [QQ Mail](https://mail.qq.com/). Find SMTP/client services in Settings (possibly under Account or Account and security), enable the SMTP service, complete the security verification and generate an authorization code. Use your full `your-account@qq.com` address for `SMTP_USERNAME` and that code for `SMTP_PASSWORD`. See [Tencent's official SMTP example](https://cloud.tencent.com/document/api/876/129350).

**163/126 authorization password:** sign in to [163 Mail](https://mail.163.com/) or [126 Mail](https://mail.126.com/), open Settings → POP3/SMTP/IMAP, enable the SMTP service and choose “新增授权密码” (add authorization password). Complete the requested phone/security verification and save the generated password. Use that mailbox's full address and authorization password. See [NetEase's authorization-password guide](https://help.mail.126.com/faqDetail.do?code=d7a5dc8471cd0c0e8b4b8f4f8e49998b374173cfe9171305fa1ce630d7f67ac286624f309a1a7089).

**Gmail app password:**

1. Sign in to the sending [Google Account](https://myaccount.google.com/security). Open Security & sign-in, find How you sign in to Google, and enable 2-Step Verification by following the prompts.
2. Open [App passwords](https://myaccount.google.com/apppasswords), signing in again if requested. Create a password for this project; you can name the app `SEU Lecture Reserve`.
3. Copy the generated **16 characters**, omitting display grouping spaces, and use the same account's full Gmail address. The password is shown once; generate another if lost. Changing your Google login password revokes app passwords, so generate a replacement and update `.env`. If the option is unavailable, see [Google's app-password guide](https://support.google.com/accounts/answer/185833).

After obtaining the authorization code/app password, fill in `.env` using this example, replacing the address and password. Gmail, 163 and 126 use the same fields:

```dotenv
SMTP_USERNAME=your-address@qq.com
SMTP_PASSWORD='your-authorization-code'
SMTP_HOST=
SMTP_PORT=465
MAIL_FROM=
MAIL_TO=
```

Use the authorization code/app password for `SMTP_PASSWORD`, rather than a web-login password or SMS code. Leave `SMTP_HOST` empty for case-insensitive domain detection; an explicit host takes precedence. Other domains, aliases and self-hosted mailboxes require the provider's SMTP hostname without a URL scheme or port. When switching accounts, clear or update the previous `SMTP_HOST`, and use the appropriate implicit TLS port in `SMTP_PORT`.

`MAIL_FROM` defaults to the sending account; normally leave it empty, as overrides must be permitted by the provider. `MAIL_TO` defaults to yourself and can instead specify one recipient at another provider, such as `recipient@gmail.com`. See the field comments in [.env.example](.env.example) and [email settings](docs/usage.en.md#email-notifications). Save `.env`, stop the old instance, complete the checks and test email in the next section, and confirm inbox delivery before starting or resuming reservations.

Mail fields in the template are empty; `SMTP_PORT=465` alone keeps notifications disabled. Only `SMTP_SSL` is supported: do not simply switch to port 587 requiring STARTTLS. If the test fails, follow [Gmail connection troubleshooting](docs/usage.en.md#gmail-connection-troubleshooting) to distinguish resolution, proxy and direct-route failures; web access does not establish SMTP connectivity. See the [usage guide](docs/usage.en.md#smtp-http-and-https) for protocol differences, other senders and the unimplemented Gmail API/SSH forwarding options.

Campus Wi-Fi, a phone hotspot and Clash settings may use different SMTP routes; another provider does not guarantee a fix for network restrictions. Test on the network used for operation, comparing with a direct hotspot connection if needed. The script does not switch accounts, networks or proxies automatically. Outlook.com's STARTTLS/OAuth requirements are outside current support.

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

Use a system-level transient systemd service to detach Python, the Playwright driver and Chromium together from SSH. **Do not keep using `nohup` for this browser project**: the Playwright driver may handle an SSH hangup signal by closing the browser while Python remains alive.

In the project directory, first run `uv run main.py --status`. Confirm `process_running=false` and that no other machine is running the same account. Use the same account for installation and operation; these commands expand paths as the current user before creating the service through sudo. Omit `sudo` when running as root:

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

This starts one service without automatic restarts or boot startup. Keep configuration in the project's `.env`; the service does not inherit configuration or proxy variables exported only in SSH. Output appends to `state/runner.log`; no `runner.pid` is written. Inspect it with:

```bash
uv run main.py --status
sudo systemctl status seu-lecture-reserve.service --no-pager
tail -f state/runner.log
```

`--status` shows the latest per-activity reasons and reservation windows in `activity_details`; check `selection_updated_at` for freshness. For example, `reservation_not_started` means booking has not opened. The latest mail time and outcome survive restarts. See [runtime diagnostics](docs/usage.en.md#runtime-diagnostics) for all reasons.

Confirm `process_running=true` and an updated `last_query_at` before disconnecting SSH; reconnect and verify that successful-query timestamps keep advancing. Here, `Ctrl+C` ends log viewing without stopping reservations. Reconnect using the same account, enter the original project directory, and use the same status and log commands.

Stop the systemd service with:

```bash
sudo systemctl stop seu-lecture-reserve.service
uv run main.py --status
```

Wait for `process_running=false` before restarting. Stopped or failed services are collected, so `systemctl status` may report that the unit does not exist; local state and logs remain available. After a server restart, program exit or authentication stop, repeat the startup command manually.

**Migrating from the old `nohup` setup**: first check the old PID, command and working directory:

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

Do not send `kill` if the PID is stale or belongs to another process. Once `process_running=false`, keep `state/`, complete a read-only check with `uv run main.py --check --headless`, then start with the systemd command above.

## Rules and limits

- Activities with a valid category outside the configured selection are excluded first. Within selected categories, missing required categories take priority. Titles, campuses, online/in-person settings and time constraints all apply; touching endpoints count as conflicts.
- The default wait between rounds is 10 seconds. Unknown submission results pause other submissions while the original activity is checked. Do not delete state to bypass this protection.
- The transient systemd service is independent of SSH, without automatic restarts or boot startup. A closed/disconnected browser records `browser_closed`, preserves the task, optionally alerts and exits instead of repeatedly refreshing an unusable page. Restart manually after fixing the problem.
- Keep `.env`, `state/` and authentication data private. University records determine reservations and attendance. Complete historical coverage remains unproven.
- Headless Chromium on Linux and Windows has completed real login and read-only queries. Actual reservations, real CAPTCHA recognition and at least 24 hours of operation remain unverified. See [configuration](docs/usage.en.md#configuration) when upgrading from an older version.

[Full configuration and troubleshooting](docs/usage.en.md) · [Requirements](docs/browser-upgrade-requirements.md) (Chinese) · [Independent HTTPS project](https://github.com/MuZiJin701/seu-lecture-reserve-http)

Maintained by [MuZiJin701](https://github.com/MuZiJin701), based on [ApricityWang's original project](https://github.com/ApricityWang/SEU_Lecture_Reserve), retaining original and historical attribution. Goal, state and email logic comes from the maintainer's HTTPS project.
