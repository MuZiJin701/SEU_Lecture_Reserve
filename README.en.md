# SEU Lecture Reservation

[中文](README.md)

Keep checking for suitable SEU lectures, filter them, recognize image CAPTCHAs, and attempt a reservation. SMS verification needs your input. The program exits after confirming one reservation.

![Lecture reservation script running](docs/images/使用截图.png)

*After login, the script keeps scanning for lectures that match your settings.*

## Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Google Chrome. ChromeDriver is not needed.

**1. Download the project and install dependencies**

```shell
git clone https://github.com/MuZiJin701/SEU_Lecture_Reserve.git
cd SEU_Lecture_Reserve
uv sync --locked
```

**2. Fill in your settings**

For first-time setup, copy the example below. Keep your existing `.env` if you already have one.

```shell
cp .env.example .env
```

Open `.env` in a text editor and enter your credentials and campus, for example:

```dotenv
SEU_CARD_NUMBER="your-card-number"
SEU_PASSWORD="your-password"
SEU_PREFERRED_CAMPUS='["无锡校区"]'
SEU_TIMEOUT_LOGIN_REDIRECT=60
```

Campus names must match the university system exactly. This example allows 60 seconds for any SMS verification.

**3. Start**

```shell
uv run main.py
```

Complete SMS verification in the browser if prompted. The script keeps scanning and exits after confirming one reservation.

## Common settings

Edit `.env`, then restart. Use the campus example above as the format for lists.

| Setting | Purpose |
| --- | --- |
| `SEU_PREFERRED_CAMPUS` | Campuses you want to attend; multiple names are allowed |
| `SEU_REQUIRED_CATEGORIES` | Lecture categories to include; the example values can be kept |
| `SEU_ENABLE_ONLINE` / `SEU_ENABLE_OFFLINE` | Allow online / offline lectures; use `true` or `false` |
| `SEU_PREFERRED_LECTURES` | Only reserve exact titles; normally leave it as `'[]'` |

See [.env.example](.env.example) for all settings and the [usage guide](docs/usage.en.md) for formats and troubleshooting.

## Before you run

- The campus list is empty by default, which excludes all offline lectures. Fill it in for offline reservations.
- Selecting exact titles bypasses category, campus, online/offline switches, and time conflict checks.
- Keep the terminal and browser open. Press `Ctrl+C` to stop.
- OCR and reservations can fail. Conflict checks only cover the current page. Confirm your reservation and schedule in the [SEU portal](https://ehall.seu.edu.cn/) and follow university rules.
- Do not upload `.env`, login pages, or screenshots containing personal information.

## Credits and maintenance

Maintained by [MuZiJin701](https://github.com/MuZiJin701), based on [ApricityWang's original project](https://github.com/ApricityWang/SEU_Lecture_Reserve). Attribution for the original author and historical contributors is retained.
