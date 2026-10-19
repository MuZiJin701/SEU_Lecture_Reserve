# 项目约定

运行与配置见 [中文 README](README.md) / [English README](README.en.md)。

- 使用 uv、Python 3.11 和 `pyproject.toml`，提交 `uv.lock`；同步 `uv sync --locked`，启动 `uv run main.py`。
- `config.py` 加载根目录 `.env`，环境变量优先。配置行为变更同步 `.env.example`、双语使用文档和 `tests/test_config.py`。
- 完整检查：先 `uv run playwright install chromium`，再 `uv run --locked python -m unittest discover -s tests -v`。仅配置检查：`uv run --locked python -m unittest discover -s tests -p test_config.py -v`。
- 测试使用临时配置和 `about:blank`／内存构造页面，阻断外部请求，不读取真实凭据。检查配置直接调用 `config.load_config()`，只输出校验结果。
- 导入 `main.py`、`captcha_ocr.py` 无启动副作用；执行入口可能访问真实学校系统。两者共用 `browser.py` 的 Playwright 同步 API、Chromium 和登录，统一 `channel="chromium"`，保留 `--enable-logging` 排除；不使用系统 Chrome 或 ChromeDriver。
- Playwright 调用日志可能含凭据，登录失败只输出异常类型。`.env`、驱动、生成样本及诊断页面／截图仅留本地；已有 `image/`、`images/` 素材保留原状。

## 按任务读取

- 读取或发布任务前：[Issue tracker](docs/agents/issue-tracker.md)，使用本仓库 GitHub Issues。
- 分诊或修改标签前：[标签映射](docs/agents/triage-labels.md)，使用五个默认角色。
- 探索领域概念或设计变更前：[领域文档](docs/agents/domain.md)，采用 single-context 布局。
