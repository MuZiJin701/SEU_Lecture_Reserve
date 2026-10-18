# 使用与维护指南

[返回首页](../README.md) · [English](usage.en.md)

> 实现依据为[最终规格](browser-upgrade-requirements.md)。所有平台默认有头，显式 `--headless` 无头；普通启动每次通过网站核对个人记录，不要求迁移状态目录。离线验证不代表真实预约和长期运行已验收。

## 运行入口

| 命令 | 行为 |
| --- | --- |
| `uv run --locked main.py --check` | 登录、查看“我的活动／全部”和讲座列表并校验；不打开预约弹窗、不提交、不发邮件、不创建任务 |
| `uv run --locked main.py` | 开始或恢复真实预约 |
| `uv run --locked main.py --headless` | 无头运行真实预约；也可与 `--check` 组合 |
| `uv run --locked main.py --status` | 本地状态和进程锁，不启动浏览器、不要求学校凭据 |
| `uv run --locked main.py --test-mail` | 真实发送一封邮件，不登录学校、不创建任务 |
| `uv run --locked main.py --new-task` | 重新核对已完成目标；不能重置活跃或待确认任务 |

项目 `.env` 自动加载，进程环境变量优先；改配置后重启。浏览器模式只由命令参数决定，旧 `SEU_HEADLESS` 被忽略。`captcha_ocr.py` 也默认有头，可加 `--headless`。`--new-task` 只作兼容保留，普通启动即使本地已完成也会登录重查，不需要先加此参数。`--check` 不验证真实提交或 OCR，邮件需用 `--test-mail` 单独验收并核对收件箱。

## 完整配置

| 环境变量 | 含义与默认值 |
| --- | --- |
| `SEU_CARD_NUMBER`、`SEU_PASSWORD` | 正常启动和只读检查必填；状态和测试邮件不要求 |
| `SEU_PREFERRED_LECTURES` | 完整标题数组，默认 `[]`；仍受全部其他筛选约束 |
| `SEU_REQUIRED_CATEGORIES` | 候选类别及顺序；默认心理健康、法律、艺术、其他；不能空或重复；沙龙不预约、不计数 |
| `SEU_PREFERRED_CAMPUS` | 线下校区白名单，默认 `[]` 不约线下 |
| `SEU_ENABLE_OFFLINE`、`SEU_ENABLE_ONLINE` | 线下／线上开关，默认均为 `true` |
| `SEU_STATE_DIR` | 私有检查点和事件目录，默认项目目录下 `state`，支持绝对路径 |
| `SEU_VPN_IP` | 可选 VPN 备用 IPv4／IPv6，默认空；样例预填 `121.249.14.2`，正常 DNS 优先 |
| `SEU_TIMEOUT_PAGE_LOAD` | 登录导航后的额外等待，默认 0.5 秒 |
| `SEU_TIMEOUT_ELEMENT_WAIT` | 页面、数据、元素和显示结果的等待上限，默认 3 秒；慢网络可增至 15 |
| `SEU_TIMEOUT_LOGIN_REDIRECT` | 认证跳转上限，默认 30 秒；不提供短信输入 |
| `SEU_TIMEOUT_SCAN_INTERVAL` | 正常扫描和待确认查询的间隔，默认 10 秒，必须大于零 |
| `SEU_TIMEOUT_ACTION_CONFIRM` | 点击提交后的基础等待，默认 0.2 秒，随后仍须核对活动 ID |
| `SMTP_USERNAME`、`SMTP_PASSWORD` | 邮箱账号和应用专用密码，Gmail 可只填这两项 |
| `SMTP_HOST`、`SMTP_PORT` | 显式 SMTP 主机和 TLS 端口；Gmail 默认 `smtp.gmail.com:465` |
| `MAIL_FROM`、`MAIL_TO` | 显式发件人与收件人；默认账号自己给自己发信 |

列表是 JSON 数组，例如 `SEU_PREFERRED_CAMPUS='["无锡校区"]'`；开关用 `true/false`，含空格或 `#` 的密码加引号。数字须有限且非负。Playwright 超时为零时转换为 1 毫秒，避免无限等待。旧的 `SEU_TIMEOUT_RETRY_DELAY` 仅兼容读取，业务失败统一退避。旧 `.env` 中的 0.05 秒扫描不会自动改为十秒，请手动调整。

## 浏览器与预约规则

全程由 Playwright 操作 Chromium：登录 → 刷新 → 点击“我的活动／全部” → 读取选听和预约 → 刷新讲座列表 → 按稳定 ID 定位卡片 → 点击精确“预约”按钮 → 读取图形验证码并填写 → 点击确定 → 返回“我的活动／全部”核对原活动 ID。

只读页面已绑定的 Vue 数据以取得 ID、打卡和违约状态，不调用 Vue 业务方法或另建接口客户端。校验学校时间已加载、页面无错误、全部筛选和卡片数量一致。当前页面没有历史总数，`count` 为未读通知数；全历史完整性仍待进一步证明。

目标为已打卡、未违约、未取消且按冲突规则计入本地的八场系列讲座，法律、艺术、心理健康各至少一场。已选听与有效待参加预约共同占位，优先补齐必需类别并预留名额。计划覆盖后等待核对，实际打卡达标才结束；取消／违约后补足，已结束但打卡／违约未明确时暂停新增。

标题、类别、校区、线上线下和冲突条件共同生效。沿用浏览器版约定，标题含“线上”视为线上；页面没有独立线上布尔字段，学校命名变化后需重新验收。新增与全部有效预约检查冲突，首尾相接也算冲突。已有重叠按已打卡、当前缺少类别、结束较早、活动 ID 顺序逐次选择本地计数场次；不取消学校记录，未计数的有效预约仍参与冲突检查。

缺少类别优先，其余按配置类别顺序、线上优先、开始较早排序。验证码明确错误后最多再取图三次，再让该场冷却五分钟。提交前原子保存 `pending`；即使页面提示成功，也先按活动 ID 查询确认。超时、断线或未知结果不当作验证码错误重试。结果持续不明时只查询并通知一次，不提交其他讲座、不要求终端按回车。

## 邮件通知

邮件完全可选。每位用户配置自己的发件账号，无需统一发信后台；不要分享应用专用密码。全部邮件项为空／缺省时关闭，单独保留 `SMTP_PORT=465` 也视为关闭。尝试配置但缺项或格式错误时停止启动。

Gmail 只填 `SMTP_USERNAME` 和 `SMTP_PASSWORD` 即可：先开启 Google 两步验证，再[创建应用专用密码](https://myaccount.google.com/apppasswords)。某些账号策略不允许创建，见 [Google 说明](https://support.google.com/accounts/answer/185833)。默认自己给自己发信；可选的 `MAIL_TO` 指定另一个服务商的单个收件地址。其他发件邮箱再填 `SMTP_HOST`，按服务商要求填写账号与授权码；端口默认 465。`MAIL_FROM` 默认发件账号，覆盖时须得到发信服务允许。当前使用校验证书的 `SMTP_SSL`，也支持无需认证的 TLS 中继，不支持 STARTTLS 或明文 SMTP。

单场成功、目标完成、认证需人工处理、预约结果待确认和可捕获异常退出会记录终端及本地事件，启用邮件后再通知。连续三轮查询或处理失败提醒一次，恢复后重置；正常轮询不发信。邮件包含中文事件说明和处理建议，不含学校凭据、讲座标题、完整个人记录或票据。

启用邮件后，运行期间每天北京时间 20:00 自动汇报已选听、待参加数量、必需类别缺口（含待参加计划）、进度记录时间、最近成功查询和待处理问题。等待和退避会在 20:00 唤醒发信，但不会提前发起学校查询；页面操作或 SMTP 等待可能使汇报稍有延迟。查询失败时使用最近核对的进度并标明时间，未取得数据时显示未知，不将查询错误当作零场。重启到待确认状态时尚未重建的进度也显示未知。

同一状态目录每天最多尝试一次汇报，发送前保存尝试时间；当天 20:00 后启动会在首次等待时补发当天汇报，不补发更早日期。不配置邮件、只读检查、程序停止或目标完成退出后都不继续汇报。汇报和其他通知发信失败后均不自动重发。

发信失败只记 `notification_failed`，不重发、不改变预约结果、不重复预约。`test_mail_accepted`／`mail_status=accepted` 仅表示 SMTP 接受，不证明收件箱送达；强制结束、断电或邮件不可达时不能保证通知。

当前通知范围见[邮件通知需求](notification-requirements.md)。

## 服务器准备

Windows 和 Linux 统一使用 Playwright 管理的 Chromium，不使用机器上已有的 Chrome。先安装 Git 和 uv，按 [README](../README.md#开始使用) 下载项目并执行 `uv sync --locked`，再安装浏览器：

```shell
uv run --locked python -m playwright install chromium --no-shell
```

浏览器安装在 Playwright 的用户缓存中，不进入 Git 仓库，也不替换系统 Chrome。有窗口和无窗口都使用完整 Chromium；`--no-shell` 省去另一个无头专用版本。首次下载需联网，Playwright 更新后重跑该命令；程序缺少浏览器时会提示安装命令，不在运行中自动下载。参见 [Playwright 官方说明](https://playwright.dev/python/docs/browsers)。

受支持的 Debian／Ubuntu 还需系统运行库，可由管理员执行：

```shell
uv run --locked python -m playwright install-deps chromium
```

该命令可能要求管理员权限并修改系统包。无头模式不需要桌面；有窗口模式需图形环境，服务器上使用 `--headless`。

接着复制 `.env.example` 为 `.env`，填写学校账号、校区及可选邮件配置。先验证登录和数据：

```shell
uv run --locked main.py --check --headless
```

看到 `event=read_only_complete` 后，如已配置邮件，可运行 `uv run --locked main.py --test-mail` 并核对收件箱。最后执行 `uv run --locked main.py --headless` 开始真实预约；后台运行按下一节操作。Windows 需要显示窗口时去掉 `--headless`。

## 后台运行与恢复

按 README 的 `nohup` 命令（带 `--headless`）启动前先用 `--status` 核对无运行实例。锁只覆盖同一状态目录；同账号在所有主机和两个项目之间仅运行一个实例，不提供跨主机锁。换机器可直接登录读取学校记录，无需迁移目录；本地文件仅辅助本机恢复，不承诺跨主机提交去重。

```shell
uv run --locked main.py --status
tail -n 20 state/runner.log
tail -n 20 state/events.log
```

`scanning/pending/done` 是任务状态，不能单独证明健康。结合 `process_running`（进程锁）、`phase`、最近成功查询时间和错误判断。`manual_required` 表示认证受阻；停止后 `phase=stopped`、`last_phase` 保留上一阶段。

停止后台实例前读取 PID 并核对命令、工作目录：

```shell
reserve_pid=$(cat state/runner.pid)
ps -p "$reserve_pid" -o pid,ppid,args
readlink "/proc/$reserve_pid/cwd"
```

确认是本项目后执行 `kill -TERM "$reserve_pid"`，再核对退出。保留状态目录，用原命令重启；退避与待确认结果会恢复。不提供活跃任务重置、自动取消、后台短信输入、守护服务或重启自动拉起；不要删除状态以绕过待确认保护。自定义状态目录须调整以上路径。

## 网络与认证

首次登录正常 DNS 优先，只有 VPN 主框架尚未恢复的 `ERR_NAME_NOT_RESOLVED`、`ERR_CONNECTION_CLOSED`、`ERR_CONNECTION_RESET` 才使用备用 IP 重启一次；普通超时、证书错误、凭据错误、其他域名和子资源失败不回退。后续业务不自动换 IP。保留域名证书校验，不改系统 DNS／Clash；远端解析的代理可能忽略映射。

学校遗留 HTTP 回调在浏览器内用本地 307 响应升级到同主机 HTTPS，原始 HTTP 请求不发送，查询中的 service 标识保持原样；其他 HTTP 请求阻断。凭据只在受信学校 HTTPS 页面填写，诊断不输出原始 Playwright 日志，不自动保存认证页面和截图。

会话失效时先尝试重登；无法完成时保留任务、停止业务并按邮件配置通知。不提供短信发送、短信输入或远程桌面。学校不要求人工操作是自动运行的条件，程序不能保证这一点。

## 开发与验收

```shell
uv run --locked python -m unittest discover -s tests -v
```

离线测试用临时配置、替代业务对象和 Playwright 管理的 Chromium 构造页面；全部页面请求被拦截，不读取真实 `.env`。覆盖模式、浏览器缺失提示、登录清理、HTTPS 本地重定向、网络回退、目标与冲突、待确认提交、任务锁、重启、邮件失败和按 ID 操作。`captcha_ocr.py` 共用模式采集样本，`captcha_fetch.py` 保留离线评估；`image/`、`images/` 素材保持原状。

2026-10-18 实施检查：69 项离线测试通过；十个源文件通过 mypy（`--check-untyped-defs`），锁文件和已安装依赖兼容性检查通过。模式参数与本地完成后重新核对均有回归检查。审查发现的重叠记录掩盖已结束未决状态、非 ASCII 验证码误入待确认两项问题已修复并覆盖回归。本轮未访问学校或发送真实邮件。

2026-10-18 授权只读验收：Windows 本机有头／无头均完成真实登录、全部活动记录读取与候选列表校验，包括遗留回调的 HTTPS 升级。未提交或取消预约、未发测试邮件、未修改真实 `.env`。Linux、真实预约、实际 OCR、人工认证场景、跨天及至少二十四小时运行仍待验收。

2026-10-18 后续浏览器调整：按用户确认统一使用 Playwright 管理的 Chromium，移除系统 Chrome 发现，增加缺失时的安装提示。Windows 临时浏览器缓存下 69 项离线测试通过，包含有窗口和无窗口构造页面；未访问学校、未发真实邮件。以上 Chrome 真实验收属于切换前记录，不能作为 Chromium 真实登录已通过的证据。

2026-10-18 邮件调整：确认每位用户可选配置自己的发件邮箱，收件人默认自己；增加中文通知和北京时间 20:00 汇报。完整 75 项离线测试通过，覆盖跨日、重启去重、退避期间汇报和待确认结果保护；文档链接检查通过，未访问学校或发送真实邮件。

目标、状态和邮件代码来自维护者 HTTPS 项目的 `96b9c5c`，两仓库无运行时依赖，源项目未改。文档：[改造需求](browser-upgrade-requirements.md)、[ADR 0001](adr/0001-browser-only-reservations.md)、[词汇表](../GLOSSARY.md)、[历史评估](design-assessment.md)、[历史网络规格](network-recovery-requirements.md)。
