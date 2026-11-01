# -*- coding: utf-8 -*-
"""导出卡片清单(人读),用于核对引用与人工抽查"""
import glob
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = []
cards = []
for p in sorted(glob.glob(os.path.join(BASE, "kb", "cards", "*.jsonl"))):
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        cards.append(json.loads(line))
for c in cards:
    rows.append("\t".join([
        c["id"], c["kind"], c["subject"], c["chapter"], c["topic"], c["title"],
    ]))
out = os.path.join(BASE, "build", "card_list.tsv")
open(out, "w", encoding="utf-8", newline="\n").write("\n".join(rows))
print(f"cards={len(cards)} -> {out}")
from collections import Counter
print("by prefix:", dict(Counter(c["id"].split("-")[0] for c in cards)))
