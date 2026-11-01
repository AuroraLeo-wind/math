# Triage 标签

`triage` skill 通过下列五个状态角色标签驱动 issue 状态机。左列是 skill 使用的角色名，中列是本仓库跟踪器中实际应用的标签字符串。

| 标签                | 跟踪器中的标签           | 含义          |
| ----------------- | ----------------- | ----------- |
| `needs-triage`    | `needs-triage`    | 待评估         |
| `needs-info`      | `needs-info`      | 待报告人反馈      |
| `ready-for-agent` | `ready-for-agent` | 可由 Agent 接手 |
| `ready-for-human` | `ready-for-human` | 待人工处理       |
| `wontfix`         | `wontfix`         | 不处理         |

## 本仓库配置

- 中列与左列一致（未做重映射）。如需改用既有标签名（例如 `bug:triage` 替代 `needs-triage`），只改中列即可，skill 会按映射应用。
