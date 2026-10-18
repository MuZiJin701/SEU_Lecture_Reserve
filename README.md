# 东南大学讲座自动预约

[English](README.en.md)

通过 Chromium 自动查看讲座、识别图形验证码、预约并核对结果。目标是实际选听 **8 场系列讲座，法律、艺术、心理健康各至少 1 场**；沙龙不计数。已有预约足够时等待打卡，实际达标后结束。

按下面顺序完成安装、配置和检查，再选择本地运行或服务器后台运行。

## 1. 安装

**Windows 本地**：先安装 [Git](https://git-scm.com/downloads) 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)，重新打开 PowerShell。

**Ubuntu 24.04 服务器**：使用已有 sudo 或 root 权限的账号登录 SSH，准备工具。root 用户执行下面两条 apt 命令时去掉 `sudo`；已有工具可跳过对应安装：

```bash
sudo apt update
sudo apt install git curl nano
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
```

然后下载项目、准备 Python 3.11 和依赖。以下默认放在用户主目录；已有项目直接进入原目录即可：

```shell
cd ~
git clone https://github.com/MuZiJin701/SEU_Lecture_Reserve.git
cd SEU_Lecture_Reserve
uv sync
```

安装项目使用的浏览器：

- Windows：`uv run playwright install chromium`
- Ubuntu：`uv run playwright install --with-deps chromium`

Ubuntu 安装系统运行库时可能要求 sudo 密码。安装与运行使用同一账号；首次下载需要联网，更新 Playwright 后重跑浏览器安装命令。

## 2. 配置账号、校区和邮件

首次使用时，将 `.env.example` 复制为同目录的 `.env`，已有文件请保留。

Windows 可在资源管理器中复制并用文本编辑器打开；Ubuntu 执行：

```bash
cp -n .env.example .env
chmod 600 .env
nano .env
```

在 nano 中按 `Ctrl+O`、回车保存，再按 `Ctrl+X` 退出。

在 `.env` 中填写：

```dotenv
SEU_CARD_NUMBER="你的一卡通号"
SEU_PASSWORD='你的密码'
SEU_PREFERRED_CAMPUS='[]'

# 邮件可选，不需要就留空
SMTP_USERNAME=
SMTP_PASSWORD=
```

校区为 `[]` 时只约线上；需要线下时改为学校系统中的校区名称，例如 `'["无锡校区"]'`。

需要邮件时，每位用户填写自己的发件账号。**Gmail 的 `SMTP_PASSWORD` 获取步骤：**

1. 登录用于发信的 [Google 账号](https://myaccount.google.com/security)，进入“安全性与登录”，在“您的 Google 账号登录选项”中开启“两步验证”，按页面提示完成设置。
2. 打开[应用专用密码](https://myaccount.google.com/apppasswords)，如有要求则再次登录。为本项目创建密码，应用名称可填 `SEU Lecture Reserve`。
3. 复制生成的 **16 个字符**，去掉用于分组显示的空格，填入 `.env` 的 `SMTP_PASSWORD`；`SMTP_USERNAME` 填同一个账号的完整 Gmail 地址。例如，替换下面的邮箱与密码：

```dotenv
SMTP_USERNAME=your-address@gmail.com
SMTP_PASSWORD='your-app-password'
```

4. 保存 `.env`；如果程序正在运行，先停止。按下一节完成检查和测试邮件、确认收件箱收到后，再启动或恢复预约。

应用专用密码仅显示一次；忘记后可重新生成。更改 Google 登录密码后，需重新生成应用专用密码并更新 `.env`。找不到该入口时，见 [Google 应用专用密码说明](https://support.google.com/accounts/answer/185833?hl=zh-Hans)。`SMTP_PASSWORD` 填应用专用密码，不填登录密码或短信验证码。

默认发给自己；想换收件邮箱，再加 `MAIL_TO=recipient@example.com`。其他发件服务见[邮件配置](docs/usage.md#邮件通知)。

邮件包括重要通知和运行期间每天北京时间 **20:00** 的进度汇报。程序停止后不汇报，同一天最多尝试一次日报。配置修改后重启生效；进程环境变量优先于 `.env`。

## 3. 检查后再启动

先检查登录和讲座数据，**不提交预约、不发邮件**：

- Windows 本地：`uv run main.py --check`
- 无桌面的服务器：`uv run main.py --check --headless`

看到 `event=read_only_complete` 后再继续。配置了邮件的用户，再发一封测试邮件并检查收件箱：

```shell
uv run main.py --test-mail
```

这条命令会真实发信；未配置邮件就跳过。学校要求人工认证时须先处理认证，邮件不能代替登录。

## 4. 运行、查看与停止

**正式启动会提交真实预约。同账号在所有机器及两个项目之间只运行一个实例。**

### Windows 本地运行

在项目目录执行，默认显示浏览器窗口：

```shell
uv run main.py
```

不需要窗口时加 `--headless`。按 `Ctrl+C` 停止，不会取消已有预约。

### Ubuntu 服务器后台运行

在项目目录先执行 `uv run main.py --status`。确认 `process_running=false`，且其他机器也没有同账号实例后启动：

```bash
mkdir -p state
chmod 700 state
nohup uv run main.py --headless >> state/runner.log 2>&1 < /dev/null &
echo $! > state/runner.pid
```

这会保存进程号并将输出追加到日志。查看运行情况：

```bash
uv run main.py --status
tail -f state/runner.log
```

确认 `process_running=true`、`last_query_at` 已更新后再关闭 SSH。`Ctrl+C` 只退出日志查看，不停止后台预约。重新登录同一账号后，先 `cd ~/SEU_Lecture_Reserve`，再用以上命令查看状态和日志。

需要停止时，先核对保存的进程号、命令和工作目录：

```bash
reserve_pid=$(cat state/runner.pid)
ps -p "$reserve_pid" -o pid,args
readlink "/proc/$reserve_pid/cwd"
```

**确认是本项目的进程后**，再执行：

```bash
kill "$reserve_pid"
uv run main.py --status
```

等到 `process_running=false` 后才重新启动。若 PID 已失效或对应其他进程，不要执行 `kill`。保留 `state/`，恢复时重复后台启动步骤；服务器重启、程序退出或人工认证受阻后，都需手动启动。

## 使用规则与限制

- 优先补齐必需类别，标题、校区、线上线下和时间条件同时生效；首尾相接也算冲突。
- 默认每轮等待 10 秒。提交结果不明时只核对原活动，暂停其他提交；不要删除状态文件绕过保护。
- `nohup` 用于终端断开后继续运行，不提供异常恢复或开机自启。若服务器有登出清理策略，需在目标机器断开 SSH 后验证进程和查询仍在继续。
- 不要上传 `.env`、`state/` 或认证数据。最终预约、选听认定以学校系统为准，页面历史记录的完整性尚不能证明。
- 离线测试已通过；Chromium 真实学校登录、Linux 业务运行、真实预约、实际验证码识别及长期运行仍待验收。从旧版升级的配置说明见[使用指南](docs/usage.md#完整配置)。

[完整配置与排错](docs/usage.md) · [改造需求](docs/browser-upgrade-requirements.md) · [独立 HTTPS 项目](https://github.com/MuZiJin701/seu-lecture-reserve-http)

维护者：[MuZiJin701](https://github.com/MuZiJin701)。基于 [ApricityWang 的原始项目](https://github.com/ApricityWang/SEU_Lecture_Reserve)继续开发，保留原作者及历史贡献者署名；目标统计、状态和邮件逻辑来自维护者的 HTTPS 项目。
