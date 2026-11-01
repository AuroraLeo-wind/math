# -*- coding: utf-8 -*-
"""P1: 把 KK 单页巨型思维导图 PDF 重建为「骨架节点树」。

为什么不能用文字坐标猜层级
------------------------
两版尝试都被实测否掉：
1. 旧 `build_kk_outline.py`：用文字 block 的 x0 聚类。导图标题文字在框内居中，
   框宽不等 → x0 漂移。旧脚本注释自己写了「不做严格父子推断，避免伪造层级」。
2. 用框的 x0 聚类：mindmap 是「父框垂直居中于子框组、父在左子在右」的布局，
   父宽度不同导致**同层框左缘并不对齐**，实测聚出 21 个伪层（真实深度只有 4–6 层）。

本脚本的做法：**用矢量连线定父子**
--------------------------------
KK 导图的连接线是正交折线：父框右缘 --水平--> 肘 --垂直--> 肘 --水平--> 子框左缘。
- 垂直脊柱（tall & narrow 的 stroke path）两端 y 精确等于**两个框的垂直中心**；
- 脊柱 x 位置落在父框右缘与子框左缘之间。
所以：脊柱上端/下端各取中心 y 匹配框，x 较小侧为父、较大侧为子。

节点 = **含标题文字的圆角框**（框内是公式截图，无文本层，故骨架只有节点名）。
栏归属（四栏）= 沿父链上溯遇到的第一个栏锚点。

输出
----
kb/nodes.jsonl              全量骨架节点
build/kk_tree/<slug>.txt    人读树（--dump）
build/kk_tree_report.json   每本统计（节点数/未解析父/栏覆盖）

用法
----
  python src/scripts/build_kk_tree.py
  python src/scripts/build_kk_tree.py --slug kk函数极限__96b36b --dump --debug
"""
import argparse
import glob
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAGES = os.path.join(BASE, "build", "pages")
OUT_TREE = os.path.join(BASE, "build", "kk_tree")
OUT_KB = os.path.join(BASE, "kb")
CORPUS_ROOT = r"D:\Download\math"

SECTIONS = ["知识点结构化", "解题思路结构化", "题型结构化", "通俗理解", "冷门知识点"]
# 栏名变体：不同版本导图写作「解题思路」「知识点」「题型」等，统一归一
SECTION_ALIASES = [
    ("冷门知识点", "冷门知识点"),
    ("知识点结构化", "知识点"),
    ("解题思路结构化", "解题思路"),
    ("题型结构化", "题型"),
    ("通俗理解", "通俗理解"),
]
# 框内两行被合并进标题的噪声后缀（如「三角型进阶练习」）
HINT_SUFFIX = ("进阶练习", "进阶训练", "视频链接", "视频讲解", "更多新颖考法")
NOISE = re.compile(r"^(视频链接|视频讲解|进阶练习|进阶训练|更多新颖考法|扫码|关注|详情|作者[:：]|软件[:：])")
NOISE_IN = ("知犀思维导图", "kk全程班", "公众号精选", "获取更多资料", "扫码了解更多",
            "可视化高数", "可视化线代", "可视化概率")

SUBJECT_RULES = [("线性代数", "LD"), ("线代", "LD"), ("概率", "GL"),
                 ("高等数学", "GS"), ("高数", "GS"), ("数一专项", "GS")]


def clean_text(t):
    """节点内换行是框宽导致的折行，直接拼接；去掉所有空白。"""
    return re.sub(r"\s+", "", t.replace("\r", "").replace("\n", "")).strip()


def subject_of(path):
    for key, code in SUBJECT_RULES:
        if key in path:
            return code
    return "GS"


def resolve_pdf(fname):
    hits = glob.glob(os.path.join(CORPUS_ROOT, "**", fname), recursive=True)
    return hits[0] if hits else None


def load_page(slug):
    path = os.path.join(PAGES, slug + ".jsonl")
    if not os.path.exists(path):
        return None
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    return recs[0] if len(recs) == 1 else None


def drawing_points(it):
    """把一个 drawing 的所有路径点摊平成 [(x,y), ...]，保持路径顺序。"""
    pts = []
    for item in it.get("items", []):
        op = item[0]
        if op == "l":
            pts.extend([(item[1].x, item[1].y), (item[2].x, item[2].y)])
        elif op == "c":
            for p in item[1:5]:
                pts.append((p.x, p.y))
        elif op == "re":
            r = item[1]
            pts.extend([(r.x0, r.y0), (r.x1, r.y1)])
        elif op == "qu":
            q = item[1]
            pts.extend([(q.ul.x, q.ul.y), (q.lr.x, q.lr.y)])
    return pts


def canonical_section(t):
    """把栏名变体归一到标准四栏名。返回 (标准名, 命中前缀) 或 (None, None)。"""
    for canon, prefix in SECTION_ALIASES:
        if t == canon or t.startswith(prefix):
            rest = t[len(prefix):]
            if len(rest) <= 6 and not re.search(r"[：:（(]", rest):
                return canon, prefix
    return None, None


KNOWN_SECTIONS = set(SECTIONS) | {"知识点", "解题思路", "题型", "冷门知识点"}


def normalize(nodes):
    """拆噪声后缀、拆分被合并的栏名，就地清洗节点文本。"""
    for n in nodes:
        t = n["text"]
        hint = bool(NOISE.match(t))
        for suf in HINT_SUFFIX:
            if t.endswith(suf) and len(t) > len(suf) + 1:
                t = t[: -len(suf)]
                hint = True
                break
        sec, prefix = canonical_section(t)
        n["section_split"] = None
        if sec and t not in KNOWN_SECTIONS and t.startswith(prefix) and len(t) > len(prefix):
            n["section_split"] = sec
            t = t[len(prefix):]
        n["exercise_hint"] = hint
        n["text"] = t
    return nodes


def collect(pdf_path, debug=False):
    """返回 (标题节点列表, 连线段列表)。"""
    import pymupdf
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    drawings = page.get_drawings()

    # --- 框：type='fs' 的圆角矩形 ---
    boxes = []
    for it in drawings:
        if it.get("type") != "fs":
            continue
        r = it["rect"]
        if r.width < 30 or r.height < 12:
            continue
        boxes.append({"rect": pymupdf.Rect(r), "text": None})

    def owner(tb):
        best, best_d = None, 1e18
        for b in boxes:
            bx = b["rect"]
            if (bx.x0 - 2 <= tb.x0 and tb.x1 <= bx.x1 + 2
                    and bx.y0 - 2 <= tb.y0 and tb.y1 <= bx.y1 + 2):
                d = abs(bx.y0 - tb.y0) + abs(bx.x0 - tb.x0)
                if d < best_d:
                    best_d, best = d, b
        return best

    nodes = []
    for blk in page.get_text("blocks"):
        if blk[6] != 0:
            continue
        text = clean_text(blk[4])
        if not text or len(text) > 120:
            continue
        if not re.search(r"[\u4e00-\u9fffA-Za-z]", text):
            continue
        if any(n in text for n in NOISE_IN):
            continue
        tb = pymupdf.Rect(blk[:4])
        b = owner(tb) or {"rect": tb, "text": None}
        b["text"] = text
        if b not in nodes:
            nodes.append(b)

    # --- 脊柱：stroke 路径，高远大于宽（KK 的连接线是「水平钩+垂直段(+圆角小曲线)」） ---
    # 实测 items 签名: ('l','l','c','l') n=80 是脊柱；('l','l') n=59 是纯水平短钩。
    spines = []
    for it in drawings:
        if it.get("type") != "s":
            continue
        pts = drawing_points(it)
        if len(pts) < 2:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if h < 6 or h < 2.5 * max(w, 1):
            continue
        spines.append({"xc": (min(xs) + max(xs)) / 2,
                       "ya": pts[0][1], "yb": pts[-1][1],
                       "y_lo": min(ys), "y_hi": max(ys)})

    doc.close()
    if debug:
        print(f"  boxes={len(boxes)} title_nodes={len(nodes)} spines={len(spines)}")
    return nodes, spines


def link(nodes, spines, debug=False):
    """用脊柱把标题节点连成父子边；连不上的用几何最近邻兜底。"""
    def near_box(y, side, xc, tol=34.0):
        """side='L' 取 x1 <= xc+30 的最近框；'R' 取 x0 >= xc-8 的最近框。"""
        best, best_d = None, 1e18
        for i, n in enumerate(nodes):
            r = n["rect"]
            cy = (r.y0 + r.y1) / 2
            dy = abs(cy - y)
            if dy > tol:
                continue
            if side == "L" and r.x1 > xc + 30:
                continue
            if side == "R" and r.x0 < xc - 8:
                continue
            if dy < best_d:
                best_d, best = dy, i
        return best, best_d

    edges = {}
    unresolved = 0
    for sp in spines:
        xc = sp["xc"]
        hit = False
        for ya, yb in ((sp["ya"], sp["yb"]), (sp["yb"], sp["ya"])):
            p, _ = near_box(ya, "L", xc)
            c, _ = near_box(yb, "R", xc)
            if p is None or c is None or p == c or c in edges:
                continue
            edges[c] = p
            hit = True
            break
        if not hit:
            unresolved += 1

    # 兜底第一轮：挂到「整体在本节点左侧、且垂直中心最近」的节点
    fallback = 0
    for i, n in enumerate(nodes):
        if i in edges:
            continue
        r = n["rect"]
        cy = (r.y0 + r.y1) / 2
        best, best_d = None, 1e18
        for j, m in enumerate(nodes):
            if j == i:
                continue
            mr = m["rect"]
            if mr.x1 > r.x0 + 8:            # 必须在左侧
                continue
            mcy = (mr.y0 + mr.y1) / 2
            d = abs(mcy - cy)
            if d < best_d:
                best_d, best = d, j
        if best is not None:
            edges[i] = best
            fallback += 1
    # 兜底第二轮：仍然孤立的，挂到 x 范围覆盖本节点、且垂直最近的上层节点
    for i, n in enumerate(nodes):
        if i in edges:
            continue
        r = n["rect"]
        cy = (r.y0 + r.y1) / 2
        cand = []
        for j, m in enumerate(nodes):
            if j == i or j in edges.get(i, ()):  # 排除自己
                continue
            mr = m["rect"]
            if mr.x0 >= r.x0:                    # 父必须更靠左
                continue
            cand.append((abs(((mr.y0 + mr.y1) / 2) - cy), j))
        if cand:
            edges[i] = min(cand)[1]
            fallback += 1
    # 破环
    for i in list(edges):
        seen, cur = {i}, edges.get(i)
        while cur is not None:
            if cur in seen:
                edges.pop(i, None)
                break
            seen.add(cur)
            cur = edges.get(cur)

    if debug:
        print(f"  edges={len(edges)} (fallback={fallback}) unresolved_spines={unresolved}")
    return edges


def build(slug, pdf_path, subj, chapter, debug=False, dump=False):
    nodes, spines = collect(pdf_path, debug=debug)
    if not nodes:
        return None, {}

    normalize(nodes)
    edges = link(nodes, spines, debug=debug)

    # 根节点就地清洗（必须在 path_of 之前，否则 path 里会残留广告名）
    for i, n in enumerate(nodes):
        if edges.get(i) is not None:
            continue
        t = re.sub(r"^[（(][^）)]*版[本]?[）)]", "", n["text"]).strip() or n["text"]
        if re.search(r"获取|答疑|公众号|最新完整版|扫码", t):
            t = chapter
        half = len(t) // 2
        if len(t) >= 4 and len(t) % 2 == 0 and t[:half] == t[half:]:
            t = t[:half]
        n["text"] = t

    # 排序：先按父链定序更稳，但这里用 (y0, x0) 作阅读顺序
    order = sorted(range(len(nodes)), key=lambda i: (nodes[i]["rect"].y0, nodes[i]["rect"].x0))
    rank = {bi: k for k, bi in enumerate(order)}

    def path_of(i, guard=0):
        p = [nodes[i]["text"]]
        if nodes[i].get("section_split"):
            p.insert(0, nodes[i]["section_split"])
        cur = edges.get(i)
        while cur is not None and guard < 64:
            p.insert(0, nodes[cur]["text"])
            cur = edges.get(cur)
            guard += 1
        return p

    tag = slug.split("__")[-1][:6] if "__" in slug else str(abs(hash(slug)) % 100000)
    cha = chapter[:8] + "-" + tag
    out, idmap = [], {}
    for i in order:
        nid = f"KK-{subj}-{cha}-N{rank[i]:03d}"
        idmap[i] = nid
    for i in order:
        n = nodes[i]
        r = n["rect"]
        path = path_of(i)
        col = n.get("section_split")
        if col is None:
            col = next((c for c in (canonical_section(p)[0] for p in path) if c), None)
        if col is None:
            # 父链上没有栏锚点（如页底「概念题」直挂书名）：按 y 就近归栏
            cy = (r.y0 + r.y1) / 2
            near = [(abs(((m["rect"].y0 + m["rect"].y1) / 2) - cy), canonical_section(m["text"])[0])
                    for m in nodes if canonical_section(m["text"])[0]]
            col = min(near)[1] if near else "unsectioned"
        text = n["text"]
        if edges.get(i) is None:                   # 根节点 = 书名，不归栏
            col = "root"
        out.append({
            "node_id": idmap[i], "slug": slug, "subject": subj, "chapter": chapter,
            "column": col, "text": text, "path": path, "depth": len(path) - 1,
            "bbox": [round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)],
            "parent": idmap.get(edges.get(i)),
            "children": [], "exercise_hint": bool(n.get("exercise_hint")), "order": rank[i],
        })
    idx = {o["node_id"]: o for o in out}
    for o in out:
        if o["parent"] in idx:
            idx[o["parent"]]["children"].append(o["node_id"])

    stats = {
        "nodes": len(out),
        "rooted": sum(1 for o in out if o["parent"] is None),
        "max_depth": max(o["depth"] for o in out),
        "columns": {c: sum(1 for o in out if o["column"] == c)
                    for c in sorted({o["column"] for o in out})},
    }

    if dump:
        os.makedirs(OUT_TREE, exist_ok=True)
        lines = [f"# {chapter}  ({slug})   nodes={stats['nodes']} roots={stats['rooted']}", ""]
        by_parent = {}
        for o in out:
            by_parent.setdefault(o["parent"], []).append(o)

        def walk(pid, d):
            for o in sorted(by_parent.get(pid, []), key=lambda x: x["order"]):
                lines.append(f"{'  ' * d}[{o['column']}] {o['text']}")
                walk(o["node_id"], d + 1)
        walk(None, 0)
        open(os.path.join(OUT_TREE, slug + ".txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return out, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default=None)
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    slugs = [args.slug] if args.slug else sorted(
        os.path.basename(p)[:-6] for p in glob.glob(os.path.join(PAGES, "*.jsonl")))

    all_nodes, report = [], []
    for slug in slugs:
        rec = load_page(slug)
        if rec is None:
            continue
        fname = rec["file"]
        if "张宇" in fname or "1000题" in fname or "epsilon" in fname.lower() or "板书" in fname:
            continue                                   # 骨架只收 KK 导图
        if "kk" not in fname.lower() and "自测" not in fname:
            continue
        pdf = resolve_pdf(fname)
        if not pdf:
            report.append({"slug": slug, "error": "pdf not found"})
            continue
        chapter = re.sub(r"^kk|\.pdf$|（自测版本）|\(自测版本\)|（自测版）|\(自测版\)", "", fname).strip()
        try:
            nodes, stats = build(slug, pdf, subject_of(pdf), chapter,
                                 debug=args.debug, dump=args.dump)
        except Exception as e:                         # noqa: BLE001
            report.append({"slug": slug, "error": f"{type(e).__name__}: {e}"[:160]})
            continue
        if not nodes:
            report.append({"slug": slug, "error": "no nodes"})
            continue
        all_nodes.extend(nodes)
        report.append({"slug": slug, "chapter": chapter, **stats})
        print(json.dumps(report[-1], ensure_ascii=False))

    os.makedirs(OUT_KB, exist_ok=True)
    with open(os.path.join(OUT_KB, "nodes.jsonl"), "w", encoding="utf-8") as f:
        for n in all_nodes:
            f.write(json.dumps(n, ensure_ascii=False) + "\n")
    json.dump(report, open(os.path.join(BASE, "build", "kk_tree_report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    ok = sum(1 for r in report if "nodes" in r)
    print(f"\nDONE {len(all_nodes)} nodes from {ok} files -> kb/nodes.jsonl")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()



