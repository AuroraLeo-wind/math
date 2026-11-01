# Issue 跟踪器：GitHub

本仓库的 issue 与 PRD 以 GitHub issue 形式存在。所有操作用 `gh` CLI。

## 约定

- **创建 issue**：`gh issue create --title "..." --body "..."`。多行正文用 heredoc。
- **读 issue**：`gh issue view <number> --comments`，用 `jq` 过滤评论并获取标签。
- **列出 issue**：`gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`，加适当 `--label` 与 `--state` 过滤。
- **评论 issue**：`gh issue comment <number> --body "..."`
- **应用/移除标签**：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **关闭**：`gh issue close <number> --comment "..."`

从 `git remote -v` 推断仓库——在 clone 内运行 `gh` 会自动推断。

## 当 skill 说「发布到 issue 跟踪器」

创建 GitHub issue。

## 当 skill 说「获取相关工单」

运行 `gh issue view <number> --comments`。

## 本仓库配置

- 平台：GitHub
- 远程仓库：`AuroraLeo-wind/math` — 已配置为 `origin`
  （`git@github.com:AuroraLeo-wind/math.git`，SSH，密钥 `~/.ssh/id_ed25519_github`）。
- CLI：`gh` — 本机当前未安装。首次使用前需安装 GitHub CLI 并 `gh auth login`；
  登录后 `gh` 在仓库内自动推断目标，无需额外参数。
- 标签词汇见 `docs/agents/triage-labels.md`；若仓库尚无这些标签，`triage` 首次应用时创建。
