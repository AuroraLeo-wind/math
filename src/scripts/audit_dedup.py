# -*- coding: utf-8 -*-
"""审计:原始分片 vs 去重后入索引,丢了哪些卡、为什么丢。

用法: python scripts/audit_dedup.py
"""
import glob
import json
import os
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import index_build  # noqa: E402


def main():
    raw = []
    for p in sorted(glob.glob(os.path.join(BASE, "kb", "cards", "*.jsonl"))):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                raw.append(json.loads(line))
    kept = index_build.load_cards()
    kept_ids = {c["id"] for c in kept}
    dropped = [c for c in raw if c["id"] not in kept_ids]

    print(f"原始: {len(raw)}   入索引: {len(kept)}   丢弃: {len(dropped)}")
    print("\n丢弃按来源:", dict(Counter(c["id"].split("-")[0] for c in dropped)))
    print("丢弃按类型:", dict(Counter(c["kind"] for c in dropped)))

    # 判定丢弃原因:同 (chapter,kind,node_set) 或 同 (title,raw[:200])
    idx = {}
    for c in kept:
        ns = frozenset(c.get("symptom", []) + c.get("method_chain", []) + c.get("pitfall", []))
        if ns:
            idx[(c["chapter"], c["kind"], c["topic"], tuple(sorted(ns)))] = c["id"]
        idx[(c["title"], c.get("raw", "")[:200])] = c["id"]
        idx[(c["chapter"], c["kind"], c["topic"], tuple(sorted(ns)))] = c["id"]

    reasons = Counter()
    samples = {}
    for c in dropped:
        ns = frozenset(c.get("symptom", []) + c.get("method_chain", []) + c.get("pitfall", []))
        k1 = (c["chapter"], c["kind"], c["topic"], tuple(sorted(ns))) if ns else None
        k2 = (c["title"], c.get("raw", "")[:200])
        if k1 and k1 in idx:
            reasons["node_set 重复"] += 1
            samples.setdefault("node_set 重复", []).append((c["id"], idx[k1], c["title"][:50]))
        elif k2 in idx:
            reasons["title+raw 重复"] += 1
            samples.setdefault("title+raw 重复", []).append((c["id"], idx[k2], c["title"][:50]))
        else:
            reasons["其他"] += 1
            samples.setdefault("其他", []).append((c["id"], "-", c["title"][:50]))

    print("\n丢弃原因:", dict(reasons))
    for k, v in samples.items():
        print(f"\n[{k}] 示例:")
        for a, b, t in v[:5]:
            print(f"   {a}  <-被-> {b}   {t}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
