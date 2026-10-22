# 配置与排错指南

[返回 README](../README.md) · [English](usage.en.md)

首次安装和后台启动按 README 操作；本页用于查配置、看状态和处理故障。业务约束与待验收事项见[浏览器规格](browser-upgrade-requirements.md)。

## 命令速查

| 命令 | 用途 |
| --- | --- |
| `uv run main.py` | 开始或恢复真实预约，默认显示窗口 |
| `uv run main.py --headless` | 无窗口运行；也可与 `--check` 组合 |
| `uv run main.py --check` | 登录、校验个人记录和讲座列表；不提交、不发邮件、不创建或改写任务 |
| `uv run main.py --status` | 查看本地状态和进程锁，不启动浏览器、不要求学校凭据 |
| `uv run main.py --test-mail` | 真实发送一封测试邮件，不登录学校、不创建任务 |
| `uv run main.py --new-task` | 兼容入口，重新核对已完成目标；不重置活跃或待确认任务 |

普通启动每次都会登录学校核对进度，即使本地曾完成，也无需先加 `--new-task`。`--check` 不打开预约弹窗、不验证 OCR 或真实提交。`captcha_ocr.py` 用于采集验证码样本，也默认显示窗口，可加 `--headless`；`captcha_fetch.py` 用于离线评估。

## 完整配置

项目自动读取根目录 `.env`，进程环境变量优先；改配置后重启。只合并需要的项，保留已有凭据。注释模板见 [.env.example](../.env.example)。

| 环境变量 | 含义与默认值 |
| --- | --- |
| `SEU_CARD_NUMBER`、`SEU_PASSWORD` | 学校账号和密码；预约及只读检查必填 |
| `SEU_PREFERRED_LECTURES` | 完整标题数组，默认 `[]` 不限制；其他筛选仍生效 |
| `SEU_REQUIRED_CATEGORIES` | 候选白名单及顺序，默认心理健康、法律、艺术、其他、SEU 咖啡间沙龙；不能空或重复；不改变三类必需项 |
| `SEU_PREFERRED_CAMPUS` | 线下校区白名单，默认 `[]` 不约线下 |
| `SEU_ENABLE_OFFLINE`、`SEU_ENABLE_ONLINE` | 线下／线上开关，默认均为 `true` |
| `SEU_STATE_DIR` | 私有状态目录，默认项目下的 `state`；可用绝对路径 |
| `SEU_VPN_IP` | 首次登录备用 IPv4／IPv6；内置为空，模板预填历史地址 `121.249.14.2` |
| `SEU_TIMEOUT_PAGE_LOAD` | 登录导航后的额外等待，默认 0.5 秒 |
| `SEU_TIMEOUT_ELEMENT_WAIT` | 页面、数据、操作和结果显示的等待上限；内置 3 秒，模板 15 秒 |
| `SEU_TIMEOUT_LOGIN_REDIRECT` | 认证跳转上限；内置 30 秒，模板 60 秒 |
| `SEU_TIMEOUT_SCAN_INTERVAL` | 正常扫描和待确认查询间隔，默认 10 秒，必须大于零 |
| `SEU_TIMEOUT_ACTION_CONFIRM` | 提交后基础等待，默认 0.2 秒；之后仍核对活动 ID |
| `SMTP_USERNAME`、`SMTP_PASSWORD` | 完整发件邮箱和授权码／应用专用密码 |
| `SMTP_HOST`、`SMTP_PORT` | 主机可按邮箱域名识别；默认隐式 TLS 端口 465 |
| `MAIL_FROM`、`MAIL_TO` | 发件和单个收件地址；默认账号自己给自己发信 |

列表用单引号包裹的 JSON 数组，例如 `SEU_PREFERRED_CAMPUS='["无锡校区"]'`；开关只用 `true/false`。密码建议加单引号，尤其包含空格或 `#` 时。时间单位为秒，须有限且非负；Playwright 超时为零会转为 1 毫秒，不表示无限等待。

旧 `SEU_HEADLESS` 不再生效，浏览器模式只看命令行。`SEU_TIMEOUT_RETRY_DELAY` 仅兼容读取，业务失败统一退避；旧配置中的 0.05 秒扫描不会自动变为 10 秒。备用 IP 可能过期，失效时更新或清空；仅增加等待不能解决断线或认证受阻。

沙龙的准确类别名是 `“SEU咖啡间”系列沙龙活动`；兼容旧代码的混合引号写法。已有 `.env` 不会随默认值自动扩充，需要将该类别加入现有 JSON 数组。缩小候选白名单不删除已参加的计数；旧沙龙历史重新参与目标统计，缺少打卡结论或必要字段时同样暂停新增。

加速范围为页面提供的预约开始时间前 30 秒至后 60 秒，整轮目标周期 1 秒，扣除本轮查询和操作耗时；超时则立即开始下一轮，不并发。普通等待会提前结束以进入加速窗口；缺少预约时间时普通扫描，本地时钟只用于调度，真正可约以新读取的页面按钮为准。待确认查询及限流、失败退避不被缩短。

标题包含“系统测试”“请勿预约”或“购票”的活动作为测试／公告排除，不参与日常预约和目标计数，即使学校把购票公告归为沙龙。明确授权的真实测试须核对活动 ID 和可约按钮；提交后核对预约结果，测试结束立即取消并再次核对，不能取消测试前已有的预约，也不包含付款。

### 开抢前检查与成功边界

预约开放时间与讲座举办时间不同，以 `activity_details` 中的 `reservation_start` 为准。例如北京时间 19:00 开放时，加速窗口为 18:59:30 至 19:01:00。每轮仍顺序读取个人记录与活动列表，一秒只是目标周期；查询、页面操作和网络耗时可能超过一秒。预检会复用刚完成扫描的页面并核对可约按钮，不能提前提交或保证抢到名额。

更新代码或配置后，先按 README 停止旧实例，确认 `process_running=false` 并保留 `state/`；运行 `uv run main.py --check --headless` 后再启动。只读检查通过不代表旧后台进程已加载新代码。启动后检查 `last_query_at` 持续更新、`failure_count=0`，核对候选筛选原因；`reservation_not_started` 是首个命中原因，不证明开放后一定通过类别、目标、校区和冲突筛选。`pending` 表示结果待确认，应保留保护并核对原预约，不删除状态或另开实例。

OCR 模型在首次取得验证码时加载，首次提交包含初始化耗时。识别输出无效或页面明确提示验证码错误时，最多尝试四次，耗尽后该场冷却五分钟；提交结果不明则仅核对原活动，不盲目重发。开抢期间延后运行问题汇总邮件，网络故障和限流仍退避。离线测试和一次真实测试成功不能推导热门讲座的成功率；名额竞争、验证码和学校响应仍可能导致漏约。事后用本地 `scan_timing`、预检与提交诊断定位，缺少历史证据时不能确认上次漏约原因。

### 校区识别与指定活动测试

程序先从标题开头的 `【线上】`／`【线下】` 判断授课方式，不根据标题正文、地点中的“线上”字样或城市猜测。普通候选缺少这个标记时按 `invalid_activity_data` 跳过并告警，不默认归为线下，也不阻断其他候选。

校区来自学校地点字段 `JZDD`：用 `^(.+?校区)` 提取从开头到第一个“校区”的文字；没有匹配时保留完整地点。只校验地点非空，不去除前后空格、不转换校区别名，也不根据场馆地址推断校区。

| 标题标记 | 学校地点示例 | 校区处理 |
| --- | --- | --- |
| `【线下】` | `无锡校区某教室` | 提取 `无锡校区`，与 `SEU_PREFERRED_CAMPUS` 精确匹配 |
| `【线下】` | `九龙湖校区某报告厅` | 提取 `九龙湖校区`；仅允许无锡时排除 |
| `【线下】` | `某剧场` | 保留 `某剧场`；不会自动归入无锡或其他校区 |
| `【线上】` | `线上会议` | 不受校区白名单限制，仍须满足其他候选校验与筛选 |

购票公告即使属于 `.env` 允许的沙龙类别，也会先命中 `notice_test_only`，不进入普通讲座及校区解析。已验证的 `【一“剧”钟情】` 购票优惠活动没有 `【线上】`／`【线下】` 前缀，因此不能依据它的测试预约结果推断校区归属。其学校地点原文未在本次核对中确认，不在文档中指定实际校区。

该次真实测试是在明确授权后，用临时脚本按完整标题取得唯一活动 ID，直接复用 `BrowserClient` 的预检、验证码和提交链路，没有执行常驻任务的 `select_candidates()`。没有修改 `.env` 或放宽日常筛选；成功后已取消并复核。它证明提交与取消链路可用，不能证明日常类别／校区筛选、完整自动预约流程或热门活动抢约时效。临时脚本已删除，测试记录仅保留在本地 `state/`；本项目不提供绕过日常筛选的常规测试命令。

## 邮件配置

每人使用自己的发件账号，一次配置一个。不要分享授权码。全部邮件字段留空可关闭通知，单独保留 `SMTP_PORT=465` 仍关闭；填写了部分信息但不完整时会阻止启动。

### 取得发信密码

| 发件邮箱域名 | 自动使用的主机 | `SMTP_PASSWORD` |
| --- | --- | --- |
| `qq.com` | `smtp.qq.com` | SMTP 授权码 |
| `163.com` | `smtp.163.com` | SMTP 授权密码 |
| `126.com` | `smtp.126.com` | SMTP 授权密码 |
| `gmail.com` | `smtp.gmail.com` | 应用专用密码 |

**QQ**：

1. 在电脑浏览器登录 [QQ 邮箱](https://mail.qq.com/)。手机浏览器如显示简版，先在设置中切换到标准版。
2. 打开“设置 → 账号与安全 → 安全设置”；旧版入口为“设置 → 帐户”。
3. 向下找到“POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV 服务”，开启包含 SMTP 的服务。已开启时，进入“管理服务 → 生成授权码”，保留已有服务。
4. 按页面提示完成安全验证，复制生成的授权码。`SMTP_USERNAME` 填完整 QQ 邮箱，`SMTP_PASSWORD` 填授权码。

不同版本的入口名称可能有差异，参考华为支持的[账号与安全操作说明](https://consumer.huawei.com/cn/support/content/zh-cn00696857/)及[获取授权码图文步骤](https://consumer.huawei.com/cn/support/content/zh-cn00692809/)。后者也说明了服务已开启时如何生成新授权码。

**163／126**：登录 [163 邮箱](https://mail.163.com/)或 [126 邮箱](https://mail.126.com/)，在“设置 → POP3/SMTP/IMAP”开启 SMTP，选择“新增授权密码”，按提示完成验证。账号填写完整邮箱，密码填写生成的授权密码。可参考[网易授权密码教程](https://help.mail.126.com/faqDetail.do?code=d7a5dc8471cd0c0e8b4b8f4f8e49998b374173cfe9171305fa1ce630d7f67ac286624f309a1a7089)。

**Gmail**：

1. 登录 [Google 账号安全设置](https://myaccount.google.com/security)，开启“两步验证”。
2. 打开[应用专用密码](https://myaccount.google.com/apppasswords)，为本项目创建密码，例如命名为 `SEU Lecture Reserve`。
3. 复制 16 个字符，去掉分组空格。完整 Gmail 地址填入账号，生成的密码填入 `SMTP_PASSWORD`。

Gmail 应用专用密码只显示一次，丢失或更改 Google 登录密码后需重新生成。找不到入口时，确认登录账号和两步验证状态；组织限制、高级保护或仅安全密钥验证可能影响可用性，见 [Google 说明](https://support.google.com/accounts/answer/185833?hl=zh-Hans)。无法使用时可选择其他发件邮箱或关闭邮件。

### 填写并测试

```dotenv
SMTP_USERNAME=your-address@qq.com
SMTP_PASSWORD='your-authorization-code'
SMTP_HOST=
SMTP_PORT=465
MAIL_FROM=
MAIL_TO=
```

`SMTP_HOST` 留空时按上表匹配域名，不区分大小写；显式主机优先。其他域名、别名或自建邮箱须填写服务商提供的主机名，不含 URL、端口或路径。换邮箱时清空或更新旧主机。`MAIL_FROM` 默认发件账号，覆盖须获服务商允许；`MAIL_TO` 默认发给自己，可改为一个其他邮箱，如 `recipient@gmail.com`。

保存 `.env`，停止旧实例，运行 `uv run main.py --test-mail`，确认收件箱收到后再恢复预约。`event=test_mail_accepted` 只表示 SMTP 接受，不能证明送达。测试邮件的错误只显示在终端，不写入任务状态。

当前使用校验证书的 `SMTP_SSL`，默认 465，也支持无需认证的 TLS 中继；不支持 STARTTLS、明文 SMTP 或 OAuth。不要直接改为 587。Gmail API、网页登录发信和 SSH 邮件转发均未接入。

### 通知规则

- 页面／查询异常、预检失效、无效 OCR、验证码错误、提交被拒或结果不明另发 `runtime_problem` 汇总，不等到三次失败。同类问题十五分钟内合并且跨重启保留限频，失败不自动重发；正常的未开放、已满筛选不发信。开抢期间先完成预约和确认，问题邮件在恢复普通扫描、退避或退出时发送。

- 单场预约成功、目标完成、人工认证、提交待确认和可捕获异常退出会通知；连续三轮查询或处理失败告警，完整恢复后通知一次。正常轮询不发信。
- 人工认证、待确认和连续失败的未解决告警跨重启去重，发送失败或结果不明均不自动重发；关闭邮件不消耗新的告警配额。查询失败告警至少相隔 15 分钟，间隔跨重启保留。
- 运行期间每天北京时间 20:00 汇报。同一状态目录每天最多尝试一次；20:00 后启动在首次等待时补发当天，不补更早日期。页面操作可能延迟发送；汇报不会提前结束业务退避，停止或完成退出后不再发送。
- 通知包含最近核对的整体进度、数据时间、安全错误码和下次检查计划；未知数据明确标记，不包含凭据、讲座详情或完整个人记录。待确认模式的“查询已恢复”不等于预约成功。
- 邮件在主线程同步发送，每封重新连接认证。20 秒是网络操作超时，不是整封邮件总时限；发信失败不会改变预约结果。用下方耗时字段评估是否影响扫描。

## 状态与筛选原因

执行 `uv run main.py --status`。它显示本地快照，不能代替学校当前记录；查询失败或等待参加期间，部分内容可能不更新。

| 字段 | 怎么看 |
| --- | --- |
| `process_running`、`phase` | 进程是否运行及当前阶段；停止时 `last_phase` 保留退出前阶段 |
| `last_query_at`、`last_error`、`failure_count` | 最近成功查询、安全业务错误码、连续失败次数 |
| `next_check_at` | 下一次计划检查时间 |
| `selection_updated_at`、`activity_details` | 最近筛选时间、逐场标题、首个命中原因和预约起止时间；缺失或未校验时间为 `null` |
| `mail_status`、`last_mail_status` | 当前邮件状态和最近尝试结果；`accepted` 仅为 SMTP 接受，`sending` 结果未明，`failed` 失败，`never` 无记录 |
| `last_mail_at`、`last_mail_error` | 最近运行邮件尝试时间和错误分类；新尝试或成功为 `none`，旧失败缺分类为 `unknown` |
| `last_mail_event`、`last_mail_duration_seconds` | 最近运行通知事件与耗时；旧记录或未结束尝试的耗时为 `unknown` |

邮件历史跨重启及关闭邮件保留；已丢失的旧证据不能补回。`scanning/pending/done` 只说明任务状态，不能单独证明运行健康。活动详情只保存在私有状态，不写事件日志或邮件；不要公开含详情的输出。

| 筛选原因 | 含义 |
| --- | --- |
| `candidate` | 通过筛选，尚未预约成功 |
| `notice_test_only` | 测试／购票公告，只能在明确授权的测试中操作 |
| `invalid_activity_data` | 该条候选校验失败，跳过并告警，继续检查其他活动；具体错误码保存在私有诊断的 `validation_error` |
| `reservation_not_started`、`capacity_full` | 学校标记未开放／人数已满 |
| `not_reservable` | 页面无可预约标记，具体原因未知 |
| `already_reserved` | 学校记录已预约 |
| `category_not_allowed`、`category_not_needed` | 不在配置类别／当前目标暂不需要 |
| `title_not_selected`、`campus_not_selected` | 标题／线下校区不匹配 |
| `online_disabled`、`offline_disabled` | 对应授课方式已关闭 |
| `time_conflict`、`cooldown` | 与有效预约冲突／验证码失败后冷却中 |

私有 `state/diagnostics.jsonl` 追加保留筛选变化（含活动 ID）、预检结果、OCR 无效／冷却、每次提交及其结果分类、确认成功和耗时，不保存验证码、凭据或原始服务器错误。加速扫描逐轮记录查询耗时和等待，普通扫描每五分钟采样一次；标题和 ID 不输出到运行事件日志或邮件。旧日志无法补出此前漏约的原因；诊断文件随状态目录保留，应仅在本地按需归档。

## 排错步骤

1. 用 `--status` 看进程、查询时间和错误；只读检查输出也可用于定位。停止旧实例，保留 `state/`。
2. 按下面对应情况处理，避免同时改多个设置。
3. 修复后先运行 `uv run main.py --check`；服务器加 `--headless`。看到 `read_only_complete` 再启动真实预约。邮件另用 `--test-mail` 验证。

### 登录或页面失败

未找到 Chromium 时重新执行 README 的浏览器安装命令；Linux 只缺运行库时可用 `uv run playwright install-deps chromium`。浏览器在安装账号的缓存中，有窗口运行需要图形环境。

白屏、持续加载、`page_not_ready`、`history_navigation_failed`：检查学校页面能否手动加载和切换“我的活动／全部”，再看网络与代理日志。慢加载可采用模板的 15 秒元素等待和 60 秒认证等待；断线或页面结构变化不能只靠增加超时解决。

`invalid_activity_data`：单条候选缺少必要字段、有效时间或标题开头的【线上】／【线下】标记时，跳过该条并继续筛选。`--check` 输出警告和逐条原因后仍可显示 `read_only_complete`，表示读取完成，不表示每条数据都有效；它不发邮件或写入状态。正常运行将原因存入私有状态和 `diagnostics.jsonl` 的 `validation_error`，例如 `interval_invalid` 表示活动时间倒置；事件日志只记通用错误码。配置邮件时复用十五分钟合并告警，开抢期间延后，不因单条异常进入整轮退避。明确非目标类别可先排除；个人预约记录仍完整校验，无法可靠判断冲突时暂停新增。

活动开始和结束时间相同可以通过校验，按一个时间点参与冲突判断，不自动补时长；结束早于开始、缺失或无法解析仍视为异常。相同时间点在已预约历史中也按该规则处理，未打卡且到达结束时间后仍暂停新增、等待结果核实。真实持续时长需自行确认，晚于记录时间点的冲突可能无法识别。预约开放／截止时间是另一组字段，仍要求截止晚于开放，不放宽为相同时间。

首次登录优先正常 DNS。仅 VPN 主框架出现 `ERR_NAME_NOT_RESOLVED`、`ERR_CONNECTION_CLOSED`、`ERR_CONNECTION_RESET` 且登录最终失败时，才使用 `SEU_VPN_IP` 重启一次。普通超时、证书、凭据和其他资源错误不回退，后续业务不自动换 IP。它不修改系统 DNS 或 Clash，代理远端解析时映射可能无效。

`host=<unknown>` 只表示域名不在日志允许显示的学校域名中。深信服本机客户端探测失败会合并提示，不代表学校查询失败。会话失效可尝试重登；人工认证受阻时保存任务并退出，不提供短信发送、输入或远程桌面。

`browser_closed`：浏览器断连或页面关闭，程序保留任务、按配置告警后退出。若正在提交会保留 `pending`，重启后先核对原活动。服务器改用 README 的 systemd 方式；单独忽略 Python 的挂断信号不足以保护整个浏览器进程树。

### 邮件失败

| `reason` / `last_mail_error` | 处理方向 |
| --- | --- |
| `dns_failed` | 检查 SMTP 域名解析 |
| `connection_failed`、`network_failed` | 检查主机、端口和网络路径；断开不能证明邮件未被接受 |
| `tls_failed` | 检查端口、证书、代理和上游；EOF 也归此类，不等于密码错误 |
| `timeout` | 网络操作超时，单凭分类无法确定 TCP、TLS 或 SMTP 阶段 |
| `authentication_failed` | 检查账号及授权码／应用专用密码 |
| `sender_refused`、`recipient_refused`、`message_rejected` | 检查收发地址、服务商权限和内容限制 |
| `smtp_failed`、`unknown` | 其他协议错误或缺少分类，不能从旧日志猜测原因 |

网页 HTTPS 可访问不代表 SMTP 可用。先在实际运行网络测试，必要时对比校园网、热点和代理开关；换邮箱不保证修复网络限制。当前 SMTP 不自动读取 `HTTP_PROXY`、`HTTPS_PROXY` 或 `ALL_PROXY`，TUN 仍可能接管连接。

需要定位时，先做不认证、不发信的 DNS、TCP、TLS、SMTP 问候检查；对相同目标 IP 对比路径时保留 SMTP 域名的 TLS 身份和证书校验。检查代理实际运行状态和日志，关闭窗口不等于退出内核，Fake-IP 也不单独证明 DNS 错误。临时网络改动后恢复原设置；不要关闭证书校验掩盖故障。

### 旧后台实例与恢复

旧版用 `nohup` 的实例先核对 PID、命令和工作目录：

```bash
reserve_pid=$(cat state/runner.pid)
ps -p "$reserve_pid" -o pid,args
readlink "/proc/$reserve_pid/cwd"
```

只有确认属于本项目，才执行 `kill "$reserve_pid"`。PID 失效或属于其他进程时不要终止。再用 `uv run main.py --status` 确认 `process_running=false`，保留状态、完成只读检查，然后按 README 启动 systemd 服务。

锁只覆盖同一状态目录，换机器前先停止旧实例；新机器可直接读取学校记录，无需迁移状态，但不保证跨机器提交去重。本机恢复应保留待确认、冷却与退避状态。`runner.log` 和 `events.log` 持续追加，留意磁盘空间；停止 systemd 服务最多等待 60 秒清理，超时会强制结束。

## 开发检查

```shell
uv sync --locked
uv run playwright install chromium
uv run --locked python -m unittest discover -s tests -v
```

Linux 按 README 安装浏览器运行库。仅查配置可执行 `uv run --locked python -m unittest discover -s tests -p test_config.py -v`。测试使用临时配置和本地构造页面，阻断外部请求，不读取真实 `.env`。源码导入不启动业务；不要为文档检查直接运行预约或样本采集入口。

[词汇表](../GLOSSARY.md) · [架构决策](adr/0001-browser-only-reservations.md) · [规格与验证边界](browser-upgrade-requirements.md)
