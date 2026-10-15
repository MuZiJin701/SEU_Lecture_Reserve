# Domain Docs

本项目的领域上下文为东南大学素质讲座预约，采用 single-context 布局：根目录 `GLOSSARY.md` 记录领域词汇，`docs/adr/` 记录需要保留的架构决策。

## Before exploring

- 探索代码前，读取 `GLOSSARY.md`（存在时）以及 `docs/adr/` 中与当前任务相关的决策。
- 文件尚不存在时直接继续；首次确定领域词汇时再创建词汇表，发生需要记录的真实架构权衡时再创建 ADR，不预建占位文件。
- 当前运行流程、配置格式和行为限制见 [中文 README](../../README.md) / [English README](../../README.en.md)；它们不替代代码或未来 ADR 的核对。

## Vocabulary and decisions

- Issue、设计说明和测试使用词汇表定义的领域名称；新概念确定后按 `domain-modeling` Skill 格式记录。
- 词汇表只解释领域概念，运行命令和实施细节放在 README、设计说明或代码中。
- 新方案与现有 ADR 冲突时，指出对应 ADR 和重新讨论的理由，再处理变更。
