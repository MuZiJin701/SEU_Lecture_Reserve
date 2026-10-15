# 东南大学讲座预约

[English](README.en.md)

东南大学人文与科学素养系列讲座预约自动化脚本，支持图形验证码识别、讲座筛选和需要人工参与的短信认证。基于 [ApricityWang/SEU_Lecture_Reserve](https://github.com/ApricityWang/SEU_Lecture_Reserve) 进行二次创作，本仓库独立维护。

## 功能与运行流程

运行 `uv run main.py` 后，程序会自动读取项目根目录 `.env`，检查配置，初始化 OCR 并打开 Chrome；随后填写账号密码，等待登录跳转或人工短信认证。登录成功后持续刷新讲座页面，筛选并尝试预约。

- 未指定讲座标题时，按类别、校区、线上线下开关和当前页面已预约讲座的时间冲突进行筛选。
- 没有合适讲座或预约失败时继续扫描；程序判断成功预约一场后退出并关闭浏览器。
- 成功提示依据页面内容判断，最终结果请在 [SEU 门户](https://ehall.seu.edu.cn/)确认。

## 快速开始

需要 [uv](https://docs.astral.sh/uv/getting-started/installation/)、Chrome，以及与浏览器和操作系统兼容的 [ChromeDriver](https://googlechromelabs.github.io/chrome-for-testing/)。Windows 将 `chromedriver.exe` 放到项目根目录；macOS/Linux 使用有执行权限的 `chromedriver`。也可使用系统 `PATH` 中的驱动，自动获取是否成功取决于本机环境和网络。

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

`.env`、本地驱动、生成的验证码样本及登录错误页面/截图均被 Git 忽略；只提交不含真实凭据的 [.env.example](.env.example)。

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
| `SEU_TIMEOUT_ELEMENT_WAIT` | 查找页面元素的等待时间，默认 3 秒 |
| `SEU_TIMEOUT_LOGIN_REDIRECT` | 提交登录后的等待时间，默认 2 秒；人工短信认证时可临时改为 60 |
| `SEU_TIMEOUT_SCAN_INTERVAL` | 每轮扫描后的额外等待，默认 0.05 秒；不是整个扫描周期 |
| `SEU_TIMEOUT_RETRY_DELAY` | 重试等待，默认 0.05 秒 |
| `SEU_TIMEOUT_ACTION_CONFIRM` | 提交预约后的确认等待，默认 0.2 秒 |

列表使用 JSON 数组，整个数组在 `.env` 中以单引号包裹，例如：

```dotenv
SEU_PREFERRED_CAMPUS='["无锡校区"]'
SEU_PREFERRED_LECTURES='[]'
SEU_ENABLE_OFFLINE=true
SEU_ENABLE_ONLINE=true
SEU_TIMEOUT_LOGIN_REDIRECT=60
```

未设置的可选变量使用程序默认值；留空不等于未设置，列表、开关和数字留空会报错。等待时间须为有限非负数，扫描间隔须大于零。缺少凭据或配置格式错误时，在创建浏览器前退出；没有 `.env` 时也可使用系统环境变量提供完整配置。

**标题指定模式的限制：**`SEU_PREFERRED_LECTURES` 非空时，标题命中且状态可预约就直接接受，跳过类别、校区、线上线下开关及时间冲突检查。这是当前行为；需要这些筛选时保持 `[]`。

常规模式下，校区列表默认为空，会过滤掉线下讲座。程序以标题包含“线上”判断线上讲座；线上讲座可绕过校区白名单，但仍受类别及线上开关等条件限制。

## 短信认证、停止与浏览器

- 浏览器默认可见。首次登录或认证失效时，设置足够的 `SEU_TIMEOUT_LOGIN_REDIRECT` 等待时间，在浏览器中手动完成短信认证，之后再恢复正常等待值。
- 按 `Ctrl+C` 停止，主程序会尝试关闭浏览器。最小化终端可继续运行；关闭承载程序的终端通常会终止进程，强制关闭可能残留浏览器。
- 当前以前台进程运行，没有后台保活或定时启动。停止程序不会撤销已经成功提交的预约。
- 主程序和采集脚本保留 Chrome 自动发现，并排除 `enable-logging`，避免部分 Windows/Scoop 环境弹出额外控制台。Chrome 底层日志会减少，脚本自身输出保留。
- 无界面运行可取消 `main.py` 中 `chrome_options.add_argument("--headless")` 前的注释；需要人工短信认证时保留可见浏览器。无界面模式不等于后台保活。

## 辅助脚本与检查

| 命令 | 作用 |
| --- | --- |
| `uv run captcha_ocr.py` | 使用相同配置登录真实系统，批量采集验证码到 `image_dataset/`；会打开浏览器，不是离线检查 |
| `uv run captcha_fetch.py` | 对 `image/` 中以正确验证码命名的已有图片进行 OCR 评估，不需要登录凭据 |
| `uv run --locked python -m unittest discover -s tests -v` | 配置回归检查，不访问预约系统，也不读取本地真实 `.env` |

`main.py` 是预约入口，`config.py` 是共享配置读取与校验，`tests/test_config.py` 是配置测试。修改启动或配置行为时同步更新中英文 README 和 [.env.example](.env.example)。

## 验证与已知限制

已验证六项配置测试、锁文件与依赖一致性、本地 OCR 推理，以及 Windows 下两个登录脚本的真实浏览器配置在空白页启动时不产生额外控制台。未完整验证真实登录、短信认证和预约，也未在 macOS/Linux 实测。OCR 准确率未重新测量，不保证每次识别成功。

预约系统网页结构、网络状态、页面等待时间和可用名额均会影响结果。时间冲突检查只依据当前页面识别到的已预约讲座；请自行确认完整日程，并遵守学校规则、合理设置扫描间隔。

## 工程协作配置

- [项目规则](AGENTS.md)：工程 Skills 的入口及安全验证约定。
- [Issue tracker](docs/agents/issue-tracker.md)：任务和规格记录在[本仓库 Issues](https://github.com/MuZiJin701/SEU_Lecture_Reserve/issues)。
- [Triage 标签](docs/agents/triage-labels.md)：五个默认标签及其含义。
- [领域文档](docs/agents/domain.md)：单一上下文，`GLOSSARY.md` 与 `docs/adr/` 按需创建。

可直接编辑 `docs/agents/*.md`；更换 tracker 或重新初始化时再运行 setup Skill。

## 免责声明

本项目仅供学习 Python 自动化技术，开发者不对使用后果负责。使用即表示同意遵守东南大学相关管理规定，不进行破坏性操作，不将本程序用于商业用途。
