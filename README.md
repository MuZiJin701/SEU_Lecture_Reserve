# 东南大学讲座自动预约

[English](README.en.md)

自动查找讲座、识别验证码、预约并核对结果。目标是实际参加 **8 场系列讲座或 SEU 咖啡间沙龙，法律、艺术、心理健康各至少 1 场**。预约覆盖目标后等待参加，实际达标才结束；测试活动和购票公告不自动预约，最终认定以学校记录为准。

![只读检查、邮件测试与无头启动示例](docs/images/使用截图.png)

按下面五步操作。命令都在项目文件夹中执行；已有项目继续使用原目录。

## 1. 安装

**Windows**：安装 [Git](https://git-scm.com/downloads) 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)，重新打开 PowerShell。

**Ubuntu 24.04 服务器**：通过 SSH 登录有 sudo 权限的账号，安装工具；root 用户去掉 `sudo`。已有工具可跳过安装。

```bash
sudo apt update
sudo apt install git curl nano
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
```

两种环境都执行以下命令，下载项目并准备 Python 3.11 和依赖；已有项目就进入原文件夹。

```shell
cd ~
git clone https://github.com/MuZiJin701/seu_lecture_reserve.git
cd seu_lecture_reserve
uv sync --locked
```

安装项目使用的 Chromium 浏览器，成功后再继续：

- Windows：`uv run playwright install chromium`
- Ubuntu：`uv run playwright install --with-deps chromium`，可能需要输入 sudo 密码。

安装和运行使用同一账号。更新 Playwright 后需重新安装浏览器。

## 2. 填写配置

首次使用，将 `.env.example` 复制为同目录的 `.env`。**已有 `.env` 时跳过复制，直接编辑，避免覆盖账号和密码。**

Windows 在 PowerShell 中执行：

```powershell
Copy-Item .env.example .env
notepad .env
```

Ubuntu 执行：

```bash
cp -n .env.example .env
chmod 600 .env
nano .env
```

在 nano 中按 `Ctrl+O`、回车保存，`Ctrl+X` 退出。填写学校账号和密码，按需修改校区：

```dotenv
SEU_CARD_NUMBER="你的一卡通号"
SEU_PASSWORD='你的密码'
SEU_PREFERRED_CAMPUS='[]'
```

校区为 `[]` 时只约线上。需要线下时填写学校中的校区名称，例如 `'["无锡校区"]'`；线上仍可预约。其他筛选和等待时间见[完整配置](docs/usage.md#完整配置)。

邮件可选，只提醒重大问题。不需要就保留空值；需要时填写完整发件邮箱和授权码：

```dotenv
SMTP_USERNAME=your-address@qq.com
SMTP_PASSWORD='your-authorization-code'
```

QQ、163、126 填 SMTP 授权码，Gmail 填应用专用密码，不填网页登录密码。默认发给自己，详见[邮件配置](docs/usage.md#邮件配置)。

修改配置后重启生效；已有环境变量优先于 `.env`。

## 3. 先检查，再预约

先检查学校登录和讲座数据，**不会提交预约或发邮件**：

- Windows：`uv run main.py --check`
- 无桌面的服务器：`uv run main.py --check --headless`

看到 `event=read_only_complete` 表示只读检查完成。失败时先按[排错步骤](docs/usage.md#排错步骤)处理；学校要求人工认证时，程序不能代替完成。

配置了邮件，再执行 `uv run main.py --test-mail`，并确认收件箱收到。这条命令会真实发信；不用邮件就跳过。

## 4. 启动预约

**以下启动命令会提交真实预约。同账号在所有机器及两个项目之间只运行一个实例。**

### Windows 本地

```shell
uv run main.py
```

默认显示浏览器窗口；加 `--headless` 隐藏窗口。按 `Ctrl+C` 停止，已有预约保留。

### Ubuntu 服务器后台

先运行 `uv run main.py --status`，确认 `process_running=false`，且其他机器没有同账号实例。然后在项目目录执行，关闭 SSH 后仍可运行：

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

使用安装时的同一账号；root 用户去掉 `sudo`。配置写在项目 `.env`，服务不继承 SSH 中临时导出的配置或代理变量。自定义状态目录时，同步调整日志路径。

## 5. 查看、停止与重启

Windows 可在另一个 PowerShell 中进入项目目录查看状态；Ubuntu 重连 SSH 后进入原项目目录。

```shell
uv run main.py --status
```

`process_running=true` 表示本地实例在运行，`last_query_at` 是最近成功查询时间。Ubuntu 还可查看服务和日志：

```bash
sudo systemctl status seu-lecture-reserve.service --no-pager
tail -f state/runner.log
```

关闭 SSH 前确认查询时间已更新，重连后确认它仍在更新。`Ctrl+C` 只结束日志查看。停止后台预约用：

```bash
sudo systemctl stop seu-lecture-reserve.service
uv run main.py --status
```

重启或更新时，先停止旧实例，确认 `process_running=false`，并保留 `state/`。完成第 3 步检查，再按第 4 步启动，确认 `last_query_at` 持续更新。

服务不会自动重启或开机自启；服务器重启或程序退出后需重新启动。停止后显示“未找到服务”是正常情况，本地日志和状态仍保留。

## 运行规则

- 标题、类别、校区和时间条件同时生效；与已有预约时间冲突的活动会跳过。详细筛选见[使用指南](docs/usage.md#完整配置)。
- 开放预约时会加速扫描；学校响应速度和名额竞争仍会影响结果，不能保证抢到名额。
- 提交结果不明时，若连续两次查询都没找到原预约，就自动继续尝试。学校记录延迟时，可能重复提交、冲突或多约；程序不自动取消预约。详见[恢复规则](docs/usage.md#开抢前检查与成功边界)。
- 邮件只提醒认证受阻、异常退出或连续 5 分钟无法完成查询；同一未解决问题只提醒一次，不发成功通知和日报。进度用 `--status` 查看。
- 保留 `state/` 以便恢复；不要上传 `.env`、`state/` 或认证数据。

[配置与排错指南](docs/usage.md) · [浏览器规格](docs/browser-upgrade-requirements.md) · [独立 HTTPS 项目](https://github.com/MuZiJin701/seu-lecture-reserve-http)

维护者：[MuZiJin701](https://github.com/MuZiJin701)。基于 [ApricityWang 的原始项目](https://github.com/ApricityWang/SEU_Lecture_Reserve)继续开发，保留原作者及历史贡献者署名；目标统计、状态和邮件逻辑来自维护者的 HTTPS 项目。
