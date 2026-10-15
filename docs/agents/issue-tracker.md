# Issue tracker: GitHub

本项目独立使用 [MuZiJin701/SEU_Lecture_Reserve 的 Issues](https://github.com/MuZiJin701/SEU_Lecture_Reserve/issues) 记录任务和规格。使用 `gh` CLI，显式指定 `--repo MuZiJin701/SEU_Lecture_Reserve`。

## Conventions

- 创建：`gh issue create --repo MuZiJin701/SEU_Lecture_Reserve --title "..." --body-file <file>`。多行正文先写入 UTF-8 文件。
- 读取：`gh issue view <number> --repo MuZiJin701/SEU_Lecture_Reserve --json number,title,body,labels,comments`。
- 列表：`gh issue list --repo MuZiJin701/SEU_Lecture_Reserve --state open --json number,title,body,labels`；按需使用 `--label`。
- 评论：`gh issue comment <number> --repo MuZiJin701/SEU_Lecture_Reserve --body-file <file>`。
- 标签：`gh issue edit <number> --repo MuZiJin701/SEU_Lecture_Reserve --add-label "..."` 或 `--remove-label "..."`；角色映射见 [triage-labels.md](triage-labels.md)。
- 关闭：`gh issue close <number> --repo MuZiJin701/SEU_Lecture_Reserve`。
- 子任务：`gh issue create --repo MuZiJin701/SEU_Lecture_Reserve --parent <parent> --title "..." --body-file <file>`；不支持时，在子任务正文写 `Part of #<parent>` 并维护父任务清单。

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Skill conventions

- “publish to the issue tracker”：创建 GitHub Issue。
- “fetch the relevant ticket”：读取对应 GitHub Issue。
- 发布运行故障前，按 [项目规则](../../AGENTS.md) 选择离线检查；运行方式与已知限制以双语 README 为准。正文和附件不包含 `.env`、凭据或未脱敏的登录页面/截图。
- 本文件规定操作方式；对外写入仍遵循当前会话与适用规则的授权要求。
