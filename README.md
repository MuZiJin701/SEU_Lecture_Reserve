# 东南大学讲座预约

[English](README.en.md)

帮你持续查找合适的讲座，自动筛选、识别图形验证码并尝试预约。短信认证需要手动完成，确认预约一场后程序自动退出。

![讲座预约脚本运行截图](docs/images/使用截图.png)

*登录后持续扫描符合条件的讲座。*

## 快速开始

先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/) 和 Google Chrome，无需 ChromeDriver。

**1. 下载项目，安装依赖**

```shell
git clone https://github.com/MuZiJin701/SEU_Lecture_Reserve.git
cd SEU_Lecture_Reserve
uv sync --locked
```

**2. 填写配置**

首次使用时复制配置样例；如果已有 `.env`，请保留原文件。

```shell
cp .env.example .env
```

用文本编辑器打开 `.env`，填写账号、密码和校区，例如：

```dotenv
SEU_CARD_NUMBER="你的一卡通号"
SEU_PASSWORD="你的密码"
SEU_PREFERRED_CAMPUS='["无锡校区"]'
SEU_TIMEOUT_LOGIN_REDIRECT=60
```

校区名称须与学校系统一致。上例留出 60 秒供你完成可能出现的短信认证。

**3. 启动**

```shell
uv run main.py
```

浏览器打开后，按提示完成短信认证。程序会持续扫描，确认预约一场后退出。

## 常用配置

在 `.env` 中修改，重新启动后生效。列表写法可参照上面的校区示例。

| 设置 | 作用 |
| --- | --- |
| `SEU_PREFERRED_CAMPUS` | 想参加讲座的校区，可填写多个 |
| `SEU_REQUIRED_CATEGORIES` | 想参加的讲座类别，保留样例值也可使用 |
| `SEU_ENABLE_ONLINE` / `SEU_ENABLE_OFFLINE` | 是否预约线上 / 线下讲座，填 `true` 或 `false` |
| `SEU_PREFERRED_LECTURES` | 只预约指定标题；通常保持 `'[]'` |

全部设置见 [.env.example](.env.example)，格式和排查方法见[使用指南](docs/usage.md)。

## 使用提醒

- 校区列表默认为空，会过滤全部线下讲座；需要线下预约时请填写校区。
- 指定标题后，会跳过类别、校区、线上线下开关和时间冲突检查。
- 保持终端和浏览器开启；按 `Ctrl+C` 停止。
- 不保证识别或预约成功，时间冲突也只检查当前页面。请在 [SEU 门户](https://ehall.seu.edu.cn/)核对结果和日程，并遵守学校规定。
- 不要上传 `.env`、含个人信息的登录页面或截图。

## 来源与维护

维护者：[MuZiJin701](https://github.com/MuZiJin701)。基于 [ApricityWang 的原始项目](https://github.com/ApricityWang/SEU_Lecture_Reserve)继续开发，保留原作者与历史贡献者署名。
