# 使用与维护指南

[返回首页](../README.md) · [English](usage.en.md)

## 完整配置

编辑项目根目录的 `.env` 后重新启动。程序自动加载该文件，已有进程环境变量优先；没有 `.env` 时也可完全通过环境变量配置。全部配置见 [.env.example](../.env.example)，其中 VPN 备用 IP 为预填样例值，其余为默认值。

| 环境变量 | 含义与默认值 |
| --- | --- |
| `SEU_CARD_NUMBER`、`SEU_PASSWORD` | 必填的一卡通号和密码 |
| `SEU_VPN_IP` | 可选的学校 VPN 备用 IPv4／IPv6 地址；未配置时默认空，样例预填 `121.249.14.2`；正常 DNS 优先，首次登录网络故障时最多回退一次 |
| `SEU_PREFERRED_LECTURES` | 精确匹配的标题数组；默认 `[]`，使用常规筛选 |
| `SEU_REQUIRED_CATEGORIES` | 类别白名单；默认五类，名称见配置样例；空数组不匹配任何类别 |
| `SEU_PREFERRED_CAMPUS` | 校区白名单；默认 `[]`，不匹配线下讲座 |
| `SEU_ENABLE_OFFLINE`、`SEU_ENABLE_ONLINE` | 线下、线上预约开关；默认均为 `true` |
| `SEU_TIMEOUT_PAGE_LOAD` | 登录导航或异常恢复刷新后的额外等待，默认 0.5 秒 |
| `SEU_TIMEOUT_ELEMENT_WAIT` | 导航、元素操作和预约确认的默认超时，默认 3 秒 |
| `SEU_TIMEOUT_LOGIN_REDIRECT` | 提交登录后等待返回预约页的最长时间，默认 2 秒；人工短信认证时可设为 60 |
| `SEU_TIMEOUT_SCAN_INTERVAL` | 每轮扫描后的额外等待，默认 0.05 秒，不是整个扫描周期 |
| `SEU_TIMEOUT_RETRY_DELAY` | 重试间隔，默认 0.05 秒 |
| `SEU_TIMEOUT_ACTION_CONFIRM` | 提交预约后的基础等待，默认 0.2 秒；随后按元素超时核对目标按钮 |

列表使用 JSON 数组，并在 `.env` 中用单引号包裹；开关使用 `true` / `false`。例如：

```dotenv
SEU_PREFERRED_CAMPUS='["无锡校区"]'
SEU_PREFERRED_LECTURES='[]'
SEU_ENABLE_OFFLINE=true
SEU_ENABLE_ONLINE=true
SEU_TIMEOUT_LOGIN_REDIRECT=60
```

账号、密码含空格或 `#` 时使用引号包裹。未设置的可选变量使用默认值；列表、开关或数字留空会报错。等待时间必须是有限非负数，扫描间隔须大于零；配置错误会在打开浏览器前报出。

配置的时间单位为秒。程序转换为 Playwright 毫秒；等待超时为 0 时使用 1 毫秒，避免无限等待。网络较慢时可增大 `SEU_TIMEOUT_ELEMENT_WAIT`；增加 `SEU_TIMEOUT_PAGE_LOAD` 不能延长导航超时。

## 网络诊断与备用 IP

样例已预填 2026-10-16 经公共 DNS 和 HTTPS 连通性核实的 `SEU_VPN_IP=121.249.14.2`；程序仍优先使用正常 DNS，清空此项即可禁用备用地址回退。学校地址变化后需要重新核实并更新。修改样例不会自动更新已有 `.env`，请按需手动同步后重启。该项接受单个 IPv4 或 IPv6 字面地址及首尾空白；域名、URL、端口、IPv6 作用域标识及其他无效输入会在打开浏览器前报配置错误，不回显输入。已有进程环境变量仍优先。

两个入口首次启动都使用正常 DNS。只有首次登录失败，且该次登录尚未恢复的学校 VPN 主框架导航出现 `ERR_NAME_NOT_RESOLVED`、`ERR_CONNECTION_CLOSED` 或 `ERR_CONNECTION_RESET`，才关闭原浏览器，以备用 IP 重启一次并从讲座入口重新登录。重启不迁移登录状态，可能再次要求短信认证；备用尝试仍失败即退出。正常登录成功、没有备用地址、证书错误、普通等待超时、凭据或短信失败，以及子资源、子框架或其他域名失败，都不会触发回退。

控制台网络诊断使用 `host=学校域名 reason=安全错误类型`；未知主机或错误以固定类别显示，不输出完整跳转 URL、票据、Cookie、凭据或 Playwright 原始调用日志。连接关闭／重置不等于已经证实 DNS 故障。

备用地址只覆盖本程序的 `vpn.seu.edu.cn`，保留 HTTPS 域名与证书校验，不修改系统 DNS、Clash 或其他网站路由，不自动发现地址。地址可能过期，不能保证解决所有连接或认证问题；显式代理在代理端解析域名时，本地覆盖也可能不生效，程序不会为此自动绕过代理。

首次登录完成后，扫描、预约、验证码采集及原有重新登录路径仅增加网络诊断，不自动切换 IP 或重启浏览器。本功能不改变现有预约重试和确认策略；提交后结果不明时仍需在学校系统核对。

## 筛选与结果确认

常规模式按类别、校区、线上线下开关及当前页面的已预约时间筛选。标题含“线上”即视为线上讲座，可绕过校区白名单，但仍受类别及线上开关等条件限制。

`SEU_PREFERRED_LECTURES` 非空时，标题精确命中且按钮为“预约”就通过筛选，跳过类别、校区、线上线下开关和时间冲突检查。需要这些约束时保持 `[]`。

每轮只尝试排序第一场，每次调用最多尝试三次，失败后继续扫描。成功要求目标讲座按钮变为“取消预约”；无法唯一定位同名讲座时暂缓提交。程序确认一场成功后退出，最终结果请在学校系统核对。

现有限制：

- 时间冲突只检查当前页面；解析失败的讲座可能被跳过，检查异常仍按无冲突处理。
- 线上讲座优先于线下；校区列表顺序不决定优先级。
- 第一候选持续失败可能阻塞后续候选；会话失效也可能被当作空列表。
- 成功确认依赖目标卡片更新；网页改版、网络和名额均可能影响预约。OCR 准确率与扫描性能未重新测量。

## 常见问题

| 情况 | 处理方式 |
| --- | --- |
| 找不到 Chrome | 安装或修复 Google Chrome；无需 ChromeDriver 或额外下载 Playwright Chromium |
| 短信认证来不及完成 | 将 `SEU_TIMEOUT_LOGIN_REDIRECT` 设为 60 或更长，重新启动并在可见浏览器中操作 |
| 导航或元素操作超时 | 检查网络，适当增大 `SEU_TIMEOUT_ELEMENT_WAIT` |
| 学校 VPN 解析失败、连接关闭或重置 | 根据安全网络诊断检查网络／Clash；必要时填写已核实的 `SEU_VPN_IP`，首次登录最多重启一次。不要关闭证书校验 |
| 一直提示没有讲座 | 检查校区、类别及开关；标题模式须完全匹配。若浏览器已回到登录页，停止后重新启动 |
| 登录失败 | 先区分网络诊断与浏览器中的认证状态；本地 `error_page_source.html`、`error_login.png` 可辅助排查，含认证信息时勿上传 |

## 浏览器与停止

两个入口共享 `browser.py` 的 Playwright 同步 API，使用本机 Chrome。Windows 通过注册表 App Paths 补充发现非默认安装位置（包括已注册的 Scoop 安装），其他平台使用 Chrome 通道的标准位置。启动配置排除 `--enable-logging`。

浏览器默认可见；若无需人工认证，可在 `browser.py` 将 `headless` 改为 `True`，同时影响两个入口。无界面模式不提供后台保活。最小化终端可继续运行，关闭终端通常会停止进程；强制结束可能残留浏览器。`Ctrl+C` 会尝试清理浏览器，停止程序不会撤销已成功提交的预约。

## 辅助脚本与开发

| 命令 | 作用 |
| --- | --- |
| `uv run captcha_ocr.py` | 登录真实系统，批量采集验证码到 `image_dataset/`；会打开浏览器 |
| `uv run captcha_fetch.py` | 使用 `image/` 中按正确验证码命名的图片离线评估 OCR |
| `uv run --locked python -m unittest discover -s tests -v` | 完整回归检查，需本机 Chrome；只使用空白页和内存构造页面，阻断页面外部请求 |
| `uv run --locked python -m unittest discover -s tests -p test_config.py -v` | 仅检查配置，无需浏览器；使用临时环境文件，不读取真实 `.env` |

uv 使用 `.python-version` 指定的 Python 3.11，在需要时下载解释器，依赖安装到 `.venv`，无需手动激活。依赖声明在 `pyproject.toml`，由 `uv.lock` 锁定；`uv run --locked main.py` 还会检查锁文件一致性。没有 `requirements.txt` 安装流程。

`main.py` 负责预约，`browser.py` 共享启动与登录，`config.py` 读取配置。导入 `main.py` / `captcha_ocr.py` 不读取配置、不初始化 OCR、不启动浏览器。两个 OCR 入口关闭第三方推广；主程序显示维护者和项目主页。

现有回归覆盖配置、启动清理、登录等待、首次登录备用 IP 回退、安全网络诊断及模拟页面预约流程；真实登录、短信认证和预约尚未完整验证，macOS/Linux 未实测。

`.env`、诊断页面/截图、生成样本和缓存仅留本地；旧 ChromeDriver 可删除。保留项目素材 `image/`、`images/`，示例配置使用不含真实凭据的 `.env.example`。

## 工程文档与来源

- [项目规则](../AGENTS.md)、[Issue tracker](agents/issue-tracker.md)、[分诊标签](agents/triage-labels.md)
- [领域文档](agents/domain.md)、[领域词汇](../GLOSSARY.md)、[原理与迁移评估](design-assessment.md)
- [首次登录网络回退规格](network-recovery-requirements.md)、[GitHub Issue #1](https://github.com/MuZiJin701/SEU_Lecture_Reserve/issues/1)

当前由 [MuZiJin701](https://github.com/MuZiJin701) 维护，主要工作包括 uv 与配置整理、Playwright 迁移、回归测试、依赖清理和文档。基于 [ApricityWang 的项目](https://github.com/ApricityWang/SEU_Lecture_Reserve)继续开发，保留原始作者及历史贡献。

本项目供学习 Python 自动化使用；请遵守学校规定，不进行破坏性操作或商业使用。开发者不对使用后果负责。
