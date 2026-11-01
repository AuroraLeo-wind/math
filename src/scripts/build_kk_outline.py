# -*- coding: utf-8 -*-
"""L1a: 把 KK 单页巨型思维导图 PDF 重建为层级化 Markdown 大纲。

原理
----
KK 的导图 PDF 是"一页 = 一张超长竖图",页面高度可达 13000pt。
文本层保留了每个节点框的 bbox,而节点是**左对齐**排布的:
  x0 相同  =>  同一层级
  y0 递增  =>  同级兄弟节点的先后顺序
因此用 (x0 聚类 -> 层级) + (y0 排序 -> 顺序) 就能把扁平文本还原成树。

四个固定板块(KK 方法论骨架):
  知识点结构化 / 通俗理解 / 解题思路结构化 / 题型结构化

输出:
  build/kk_outline/<slug>.md      人读大纲(带缩进)
  build/kk_outline/_index.json    机器读索引(每本书的板块->节点列表)

用法:
  python scripts/build_kk_outline.py            # 全部 KK 长图
  python scripts/build_kk_outline.py --slug kk函数极限__96b36b
"""
import argparse
import glob
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = os.path.join(BASE, "build", "pages")
OUT = os.path.join(BASE, "build", "kk_outline")

# 板块锚点(出现即视为一级板块)
SECTIONS = ["知识点结构化", "通俗理解", "解题思路结构化", "题型结构化", "冷门知识点"]
# 噪声节点
NOISE = re.compile(r"^(视频链接|视频讲解|进阶练习|进阶训练|更多新颖考法|扫码|关注|详情|作者[:：]|软件[:：])")
# 噪声片段(拼接后包含则丢弃)
NOISE_IN = ("知犀思维导图", "kk全程班", "公众号精选", "获取更多资料", "扫码了解更多")


def load_blocks(path):
    rec = json.loads(open(path, encoding="utf-8").readline())
    return rec


def clean_text(t):
    t = t.replace("\r", "")
    # 节点内换行是框宽导致的折行,直接拼接
    t = re.sub(r"\n+", "", t)
    t = t.replace(" ", "")
    return t.strip()


def cluster_levels(blocks, tol=6.0):
    """按 x0 聚类得到层级编号(0 = 最左侧)"""
    xs = sorted(b["x0"] for b in blocks)
    groups = []
    for x in xs:
        if groups and x - groups[-1][-1] <= tol:
            groups[-1].append(x)
        else:
            groups.append([x])
    centers = [sum(g) / len(g) for g in groups]

    def level_of(x):
        best, bi = 1e9, 0
        for i, c in enumerate(centers):
            d = abs(x - c)
            if d < best:
                best, bi = d, i
        return bi

    return level_of, centers


def build(slug):
    path = os.path.join(PAGES, slug + ".jsonl")
    if not os.path.exists(path):
        return None
    rec = load_blocks(path)
    name = rec["file"]
    # 只处理"1 页 = 一张巨型脑图"的 KK 资料
    n_pages = sum(1 for _ in open(path, encoding="utf-8"))
    if n_pages != 1:
        return None
    if "kk" not in name.lower() and "自测" not in name:
        return None
    title = re.sub(r"^kk|\.pdf$", "", name)
    blocks = [b for b in rec["blocks"] if b["type"] == 0]
    nodes = []
    for b in blocks:
        t = clean_text(b["text"])
        if not t or len(t) > 120:
            continue
        if not re.search(r"[\u4e00-\u9fffA-Za-z]", t):
            continue
        if any(n in t for n in NOISE_IN):
            continue
        nodes.append({"text": t, "x0": b["x0"], "y0": b["y0"], "y1": b["y1"], "w": b["x1"] - b["x0"]})

    if not nodes:
        return None
    nodes.sort(key=lambda n: n["y0"])
    # 先按 y 分段:遇到板块锚点开启新段
    level_of, centers = cluster_levels(nodes)

    # 合并相邻同层且 y 接近(同一节点的碎片)
    merged = []
    for n in nodes:
        lv = level_of(n["x0"])
        if merged and merged[-1]["level"] == lv and abs(n["y0"] - merged[-1]["y0"]) < 8:
            merged[-1]["text"] += n["text"]
            merged[-1]["y0"] = min(merged[-1]["y0"], n["y0"])
            continue
        merged.append({"text": n["text"], "x0": n["x0"], "y0": n["y0"], "level": lv})

    # 过滤噪声节点(拼接后再判)
    kept = [m for m in merged if not NOISE.match(m["text"])]
    # 重新编号层级(去掉空层),并压缩到 0..5 的可读缩进深度。
    # 说明:知犀脑图的节点并非严格左对齐,父节点文本宽度会让 x0 漂移,
    # 因此这里只把 x0 当作"相对深浅"信号,不做严格父子推断,避免伪造层级。
    used = sorted({m["level"] for m in kept})
    remap = {lv: i for i, lv in enumerate(used)}
    n_lv = max(1, len(used))
    for m in kept:
        raw = remap[m["level"]]
        m["level"] = min(5, int(round(raw / max(1, n_lv - 1) * 5)))

    lines = [f"# {title}", ""]
    sec_stack = []
    sections_out = {}
    cur_sec = "_root"
    for m in kept:
        t = m["text"]
        anchor = next((s for s in SECTIONS if t == s), None)
        if anchor:
            cur_sec = anchor
            sections_out.setdefault(cur_sec, [])
            lines.append("")
            lines.append(f"## {anchor}")
            sec_stack = [anchor]
            continue
        sections_out.setdefault(cur_sec, []).append({"level": m["level"], "text": t})
        indent = "  " * max(0, m["level"] - 1)
        lines.append(f"{indent}- {t}")

    md = "\n".join(lines) + "\n"
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, slug + ".md"), "w", encoding="utf-8").write(md)
    return {
        "slug": slug,
        "file": name,
        "title": title,
        "nodes": len(kept),
        "sections": {k: len(v) for k, v in sections_out.items()},
        "outline_md": os.path.join("build", "kk_outline", slug + ".md"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default=None)
    args = ap.parse_args()
    slugs = [args.slug] if args.slug else sorted(
        os.path.basename(p)[:-6] for p in glob.glob(os.path.join(PAGES, "*.jsonl"))
    )
    index = []
    for s in slugs:
        try:
            r = build(s)
            if r:
                index.append(r)
                print(json.dumps(r, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"slug": s, "error": str(e)[:200]}, ensure_ascii=False))
    if not args.slug:
        json.dump(index, open(os.path.join(OUT, "_index.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print(f"\nDONE {len(index)} outlines -> {OUT}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
