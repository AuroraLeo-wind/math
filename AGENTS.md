# AGENTS.md

本文件是 Agent 在本仓库工作时的入口约定。工程 skills 从这里跳转到 `docs/agents/` 的具体配置。

## Agent skills

### Issue 跟踪器

GitHub Issues，全部操作走 `gh` CLI；PRD 与 issue 均以 GitHub issue 形式存在。见 `docs/agents/issue-tracker.md`。

### Triage 标签

五个状态角色标签：`needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`，标签名即角色名。见 `docs/agents/triage-labels.md`。

### Domain 领域文档

根目录 `CONTEXT.md` + `docs/adr/`。见 `docs/agents/domain.md`。

### Repo Wiki（人类阅读）

`docs/repo-wiki/` 供人查阅；workflow skills 不读。见 `docs/agents/wiki.md`。
