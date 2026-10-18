# SEU Lecture Reservation · Playwright

[中文](README.md)

> Implemented against the [specification](docs/browser-upgrade-requirements.md) (Chinese). Offline checks and university-system acceptance are recorded separately in the [usage guide](docs/usage.en.md).

Control Chrome with Playwright to browse lectures, fill image CAPTCHAs, click reservation buttons, and verify results. Every platform shows the browser by default; choose `--headless` for no window. Both modes use the same reservation rules.

The goal is eight attended lectures recorded by the university, including law, art and mental health at least once each. One successful reservation does not end the task. Existing reservations occupy remaining places; the program waits until attendance meets the goal. Coffee salons are excluded. Email is optional.

![Browser interface illustration](docs/images/使用截图.png)

*This image shows an older interface. Current rules are described below.*

## Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Google Chrome. The project uses Python 3.11 and needs no ChromeDriver. Linux also needs Chrome libraries; see [server setup](docs/usage.en.md#server-setup).

```shell
git clone https://github.com/MuZiJin701/SEU_Lecture_Reserve.git
cd SEU_Lecture_Reserve
uv sync --locked
```

Copy the example for first-time setup; keep an existing `.env`:

```shell
cp -n .env.example .env
```

Edit the project-root `.env`. It loads automatically; process variables take precedence:

```dotenv
SEU_CARD_NUMBER="your-card-number"
SEU_PASSWORD='your-password'
SEU_PREFERRED_CAMPUS='["无锡校区"]'
```

The empty default campus list excludes offline lectures. Names must match the university system. When upgrading, compare `.env.example`; change old settings to `SEU_TIMEOUT_SCAN_INTERVAL=10` and `SEU_TIMEOUT_LOGIN_REDIRECT=30`. Existing files are not overwritten automatically.

First run a read-only check, without reservations, email or task creation:

```shell
uv run --locked main.py --check
```

After `event=read_only_complete`, start reservations:

```shell
uv run --locked main.py
```

Normal startup submits real reservations. Every startup logs in and reads university records, even after a local completion marker. A different machine needs no state transfer. The default interval is ten seconds, with quiet waiting. Press `Ctrl+C` to stop; restarting on the same machine preserves pending-result protection without cancelling reservations. Run only one instance per account across both projects and all machines.

## Browser mode

Windows and Linux use the same command-line convention:

```shell
uv run main.py
uv run main.py --headless
uv run main.py --check --headless
```

The first command shows a window, the second reserves headlessly, and the third checks headlessly without reservations. The OS and old `SEU_HEADLESS` variable do not select the mode. The sampling entry point `uv run captcha_ocr.py --headless` follows the same convention. Both modes need Chrome; headed Linux needs a graphical environment. Mode changes do not change reservation rules.

## Email and status

Email is optional. Gmail needs only:

```dotenv
SMTP_USERNAME=your-address@gmail.com
SMTP_PASSWORD='your-app-password'
```

Defaults are `smtp.gmail.com:465`, sending to yourself. See [email notifications](docs/usage.en.md#email-notifications) for other providers and overrides.

```shell
uv run --locked main.py --status
uv run --locked main.py --test-mail
```

`--status` reads local task and process-lock data without a browser. `--test-mail` sends one real email without school login; check your inbox separately after SMTP acceptance.

## Linux background operation

After the read-only check, confirm no other instance is running:

```shell
mkdir -p -m 700 state
nohup uv run --locked main.py --headless >> state/runner.log 2>&1 < /dev/null &
echo $! > state/runner.pid
```

This survives SSH disconnects but does not restart after a process or server failure. See [background operation and recovery](docs/usage.en.md#background-operation-and-recovery) for stopping and logs. Adjust paths for a custom state directory.

## Limits

- Exact titles still obey category, campus, online/offline and conflict checks. Touching endpoints count as conflicts.
- Unknown submission results are queried before new submissions. Restarting preserves uncertainty.
- No SMS input or remote desktop is provided. Incomplete authentication stops business actions, preserves the task and optionally emails. Email cannot complete authentication.
- Windows passed real login and read-only checks in both modes. Linux, real reservations, actual OCR and long-running operation remain unverified. The page has no historical total, so full historical coverage is not proven.
- Keep `.env`, `state/` and authentication data private. University records remain authoritative.

See the [usage guide](docs/usage.en.md) and [upgrade requirements](docs/browser-upgrade-requirements.md) (Chinese). The independent [HTTPS project](https://github.com/MuZiJin701/seu-lecture-reserve-http) is unchanged.

Maintained by [MuZiJin701](https://github.com/MuZiJin701), based on [ApricityWang's original project](https://github.com/ApricityWang/SEU_Lecture_Reserve), retaining original and historical attribution. Goal, checkpoint and email logic comes from the maintainer's HTTPS project.
