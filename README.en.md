# SEU Lecture Auto Reservation

[中文](README.md)

Use Playwright to control a browser, find lectures, read image CAPTCHAs, submit reservations and verify results. Supports Windows and Linux. Email notifications are optional.

The goal is **8 attended series lectures, including at least one each in law, art and mental health**. Upcoming reservations fill remaining places. When the plan is full, the program waits for attendance and exits once the goal is met. Salons are excluded.

## Get started

### 1. Install the project

Prepare [Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/getting-started/installation/). The project uses Python 3.11; uv prepares the runtime environment.

The project uses Playwright-managed Chromium. **Chrome and ChromeDriver are not required.** Download the project, install its dependencies, then download the matching browser:

```shell
git clone https://github.com/MuZiJin701/SEU_Lecture_Reserve.git
cd SEU_Lecture_Reserve
uv sync --locked
uv run --locked python -m playwright install chromium --no-shell
```

The initial browser download needs internet access. Run the last command again after updating Playwright. The program does not download browsers at startup. Linux also needs system libraries; see the full [environment setup](docs/usage.en.md#server-setup).

### 2. Enter your account details

For first-time setup, copy `.env.example` to `.env` in the same project directory, then edit it in a text editor. Keep any existing `.env`.

```dotenv
SEU_CARD_NUMBER="your-card-number"
SEU_PASSWORD='your-password'
```

By default, only online lectures are selected. To include in-person lectures, add allowed campuses using the exact names shown by the university:

```dotenv
SEU_PREFERRED_CAMPUS='["无锡校区"]'
```

The program reads `.env` automatically. Restart after changes; existing environment variables take precedence. See [configuration](docs/usage.en.md#configuration) for other options.

### 3. Check first, then start

Check login and lecture data first. This contacts the university but makes no reservations and sends no email:

```shell
uv run --locked main.py --check
```

After seeing `event=read_only_complete`, start automatic reservations:

```shell
uv run --locked main.py
```

**Normal startup submits real reservations.** A browser window opens by default. Add `--headless` to run without a window:

```shell
uv run --locked main.py --headless
```

Windows and Linux use the same commands. Use `--headless` on Linux without a desktop; it also works with the read-only check. Press `Ctrl+C` to stop. Existing reservations stay in place.

## How lectures are selected

- Each startup reads university records to count attended lectures and upcoming reservations.
- Missing required categories take priority, with places kept for them. One successful reservation does not end the task.
- Titles, categories, campuses, online/in-person settings and time constraints all apply. Touching start/end times count as conflicts.
- The default wait between rounds is 10 seconds. The program waits quietly when no suitable lecture is available or the plan is full.
- Submissions are verified by activity ID. An unknown result pauses all other submissions while the program checks it. Restarting preserves this protection.

Run only one instance per account across all machines and both projects. Keep the local `state/` directory for recovery. A new machine needs no state transfer, but stop the old instance first.

## Email and useful commands

Email is optional: leave the mail settings empty to disable it. Each user uses their own sending account. For Gmail, add just two values to `.env`; messages go to the same address by default:

```dotenv
SMTP_USERNAME=your-address@gmail.com
SMTP_PASSWORD='your-app-password'
```

Enable Google 2-Step Verification, then create an app password in your [Google Account](https://myaccount.google.com/apppasswords). Do not use your regular login password. To receive messages elsewhere, add `MAIL_TO=your-address@example.com`. See [email settings](docs/usage.en.md#email-notifications) for other sending providers.

Important events trigger immediate notifications: successful reservations, goal completion, required authentication, unknown results, repeated failures and abnormal exits. While running, the program also reports attendance, upcoming reservations, missing categories and recent health at **20:00 Asia/Shanghai** each day. Starting after 20:00 sends the day's report at the first wait. Reports stop when the program stops. Each day has at most one attempt, including across restarts or email failures. Notification text is in Chinese.

| Purpose | Command |
| --- | --- |
| View local status without a browser | `uv run --locked main.py --status` |
| Send one real test email | `uv run --locked main.py --test-mail` |
| Check login and data without a window | `uv run --locked main.py --check --headless` |

See the [usage guide](docs/usage.en.md#background-operation-and-recovery) for Linux background operation, stopping and recovery. The program does not restart automatically after a process or server failure.

## Before you run

- If the university requires SMS or other manual authentication, the program saves the task and exits, with email if configured. Headless mode and email cannot complete authentication.
- Earlier Windows Chrome checks passed real login and read-only queries. The switch to Chromium needs fresh acceptance checks. Linux, real reservations, actual CAPTCHA recognition and long-running operation also remain unverified. The page does not prove complete historical coverage; university records remain authoritative.
- Keep `.env`, `state/` and authentication data private. Do not delete state files to bypass unknown-result protection.
- When upgrading, compare `.env.example`, especially `SEU_TIMEOUT_SCAN_INTERVAL=10` and `SEU_TIMEOUT_LOGIN_REDIRECT=30`. The old `SEU_HEADLESS` setting is ignored.

See the [usage guide](docs/usage.en.md) for full configuration, tests and acceptance records. The [requirements](docs/browser-upgrade-requirements.md) are in Chinese. The independent [HTTPS project](https://github.com/MuZiJin701/seu-lecture-reserve-http) is maintained separately.

Maintained by [MuZiJin701](https://github.com/MuZiJin701), based on [ApricityWang's original project](https://github.com/ApricityWang/SEU_Lecture_Reserve), retaining original and historical attribution. Goal, state and email logic comes from the maintainer's HTTPS project.
