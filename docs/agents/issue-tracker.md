# Issue tracker：GitHub

任务和规格使用[本仓库 Issues](https://github.com/MuZiJin701/SEU_Lecture_Reserve/issues)，PR 不作为任务入口。所有 `gh` 命令显式加 `--repo MuZiJin701/SEU_Lecture_Reserve`。

| 操作 | 命令（补上上述仓库参数） |
| --- | --- |
| 读取 | `gh issue view <number> --json number,title,body,labels,comments` |
| 列表 | `gh issue list --state open --json number,title,body,labels`，按需加 `--label` |
| 创建 | `gh issue create --title "..." --body-file <file>` |
| 评论 | `gh issue comment <number> --body-file <file>` |
| 标签 | `gh issue edit <number> --add-label "..."` 或 `--remove-label "..."` |
| 关闭 | `gh issue close <number>` |

多行正文用 UTF-8 文件。子任务创建时加 `--parent <parent>`；不支持时写 `Part of #<parent>` 并维护父任务清单。角色标签见[映射](triage-labels.md)。

Skill 中 “publish to the issue tracker” 指创建 Issue，“fetch the relevant ticket” 指读取 Issue。发布故障前按 [AGENTS.md](../../AGENTS.md) 做适用离线检查，正文和附件去除凭据及未脱敏页面。对外写入仍须当前会话授权。
