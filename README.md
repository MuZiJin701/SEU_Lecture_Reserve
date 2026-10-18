# 东南大学讲座自动预约

[English](README.en.md)

用 Playwright 操作浏览器，自动查看讲座、识别图形验证码、提交预约并核对结果。支持 Windows 和 Linux，邮件通知可选。

目标是实际选听 **8 场系列讲座，法律、艺术、心理健康各至少 1 场**。已有预约会占用剩余名额；计划够了就等待打卡，实际达标后才结束。沙龙不预约、不计数。

## 开始使用

### 1. 安装项目

先准备 [Git](https://git-scm.com/downloads) 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)。项目使用 Python 3.11，由 uv 准备运行环境。

项目统一使用 Playwright 管理的 Chromium，**无需安装 Chrome 或 ChromeDriver**。下载项目、安装依赖后，再下载配套浏览器：

```shell
git clone https://github.com/MuZiJin701/SEU_Lecture_Reserve.git
cd SEU_Lecture_Reserve
uv sync --locked
uv run --locked python -m playwright install chromium --no-shell
```

浏览器首次安装需要联网；更新 Playwright 后也应重跑最后一条命令。程序运行时不会自动下载。Linux 还需系统运行库，完整步骤见[环境准备](docs/usage.md#服务器准备)。

### 2. 填写账号

首次使用时，将项目中的 `.env.example` 复制为同目录的 `.env`，再用文本编辑器填写。已有 `.env` 时保留原文件。

```dotenv
SEU_CARD_NUMBER="你的一卡通号"
SEU_PASSWORD='你的密码'
```

默认只约线上讲座。需要线下讲座时，增加允许的校区，名称须与学校系统一致：

```dotenv
SEU_PREFERRED_CAMPUS='["无锡校区"]'
```

程序自动读取 `.env`，修改后重启生效；已有环境变量优先。其他选项见[配置说明](docs/usage.md#完整配置)。

### 3. 先检查，再预约

先检查登录和讲座数据。这一步会访问学校系统，但不提交预约、不发邮件：

```shell
uv run --locked main.py --check
```

看到 `event=read_only_complete` 后，启动自动预约：

```shell
uv run --locked main.py
```

**正式启动会提交真实预约。** 默认显示浏览器窗口；不需要窗口时加 `--headless`：

```shell
uv run --locked main.py --headless
```

Windows 和 Linux 的用法相同。Linux 无桌面环境时使用 `--headless`；只读检查也可加此参数。按 `Ctrl+C` 停止，不会取消已有预约。

## 程序怎样选讲座

- 每次启动先读取学校记录，计算已选听场次和待参加预约。
- 优先补齐必需类别，并为缺少的类别留出名额；一场预约成功后继续检查。
- 标题、类别、校区、线上线下和时间条件同时生效。首尾相接也算时间冲突。
- 默认每轮等待 10 秒；没有合适讲座或已有预约足够时，安静等待。
- 提交后按活动 ID 核对结果。结果不明时只查询，暂停其他提交；重启后仍保留这个保护。

同账号在所有机器及两个项目之间只运行一个实例。保留本机 `state/` 目录用于恢复；换机器启动无需迁移，但应先停止旧实例。

## 邮件和常用命令

邮件完全可选。不需要通知，就保持邮件配置为空。需要时，每位用户使用自己的发件邮箱；Gmail 只需在 `.env` 填两项，默认发给自己：

```dotenv
SMTP_USERNAME=your-address@gmail.com
SMTP_PASSWORD='your-app-password'
```

应用专用密码需先开启 Google 两步验证，再到 [Google 账号](https://myaccount.google.com/apppasswords)创建，不能填普通登录密码。想发到其他邮箱，再加一行 `MAIL_TO=your-address@example.com`。其他发件服务见[邮件配置](docs/usage.md#邮件通知)。

重要事件即时通知：预约成功、目标完成、需要人工认证、结果待确认、连续失败和异常退出。运行期间每天北京时间 **20:00** 汇报已选听、待参加、类别缺口和最近运行情况；当天 20:00 后启动会在首次等待时汇报。停止运行后不发汇报；同一天最多尝试一次，不因重启或发信失败重复发送。通知使用中文说明。

| 用途 | 命令 |
| --- | --- |
| 查看本地状态，不打开浏览器 | `uv run --locked main.py --status` |
| 发送一封真实测试邮件 | `uv run --locked main.py --test-mail` |
| 无窗口检查登录和数据 | `uv run --locked main.py --check --headless` |

Linux 后台运行、停止和恢复见[使用指南](docs/usage.md#后台运行与恢复)。程序不提供异常退出或服务器重启后的自动启动。

## 使用前须知

- 学校要求短信等人工认证时，程序保留任务并退出；配置了邮件就通知。无头运行和邮件都不能代替认证。
- 此前 Windows Chrome 通过了真实登录和只读查询；切换为 Chromium 后须重新验收。Linux、真实预约、实际验证码识别和长期运行仍待验收。学校页面尚不能证明历史记录完整，最终认定以学校系统为准。
- 不要上传 `.env`、`state/` 或认证数据，也不要删除状态文件来绕过待确认保护。
- 从旧版升级时，对照 `.env.example` 检查配置，尤其是 `SEU_TIMEOUT_SCAN_INTERVAL=10` 和 `SEU_TIMEOUT_LOGIN_REDIRECT=30`。旧 `SEU_HEADLESS` 不再生效。

完整配置、测试及验收记录见[使用指南](docs/usage.md)；设计依据见[改造需求](docs/browser-upgrade-requirements.md)。独立的 [HTTPS 项目](https://github.com/MuZiJin701/seu-lecture-reserve-http)仍单独维护。

维护者：[MuZiJin701](https://github.com/MuZiJin701)。基于 [ApricityWang 的原始项目](https://github.com/ApricityWang/SEU_Lecture_Reserve)继续开发，保留原作者及历史贡献者署名；目标统计、状态和邮件逻辑来自维护者的 HTTPS 项目。
