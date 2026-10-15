# 东南大学讲座预约

[English](README.en.md)

东南大学人文与科学素养系列讲座预约自动化脚本，支持图形验证码识别、讲座筛选和需要人工参与的短信认证。基于 [ApricityWang/SEU_Lecture_Reserve](https://github.com/ApricityWang/SEU_Lecture_Reserve) 进行二次创作，本仓库独立维护。

当前维护者为 [MuZiJin701](https://github.com/MuZiJin701)，主要维护工作包括 uv 与环境配置整理、Playwright 迁移、回归测试、依赖清理及双语文档。原始项目与历史贡献保留其作者署名。

## 功能与运行流程

运行 `uv run main.py` 后，程序会自动读取项目根目录 `.env`，检查配置，初始化 OCR，并通过 Playwright 同步 API 打开本机 Chrome；随后填写账号密码，等待登录跳转或人工短信认证。登录成功后持续刷新讲座页面，筛选并尝试预约。

配置校验通过后，主程序显示项目名称、维护者和项目主页。主程序与离线 OCR 评估脚本均关闭 ddddocr 的第三方推广输出，保留运行进度、错误提示和 OCR 评估结果。

- 未指定讲座标题时，按类别、校区、线上线下开关和当前页面已预约讲座的时间冲突进行筛选。
- 没有合适讲座或预约失败时继续扫描；程序判断成功预约一场后退出并关闭浏览器。
- 成功提示要求目标讲座的按钮变为“取消预约”；重试只点击文字为“预约”的按钮。无法唯一定位同名讲座时暂缓预约，最终结果请在 [SEU 门户](https://ehall.seu.edu.cn/)确认。

## 快速开始

需要 [uv](https://docs.astral.sh/uv/getting-started/installation/) 和已安装的 Google Chrome。使用 [Playwright 的 Chrome 通道](https://playwright.dev/python/docs/browsers#google-chrome--microsoft-edge)，不再需要 ChromeDriver，也不需要下载 Playwright Chromium。Windows 还会从注册表 App Paths 自动发现非默认位置安装的 Chrome（包括已注册的 Scoop 安装），其他平台使用 Chrome 通道的标准发现方式；找不到 Chrome 时请先安装或修复 Chrome。

首次使用：

```shell
git clone https://github.com/MuZiJin701/SEU_Lecture_Reserve.git
cd SEU_Lecture_Reserve
uv sync --locked
cp .env.example .env
```

uv 使用 `.python-version` 指定的 Python 3.11，需要时自动下载解释器，在 `.venv` 中安装锁定依赖，无需手动激活虚拟环境。依赖声明在 `pyproject.toml`，锁定在 `uv.lock`，不再使用 `requirements.txt`。

编辑 `.env`，填写账号、密码及筛选条件；已有 `.env` 时保留原文件。然后在项目根目录运行：

```shell
uv run main.py
```

`.env`、生成的验证码样本、登录错误页面/截图和系统缓存均被 Git 忽略；旧 ChromeDriver 已不再使用，可以删除。只提交不含真实凭据的 [.env.example](.env.example)。项目素材 `image/`、`images/` 保留。

## 配置

程序通过 `python-dotenv` 自动读取与 `config.py` 同目录的 `.env`；已有进程环境变量优先。直接使用项目虚拟环境中的 Python 启动也会加载配置，无需 `--env-file`。`uv run --locked main.py` 会额外检查锁文件与项目配置是否一致，需要更新时直接报错。

全部变量和默认值见 [.env.example](.env.example)：

| 环境变量 | 含义与格式 |
| --- | --- |
| `SEU_CARD_NUMBER`、`SEU_PASSWORD` | 必填的一卡通号和密码；含空格、`#` 等字符的值使用引号包裹 |
| `SEU_PREFERRED_LECTURES` | 精确匹配的讲座标题数组；`[]` 表示使用常规筛选 |
| `SEU_REQUIRED_CATEGORIES` | 讲座类别白名单，JSON 字符串数组；空数组不会匹配任何类别 |
| `SEU_PREFERRED_CAMPUS` | 校区白名单，如 `'["无锡校区"]'`；须与系统名称完全一致 |
| `SEU_ENABLE_OFFLINE`、`SEU_ENABLE_ONLINE` | 线下、线上预约开关，使用 `true` 或 `false` |
| `SEU_TIMEOUT_PAGE_LOAD` | 页面加载后的基础等待时间，默认 0.5 秒 |
| `SEU_TIMEOUT_ELEMENT_WAIT` | 页面导航、元素操作和预约状态确认的默认超时，默认 3 秒 |
| `SEU_TIMEOUT_LOGIN_REDIRECT` | 提交登录后等待返回预约页的最长时间，默认 2 秒；人工短信认证时可临时改为 60，跳转完成即可继续 |
| `SEU_TIMEOUT_SCAN_INTERVAL` | 每轮扫描后的额外等待，默认 0.05 秒；不是整个扫描周期 |
| `SEU_TIMEOUT_RETRY_DELAY` | 重试等待，默认 0.05 秒 |
| `SEU_TIMEOUT_ACTION_CONFIRM` | 提交预约后的基础等待，默认 0.2 秒；随后最多等待 `SEU_TIMEOUT_ELEMENT_WAIT` 秒核对目标按钮 |

列表使用 JSON 数组，整个数组在 `.env` 中以单引号包裹，例如：

```dotenv
SEU_PREFERRED_CAMPUS='["无锡校区"]'
SEU_PREFERRED_LECTURES='[]'
SEU_ENABLE_OFFLINE=true
SEU_ENABLE_ONLINE=true
SEU_TIMEOUT_LOGIN_REDIRECT=60
```

未设置的可选变量使用程序默认值；留空不等于未设置，列表、开关和数字留空会报错。等待时间须为有限非负数，扫描间隔须大于零。缺少凭据或配置格式错误时，在创建浏览器前退出；没有 `.env` 时也可使用系统环境变量提供完整配置。

配置中的时间单位仍为秒；程序转换为 Playwright 的毫秒单位。等待超时设置为 0 时使用最短 1 毫秒，避免 Playwright 将 0 解释为无限等待。页面导航和元素操作共用 `SEU_TIMEOUT_ELEMENT_WAIT`，网络较慢时可增大该值；提交登录后的跳转等待单独使用 `SEU_TIMEOUT_LOGIN_REDIRECT`。`SEU_TIMEOUT_PAGE_LOAD` 仍是登录导航完成或异常恢复刷新后的额外等待，不是导航超时。

**标题指定模式的限制：**`SEU_PREFERRED_LECTURES` 非空时，标题命中且状态可预约就直接接受，跳过类别、校区、线上线下开关及时间冲突检查。这是当前行为；需要这些筛选时保持 `[]`。

常规模式下，校区列表默认为空，会过滤掉线下讲座。程序以标题包含“线上”判断线上讲座；线上讲座可绕过校区白名单，但仍受类别及线上开关等条件限制。

## 短信认证、停止与浏览器

- 浏览器默认可见。首次登录或认证失效时，设置足够的 `SEU_TIMEOUT_LOGIN_REDIRECT` 等待时间，在浏览器中手动完成短信认证，之后再恢复正常等待值。
- 按 `Ctrl+C` 停止，主程序会尝试关闭浏览器。最小化终端可继续运行；关闭承载程序的终端通常会终止进程，强制关闭可能残留浏览器。
- 当前以前台进程运行，没有后台保活或定时启动。停止程序不会撤销已经成功提交的预约。
- 主程序和采集脚本共享 `browser.py` 中的 Chrome 自动发现、登录和启动配置，并排除 `--enable-logging`。脚本自身输出保留。
- 无界面运行可将 `browser.py` 的 `headless` 改为 `True`，同时影响两个入口；需要人工短信认证时保留 `False`。无界面模式不等于后台保活。

## 辅助脚本与检查

| 命令 | 作用 |
| --- | --- |
| `uv run captcha_ocr.py` | 使用相同配置登录真实系统，批量采集验证码到 `image_dataset/`；会打开浏览器，不是离线检查 |
| `uv run captcha_fetch.py` | 对 `image/` 中以正确验证码命名的已有图片进行 OCR 评估，不需要登录凭据 |
| `uv run --locked python -m unittest discover -s tests -v` | 配置、启动清理、登录等待和预约回归检查；需本机 Chrome，只使用 `about:blank` 与内存页面，不访问预约系统或读取真实 `.env` |

`main.py` 是预约入口，`browser.py` 共享浏览器启动和登录，`config.py` 负责配置读取与校验。导入 `main.py` 或 `captcha_ocr.py` 不读取配置、不初始化 OCR、不启动浏览器；执行脚本才开始运行。仅检查配置可运行 `uv run --locked python -m unittest discover -s tests -p test_config.py -v`，无需浏览器。修改启动或配置行为时同步更新中英文 README 和 [.env.example](.env.example)。

## 验证与已知限制

迁移验证覆盖配置、Chrome 自动发现、毫秒转换、登录等待、异常清理，以及真实 Chrome 空白页上的讲座解析、筛选、延迟成功确认、重试、页面重排和同名讲座保护。配置测试不读取真实凭据；浏览器测试使用本地构造页面并阻断外部请求。未完整验证真实登录、短信认证和预约，也未在 macOS/Linux 实测。OCR 沿用原模型，准确率未重新测量，不保证每次识别成功。

预约系统网页结构、网络状态、页面等待时间和可用名额均会影响结果。时间冲突检查只依据当前页面识别到的已预约讲座；请自行确认完整日程，并遵守学校规则、合理设置扫描间隔。

本轮保留原筛选和排序规则：标题模式仍跳过其他筛选、时间冲突读取异常仍按无冲突处理、线上优先于线下、每轮只尝试第一候选；会话过期也可能被当作空列表。这些限制不会因迁移框架自动消失。成功确认依赖目标卡片更新，若系统改为仅显示弹窗而不更新卡片，需要调整确认方式。

## 工程协作配置

- [项目规则](AGENTS.md)：工程 Skills 的入口及安全验证约定。
- [Issue tracker](docs/agents/issue-tracker.md)：任务和规格记录在[本仓库 Issues](https://github.com/MuZiJin701/SEU_Lecture_Reserve/issues)。
- [Triage 标签](docs/agents/triage-labels.md)：五个默认标签及其含义。
- [领域文档](docs/agents/domain.md)：单一上下文，`GLOSSARY.md` 与 `docs/adr/` 按需创建。
- [领域词汇](GLOSSARY.md)与[原理及迁移评估](docs/design-assessment.md)：术语、已确认的 Playwright 迁移范围及后续改进空间。

可直接编辑 `docs/agents/*.md`；更换 tracker 或重新初始化时再运行 setup Skill。

## 免责声明

本项目仅供学习 Python 自动化技术，开发者不对使用后果负责。使用即表示同意遵守东南大学相关管理规定，不进行破坏性操作，不将本程序用于商业用途。
