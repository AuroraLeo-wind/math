# -*- coding: utf-8 -*-
"""探查 KK 思维导图 PDF 的 x0 列分布,用于设计层级重建算法"""
import json
import sys
import glob
import os

sys.stdout.reconfigure(encoding="utf-8")

target = sys.argv[1] if len(sys.argv) > 1 else "build/pages/kk函数极限__96b36b.jsonl"
rec = json.loads(open(target, encoding="utf-8").readline())
blocks = rec["blocks"]
print("page:", rec["w"], "x", rec["h"], "blocks:", len(blocks))

xs = sorted(b["x0"] for b in blocks)
# 聚类阈值
clusters = []
for x in xs:
    if clusters and x - clusters[-1][-1] <= 45:
        clusters[-1].append(x)
    else:
        clusters.append([x])
print("\n列聚类 (x0 range -> count, center):")
for c in clusters:
    print(f"  {c[0]:7.1f} ~ {c[-1]:7.1f}  n={len(c):3d}  center={sum(c)/len(c):7.1f}")

print("\n按 y 排序的前 60 个块:")
blocks.sort(key=lambda b: (b["y0"], b["x0"]))
for b in blocks[:60]:
    print(f"  y={b['y0']:8.1f} x={b['x0']:7.1f} w={b['x1']-b['x0']:6.1f} | {b['text'].replace(chr(10),'')[:40]}")
