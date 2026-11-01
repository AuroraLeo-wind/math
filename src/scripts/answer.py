# -*- coding: utf-8 -*-
"""把一道题的检索结果 + 四要素契约拼成一份完整请求（给外部模型或自己贴进对话）。

用法
----
  python src/scripts/answer.py "题目原话" --subject 高数 --mode 解题 --out build/ask.md
  python src/scripts/answer.py "洛必达什么时候失效" --mode 方法查询
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import query as Q  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEMPLATES = {
    "解题": """你是考研数学解题助手。**只依据下面 <notes-retrieval> 里的笔记证据作答**，
证据没覆盖的地方必须明说「笔记里没有直接对应」，不许用通用数学知识冒充笔记方法论。

输出结构（顺序不许调）：
① 特征识别（逐条列出触发信号，每条后标它命中哪个骨架节点）
② 方法定位（1–3 个候选方法：方法名 → 出处 → 适用条件 → 预计步数；给主选/备选）
③ 逻辑链条（编号步骤，每步写「做什么 → 依据什么 → 得到什么」，公式用 LaTeX，禁止跳步）
④ 结构化复盘（题型归属 / 前置知识 / 相邻易混 / 陷阱 / 变式）
⑤ 自检（边界条件用到了吗 / 结果能验证吗 / 有没有更短的笔记内路径）

引用格式：
[KK 节点路径] ← [证据卡 id] 文件名 p页码
""",
    "方法查询": """你是考研数学方法助手。**只依据下面 <notes-retrieval> 里的笔记证据作答**。
按方法卡格式输出：识别信号 / 适用条件 / 失效边界 / 标准动作 / 配套例题。
失效边界是关键：笔记里没写就明说没写，不要自己补。
引用格式：[KK 节点路径] ← [证据卡 id] 文件名 p页码
""",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--subject", default=None, choices=["高数", "线代", "概率"])
    ap.add_argument("--mode", default="解题", choices=list(TEMPLATES))
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    nodes, cards, nb, cb, graph = Q.load()
    ranked = Q.search_nodes(args.question, nodes, nb, k=args.k)
    nids = Q.expand([i for _, i in ranked], graph, nodes)
    got = Q.gather_cards(nids, nodes, cards, graph, limit=args.limit)
    body = Q.fmt_node_block([nodes[i] for _, i in ranked[:6]], nodes, cards, graph,
                            args.limit, cards_override=got)

    lines = [f"# 题目\n\n{args.question}\n", "## 任务", TEMPLATES[args.mode],
             "---", "<notes-retrieval>", body, "</notes-retrieval>"]
    text = "\n".join(lines)

    out = args.out or os.path.join(BASE, "build", "ask.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(text)
    print(f"骨架命中 {len(ranked)} 个节点，证据卡 {len(got)} 张 -> {out} ({len(text)} 字符)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
