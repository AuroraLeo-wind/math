# -*- coding: utf-8 -*-
"""知识库体检：骨架树完整性、证据卡字段、挂载可达性、可疑标题。

用法
----
  python src/scripts/check_kb.py
  python src/scripts/check_kb.py --fix-report   # 只输出报告文件
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB = os.path.join(BASE, "kb")
BUILD = os.path.join(BASE, "build")

REQUIRED_CARD = ["id", "kind", "subject", "title", "source", "raw"]
SUSPECT_TITLE = ("可见", "若", "则", "设", "以上", "关于", "由此")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix-report", action="store_true")
    args = ap.parse_args()

    nodes = [json.loads(l) for l in open(os.path.join(KB, "nodes.jsonl"), encoding="utf-8")]
    cpath = os.path.join(KB, "cards_anchored.jsonl")
    if not os.path.exists(cpath):
        cpath = os.path.join(KB, "cards.jsonl")
    cards = [json.loads(l) for l in open(cpath, encoding="utf-8")]

    problems = []
    nid = {n["node_id"] for n in nodes}
    if len(nid) != len(nodes):
        problems.append(f"骨架 node_id 重复: {len(nodes) - len(nid)} 个")
    for n in nodes:
        if n.get("parent") and n["parent"] not in nid:
            problems.append(f"父节点不可达: {n['node_id']} -> {n['parent']}")

    # 环检测
    idx = {n["node_id"]: n for n in nodes}
    for n in nodes:
        seen, cur, steps = {n["node_id"]}, n.get("parent"), 0
        while cur and steps < 64:
            if cur in seen:
                problems.append(f"父子环: {n['node_id']}")
                break
            seen.add(cur)
            cur = idx.get(cur, {}).get("parent")
            steps += 1

    cid = Counter(c["id"] for c in cards)
    dup = [k for k, v in cid.items() if v > 1]
    if dup:
        problems.append(f"卡片 id 重复: {len(dup)} 个（如 {dup[:3]}）")

    missing_field, bad_anchor, no_anchor = 0, 0, 0
    suspect_title, inferred = [], 0
    for c in cards:
        for f in REQUIRED_CARD:
            if not c.get(f):
                missing_field += 1
                break
        anch = c.get("kk_anchor") or []
        if not anch:
            no_anchor += 1
        for a in anch:
            if a not in nid:
                bad_anchor += 1
        t = str(c.get("title") or "")
        if len(t) > 24 or any(t.startswith(s) for s in SUSPECT_TITLE):
            suspect_title.append((c["id"], c.get("kind"), t[:70]))
        if c.get("confidence") == "inferred":
            inferred += 1

    by_kind = Counter(c.get("kind") for c in cards)
    by_subj = Counter(n.get("subject") for n in nodes)
    books = {n["slug"] for n in nodes}

    report = {
        "nodes": len(nodes),
        "books": len(books),
        "roots": sum(1 for n in nodes if not n.get("parent")),
        "max_depth": max((n["depth"] for n in nodes), default=0),
        "node_subjects": dict(by_subj),
        "cards": len(cards),
        "cards_by_kind": dict(by_kind),
        "cards_no_anchor": no_anchor,
        "cards_bad_anchor": bad_anchor,
        "cards_missing_field": missing_field,
        "cards_inferred_ratio": round(inferred / max(len(cards), 1), 3),
        "title_suspect": len(suspect_title),
        "problems": problems[:20],
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))

    os.makedirs(BUILD, exist_ok=True)
    with open(os.path.join(BUILD, "title_suspect.tsv"), "w", encoding="utf-8") as f:
        f.write("card_id\tkind\ttitle\n")
        for row in suspect_title:
            f.write("\t".join(str(x) for x in row) + "\n")
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
