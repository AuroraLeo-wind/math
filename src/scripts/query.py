# -*- coding: utf-8 -*-
"""P3: 检索 CLI —— kaoyan-math-kk skill 的唯一数据入口。

检索分四步（见 docs/adr/0001）：
  1) 骨架召回：BM25 over KK 节点路径
  2) 树扩展：命中节点 ±1 层（父=上位概念 / 子=具体题型）
  3) 证据装配：取这些节点上挂载的证据卡，按 anchor_score 与 kind 排序
  4) 预算裁剪：节点路径永远保留，卡片按分数截断到 --budget 字符

用法
----
  python src/scripts/query.py "看到加减相消就想泰勒" --prompt
  python src/scripts/query.py "二次型化标准形" --subject 线代 --k 5
  python src/scripts/query.py "洛必达" --kind method
  python src/scripts/query.py --outline --chapter 函数极限
  python src/scripts/query.py --id DX-GS-C01-001
  python src/scripts/query.py --id KK-GS-函数极限-N007
  python src/scripts/query.py "变限积分求导" --json
"""
import argparse
import json
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _text import tokenize  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB = os.path.join(BASE, "kb")
IDX = os.path.join(KB, "index")
ROOT_DOWN = 0.35           # 书名根节点降权


def load():
    nodes = {n["node_id"]: n for n in
             (json.loads(l) for l in open(os.path.join(KB, "nodes.jsonl"), encoding="utf-8"))}
    cards_path = os.path.join(KB, "cards_anchored.jsonl")
    if not os.path.exists(cards_path):
        cards_path = os.path.join(KB, "cards.jsonl")
    cards = {c["id"]: c for c in
             (json.loads(l) for l in open(cards_path, encoding="utf-8"))}
    nb = pickle.load(open(os.path.join(IDX, "nodes.bm25.pkl"), "rb"))
    cb = pickle.load(open(os.path.join(IDX, "cards.bm25.pkl"), "rb"))
    graph = json.load(open(os.path.join(IDX, "graph.json"), encoding="utf-8"))
    return nodes, cards, nb, cb, graph


def search_nodes(q, nodes, nb, k=8):
    toks = tokenize(q)
    if not toks:
        return []
    scores = nb["bm25"].get_scores(toks)
    ids = nb["ids"]
    ranked = []
    for i, s in enumerate(scores):
        if s <= 0:
            continue
        n = nodes.get(ids[i])
        if n and n["column"] == "root":
            s *= ROOT_DOWN
        ranked.append((s, ids[i]))
    ranked.sort(reverse=True)
    return ranked[:k]


def expand(node_ids, graph, nodes):
    """命中节点 ±1 层：父节点补上下文，子节点补具体题型。"""
    out = list(node_ids)
    seen = set(out)
    children = graph["children"]
    for nid in node_ids:
        n = nodes.get(nid)
        if n and n.get("parent") and n["parent"] not in seen:
            out.append(n["parent"])
            seen.add(n["parent"])
        for ch in children.get(nid, []):
            if ch not in seen:
                out.append(ch)
                seen.add(ch)
    return out


def gather_cards(node_ids, nodes, cards, graph, kinds=None, limit=12):
    node_cards = graph["node_cards"]
    hits = []
    seen = set()
    for nid in node_ids:
        for cid in node_cards.get(nid, []):
            c = cards.get(cid)
            if not c or cid in seen:
                continue
            if kinds and c.get("kind") not in kinds:
                continue
            seen.add(cid)
            hits.append((c.get("anchor_score", 0), cid, c))
    # map 卡（整章总览，raw 是全图节点列表）会命中一切，非显式要 map 时排到最后
    order = {"method": 0, "example": 1, "symptom": 2, "pitfall": 3, "map": 8}
    if not kinds:
        real = [h for h in hits if h[2].get("kind") != "map"]
        maps = [h for h in hits if h[2].get("kind") == "map"]
        real.sort(key=lambda x: (order.get(x[2].get("kind"), 9), -x[0]))
        maps.sort(key=lambda x: -x[0])
        hits = real + maps[:2]
    else:
        hits.sort(key=lambda x: (order.get(x[2].get("kind"), 9), -x[0]))
    return [h[2] for h in hits[:limit]]


def fmt_card(c):
    src = c.get("source")
    if isinstance(src, dict):
        loc = f"{src.get('file', '')} p{src.get('page', '?')}"
        if src.get("page_end") and src.get("page_end") != src.get("page"):
            loc += f"–{src['page_end']}"
    else:
        loc = str(src or "")
    lines = [f"### [{c['id']}] ({c.get('kind')}) {c.get('title')}",
             f"出处: {loc}"]
    for key, label in (("symptom", "识别信号"), ("conditions", "适用条件"),
                       ("failure_boundary", "失效边界"), ("method_chain", "方法链"),
                       ("formula", "关键公式"), ("pitfall", "陷阱")):
        v = c.get(key)
        if isinstance(v, list) and v:
            lines.append(f"{label}: " + "；".join(str(x)[:120] for x in v[:5]))
    raw = str(c.get("raw", "")).strip()
    if raw:
        lines.append("原文: " + raw[:260].replace("\n", " "))
    return "\n".join(lines)


def path_str(n):
    return " / ".join(n["path"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", default=None)
    ap.add_argument("--subject", default=None, help="高数|线代|概率")
    ap.add_argument("--chapter", default=None)
    ap.add_argument("--kind", default=None, help="method|example|symptom|pitfall|map，可逗号分隔")
    ap.add_argument("--id", dest="cid", default=None)
    ap.add_argument("--outline", action="store_true")
    ap.add_argument("--diverse", action="store_true", help="同一父节点最多 2 条")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--budget", type=int, default=6000)
    ap.add_argument("--prompt", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    nodes, cards, nb, cb, graph = load()
    SUBJ = {"高数": "GS", "线代": "LD", "概率": "GL"}

    # --- 单条查询：--id ---
    if args.cid:
        if args.cid in cards:
            print(json.dumps(cards[args.cid], ensure_ascii=False, indent=1)
                  if args.json else fmt_card(cards[args.cid]))
            return
        hit = [n for n in nodes.values() if n["node_id"] == args.cid]
        if hit:
            n = hit[0]
            body = fmt_node_block([n], nodes, cards, graph, args.limit)
            print(json.dumps(n, ensure_ascii=False, indent=1) if args.json else body)
            return
        print(f"查无此卡/节点: {args.cid}", file=sys.stderr)
        sys.exit(2)

    # --- 大纲：--outline ---
    if args.outline:
        pool = [n for n in nodes.values()
                if (not args.chapter or args.chapter in n["chapter"])
                and (not args.subject or n["subject"] == SUBJ.get(args.subject, ""))]
        by_book = {}
        for n in pool:
            by_book.setdefault((n["subject"], n["chapter"]), []).append(n)
        lines = []
        for (subj, chap), ns in sorted(by_book.items()):
            lines.append(f"## {chap}  [{subj}]  nodes={len(ns)}")
            by_parent = {}
            for n in ns:
                by_parent.setdefault(n["parent"], []).append(n)

            def walk(pid, d):
                for n in sorted(by_parent.get(pid, []), key=lambda x: x["order"]):
                    ncard = len(graph["node_cards"].get(n["node_id"], []))
                    flag = f" ({ncard}卡)" if ncard else ""
                    lines.append(f"{'  ' * d}- {n['text']}{flag}")
                    walk(n["node_id"], d + 1)
            walk(None, 0)
            lines.append("")
        if args.chapter or args.subject:
            print("\n".join(lines))
            return
        print(f"共 {len(by_book)} 章 / {len(pool)} 节点；用 --chapter 看具体章")
        for (subj, chap), ns in sorted(by_book.items()):
            print(f"  {subj} {chap}  ({len(ns)})")
        return

    if not args.query:
        ap.error("需要给查询词，或用 --outline / --id")

    # --- 检索 ---
    kinds = set(args.kind.split(",")) if args.kind else None
    ranked = search_nodes(args.query, nodes, nb, k=args.k)
    nids = [nid for _, nid in ranked]
    nids = expand(nids, graph, nodes)
    got = gather_cards(nids, nodes, cards, graph, kinds=kinds, limit=args.limit)

    if args.json:
        print(json.dumps({
            "query": args.query,
            "nodes": [{"node_id": i, "path": path_str(nodes[i]),
                       "score": round(s, 3)} for s, i in ranked],
            "cards": got,
        }, ensure_ascii=False, indent=1))
        return

    block = fmt_node_block([nodes[i] for _, i in ranked[:6]], nodes, cards, graph,
                           args.limit, cards_override=got)

    if args.prompt:
        body = "<notes-retrieval>\n" + block + "\n</notes-retrieval>"
        if len(body) > args.budget:
            body = body[: args.budget - 40].rstrip() + "\n…（已按预算截断）\n</notes-retrieval>"
        print(body)
    else:
        print(block)


def fmt_node_block(ns, nodes, cards, graph, limit=12, cards_override=None):
    if not ns:
        return "> 笔记库未命中，以下为通用方法，请自行与课堂笔记核对。"
    lines = ["## 骨架命中"]
    for n in ns:
        ncard = len(graph["node_cards"].get(n["node_id"], []))
        lines.append(f"- [{n['node_id']}] {path_str(n)}  → {ncard} 张证据卡")
    got = cards_override if cards_override is not None else gather_cards(
        [n["node_id"] for n in ns], nodes, cards, graph, limit=limit)
    lines.append("")
    lines.append("## 证据卡")
    if not got:
        lines.append("（这些骨架节点上暂无证据卡 —— 笔记里只有结构，没有展开内容）")
    for c in got:
        lines.append("")
        lines.append(fmt_card(c))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
