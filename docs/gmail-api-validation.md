# Gmail API 本机可行性验证

2026-10-19，状态：历史可行性记录。网络层通过，账号授权与实际投递未验证。用户因配置复杂选择继续完善 SMTP，见[邮件通知需求](notification-requirements.md)；以下授权和接入步骤仅保留作为备选，不属于当前配置流程。

## 已执行

使用项目已有 Python 环境和标准库 HTTPS 客户端，保留 TLS 证书校验，不改动网络配置，不安装 CLI 或新增依赖。四项匿名请求均获得预期响应：

| 检查 | 本次响应 | 能说明什么 |
| --- | --- | --- |
| Gmail API Discovery | HTTP 200 | 可读取 API 定义，包含发信方法和 `gmail.send` 权限 |
| Google OAuth Discovery | HTTP 200 | 可读取授权配置，令牌端点与官方地址一致 |
| 无授权调用 Gmail 发信端点，空请求体 | HTTP 401，`UNAUTHENTICATED` | 请求已到达认证层；不表示账号已获发信权限 |
| 无客户端、无刷新令牌调用 OAuth 令牌端点 | HTTP 400 | 端点可达，缺少凭据被正常拒绝；不表示令牌交换已通过 |

本机项目已知凭据路径、`.env` 与进程环境的常用 OAuth 配置项中，未找到客户端配置或访问／刷新令牌。没有使用 Gmail 网页登录密码、SMTP 应用专用密码或 Codex 插件的连接凭据。

本地验证脚本与匿名响应摘要位于被 Git 忽略的 `state/gmail-api/`。脚本使用短期访问令牌检查权限，仅在显式运行 `--send-test` 时向 `.env` 中 `GMAIL_USERNAME`（缺省取 `SMTP_USERNAME`）对应的自己发送一封固定测试邮件。它不会重试，也不包含学校凭据或讲座记录。离线自检已通过，覆盖中文邮件编码和收件地址换行注入拒绝：

```shell
uv run --locked python state/gmail-api/verify.py --self-check
```

## 完成一次临时授权

为先验证本机账号与发信路径，可使用 Google 官方 [OAuth Playground](https://developers.google.com/oauthplayground/) 的默认客户端，无需现在就安装 CLI。请在日常浏览器中操作：

1. 在 Step 1 的自定义 scope 中填写 `https://www.googleapis.com/auth/gmail.send`，点击 **Authorize APIs**，选择实际用于发信的 Gmail 账号并确认授权。
2. 在 Step 2 点击 **Exchange authorization code for tokens**。
3. 将 **Access token** 保存在本机 `state/gmail-api/access_token.txt`，不要发到聊天、粘贴到命令行参数或提交到 Git。无需复制 Refresh token。
4. 保存后运行 `uv run --locked python state/gmail-api/verify.py --check`，验证令牌有效期与发信权限。真实发送测试还需要用户明确同意，再运行 `--send-test`；API 接受后仍需用户核对收件箱。

目前已请求用户完成授权并选择是否允许给自己发送一封测试邮件；尚未获得令牌或执行真实发送。

## 验证边界

Playground 访问令牌短期有效，其默认配置产生的刷新令牌会在 24 小时后被撤销。这条路径用于一次性验证，不替代正式项目的 OAuth 客户端、令牌安全存储和刷新处理。即使一次投递成功，也不能证明长期无人值守已经通过。

正式接入时仅申请发信所需权限，不要求读信权限。参见 [Gmail 发信接口](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send)、[桌面应用 OAuth](https://developers.google.com/identity/protocols/oauth2/native-app)及 [OAuth Playground](https://developers.google.com/oauthplayground/)。

## 正式接入的准备流程

用户在有头浏览器中再次遇到网页登录拒绝后，询问 Gmail API 的实施方式。以下是正式接入的准备路径，尚未创建云项目、完成授权或替换现有 SMTP 实现：

1. 在 [Google Cloud Console](https://console.cloud.google.com/) 中选择或创建用于本项目的 Cloud 项目，在 API 库中启用 **Gmail API**。
2. 在 **Google Auth platform** 配置应用名称、支持邮箱等信息。个人 Gmail 使用 **External** 受众；初期测试时在 **Audience → Test users** 添加自己的 Gmail。在 **Data Access** 中只添加 `https://www.googleapis.com/auth/gmail.send`。
3. 在 **Clients → Create client** 选择 **Desktop app**，下载 OAuth 客户端 JSON，保存为本机 `state/gmail-api/client_secret.json`；该目录被 Git 忽略，不将 JSON 发到聊天或提交到仓库。
4. 客户端就绪后接入本地授权程序：打开日常浏览器，由用户完成 Google 登录及权限确认，通过本机 loopback 回调获得令牌，私有保存访问令牌和刷新令牌。已有 `verify.py` 只验证 Playground 的短期访问令牌，不具备正式客户端授权或自动刷新功能。
5. 验证实际发信、收件箱投递以及令牌刷新后，再将 Gmail API 接入现有通知接口，保留事件内容、去重、状态记录与发信失败不影响预约的规则。运行时无需填写 Gmail 登录密码或应用专用密码；首次授权仍需本人参与。

外部应用处于 **Testing** 发布状态时，包含 Gmail 权限的刷新令牌会在 7 天后到期。长期运行前需要根据 Google 的个人使用／发布及验证要求配置发布状态，不能把测试模式的一次成功当作永久授权保证；切换状态与 OAuth 验证要求也不是同一事项。用户撤销授权、更改密码等情况仍可能使令牌失效，需要明确处理重新授权。参见 [配置同意屏幕](https://developers.google.com/workspace/guides/configure-oauth-consent)、[Python 官方快速入门](https://developers.google.com/workspace/gmail/api/quickstart/python)和 [刷新令牌到期规则](https://developers.google.com/identity/protocols/oauth2#expiration)。
