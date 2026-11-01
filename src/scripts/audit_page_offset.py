# -*- coding: utf-8 -*-
"""统计"页码偏移":卡片 raw 的实际命中页 vs source.page 的差。

发现来源:round-trip 里 DX-GL-M07-009 的 source.page=48,但正文实际在 p49。

用法:
    python scripts/audit_page_offset.py --n 400
"""
import argparse
import glob
import json
import os
import random
import re
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = os.path.join(BASE, "build", "pages")
SPLIT_RE = re.compile(r"【[^】]*】|/|\n|、|:|：|_root")


def norm(s):
    s = (s or "").replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--window", type=int, default=2)
    ap.add_argument("--seed", type=int, default=99)
    args = ap.parse_args()

    man = {x["file"]: x["slug"] for x in json.load(open(os.path.join(BASE, "build", "manifest.json"), encoding="utf-8"))}
    cards = []
    for p in sorted(glob.glob(os.path.join(BASE, "kb", "cards", "*.jsonl"))):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                cards.append(json.loads(line))
    pool = [c for c in cards if len(norm(c.get("raw", ""))) >= 40 and (c.get("source") or {}).get("file") in man]
    random.seed(args.seed)
    picked = random.sample(pool, min(args.n, len(pool)))

    cache = {}
    def pages_of(slug):
        if slug in cache:
            return cache[slug]
        out = []
        with open(os.path.join(PAGES, slug + ".jsonl"), encoding="utf-8") as fh:
            for line in fh:
                out.append(norm(json.loads(line)["text"]))
        cache[slug] = out
        return out

    offs = Counter()
    for c in picked:
        src = c["source"]
        slug = man[src["file"]]
        texts = pages_of(slug)
        segs = [norm(s) for s in SPLIT_RE.split(c["raw"])]
        segs = [s for s in segs if len(s) >= 14]
        if not segs:
            continue
        base = int(src.get("page") or 0)
        found = None
        for d in range(0, args.window + 1):
            for cand in ({base - d, base + d} if d else {base}):
                if 0 <= cand < len(texts) and any(s in texts[cand] for s in segs):
                    found = cand - base
                    break
            if found is not None:
                break
        offs[found if found is not None else "未命中"] += 1

    print(f"抽样 {len(picked)} 张,窗口 ±{args.window} 页")
    for k, v in sorted(offs.items(), key=lambda x: -x[1]):
        label = "偏移 0(正确)" if k == 0 else (f"偏移 {k:+d}" if isinstance(k, int) else k)
        print(f"  {label:14s} {v:4d}  {v/len(picked):6.1%}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
