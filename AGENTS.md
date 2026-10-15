# Project instructions

本项目是独立维护的 Python 讲座预约脚本，运行与配置流程见 `README.md` / `README.en.md`。

- 使用 uv 和 Python 3.11；依赖在 `pyproject.toml` 中声明，提交 `uv.lock`。同步：`uv sync --locked`；启动：`uv run main.py`。
- `config.py` 自动加载项目根目录 `.env`，已有环境变量优先。配置变更同步 `.env.example`、双语 README 和 `tests/test_config.py`。
- 验证配置：`uv run --locked python -m unittest discover -s tests -v`；测试使用临时环境文件，不读取真实凭据。
- 导入 `main.py` 或执行 `captcha_ocr.py` 会启动浏览器并可能访问真实系统；检查配置时直接调用 `config.load_config()`，仅输出校验结果，不打印凭据。浏览器启动验证只访问 `about:blank`。
- 两个登录脚本保留 Chrome 自动发现，排除 `enable-logging`；修改浏览器配置时同时检查这两个入口，避免写死个人安装路径。
- `.env`、驱动二进制、生成的样本和登录错误页面/截图仅留本地；已有 `image/`、`images/` 样本为项目素材，保留原状。

## Agent skills

### Issue tracker

读取或发布任务前，阅读 `docs/agents/issue-tracker.md`；本仓库 GitHub Issues 为 tracker。

### Triage labels

分诊或修改标签前，阅读 `docs/agents/triage-labels.md`，使用其五个默认角色映射。

### Domain docs

探索领域概念或设计变更前，阅读 `docs/agents/domain.md`；本项目采用 single-context 布局。
