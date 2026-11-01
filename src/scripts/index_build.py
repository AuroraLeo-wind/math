# -*- coding: utf-8 -*-
"""P3: 建索引 —— 骨架节点 BM25 + 证据卡 BM25 + 图（node ⇄ card）。

产出
----
kb/index/nodes.bm25.pkl    骨架节点索引
kb/index/cards.bm25.pkl    证据卡索引
kb/index/graph.json        node -> children / node -> cards / card -> anchors
kb/index/meta.json         规模统计

用法
----
  python src/scripts/index_build.py
  python src/scripts/index_build.py --stats
"""
import argparse
import json
import os
import pickle
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _text import tokenize  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB = os.path.join(BASE, "kb")
IDX = os.path.join(KB, "index")

ROOT_WEIGHT_DOWN = 0.5     # 书名根节点降权，避免命中一切


def node_doc(n):
    return " ".join(n["path"]) + " " + n.get("column", "") + " " + n.get("chapter", "")


def card_doc(c):
    parts = [c.get("title"), c.get("topic"), c.get("chapter")]
    for f in ("symptom", "tags", "formula", "pitfall", "method_chain"):
        v = c.get(f)
        if isinstance(v, (list, tuple)):
            parts.extend(str(x) for x in v)
    parts.append(str(c.get("raw", ""))[:400])
    return " ".join(p for p in parts if p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    from rank_bm25 import BM25Okapi

    if args.stats:
        meta = json.load(open(os.path.join(IDX, "meta.json"), encoding="utf-8"))
        print(json.dumps(meta, ensure_ascii=False, indent=1))
        return

    nodes = [json.loads(l) for l in open(os.path.join(KB, "nodes.jsonl"), encoding="utf-8")]
    cards_path = os.path.join(KB, "cards_anchored.jsonl")
    if not os.path.exists(cards_path):
        cards_path = os.path.join(KB, "cards.jsonl")
    cards = [json.loads(l) for l in open(cards_path, encoding="utf-8")]

    os.makedirs(IDX, exist_ok=True)

    n_docs = [tokenize(node_doc(n)) or ["_"] for n in nodes]
    n_bm25 = BM25Okapi(n_docs)
    with open(os.path.join(IDX, "nodes.bm25.pkl"), "wb") as f:
        pickle.dump({"bm25": n_bm25, "ids": [n["node_id"] for n in nodes]}, f)

    c_docs = [tokenize(card_doc(c)) or ["_"] for c in cards]
    c_bm25 = BM25Okapi(c_docs)
    with open(os.path.join(IDX, "cards.bm25.pkl"), "wb") as f:
        pickle.dump({"bm25": c_bm25, "ids": [c["id"] for c in cards]}, f)

    children = defaultdict(list)
    node_cards = defaultdict(list)
    card_anchors = {}
    for n in nodes:
        if n.get("parent"):
            children[n["parent"]].append(n["node_id"])
    for c in cards:
        for nid in c.get("kk_anchor") or []:
            node_cards[nid].append(c["id"])
            card_anchors.setdefault(c["id"], []).append(nid)

    graph = {"children": children, "node_cards": node_cards, "card_anchors": card_anchors}
    json.dump(graph, open(os.path.join(IDX, "graph.json"), "w", encoding="utf-8"), ensure_ascii=False)

    meta = {
        "nodes": len(nodes),
        "books": len({n["slug"] for n in nodes}),
        "cards": len(cards),
        "cards_anchored": sum(1 for c in cards if c.get("kk_anchor")),
        "nodes_with_cards": sum(1 for n in nodes if node_cards.get(n["node_id"])),
        "kinds": {k: sum(1 for c in cards if c.get("kind") == k)
                  for k in sorted({c.get("kind") for c in cards})},
        "columns": {k: sum(1 for n in nodes if n["column"] == k)
                    for k in sorted({n["column"] for n in nodes})},
    }
    json.dump(meta, open(os.path.join(IDX, "meta.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(meta, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
