# -*- coding: utf-8 -*-
"""把知识库导出成 Obsidian vault：骨架 → 章 MOC，证据卡 → 一卡一文件。

设计要点
--------
- **vault 是唯一权威来源（SSOT）**：卡和骨架都落成可读可编辑的 Markdown，
  人可以直接改（比如修那些标题是正文句子的卡），改完回灌索引即可。
- **一卡一文件**：YAML frontmatter 保留全部结构化字段，正文人读友好。
- **双向链接 = 挂载关系**：卡里写 `[[节点名]]`，MOC 里写 `[[卡文件名]]`，
  Obsidian 的「反向链接」面板直接就是「这个知识点下有哪些证据」。
- **章 MOC** 按 slug 分节承载骨架树（同名章的多个版本不混成一棵树），
  并单列「0 卡节点」——那就是该补的地方。

用法
----
  python src/scripts/export_obsidian.py --out "D:\\math-vault" --chapter 函数极限
  python src/scripts/export_obsidian.py --out "D:\\math-vault" --all
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB = os.path.join(BASE, "kb")

KIND_DIR = {"method": "方法卡", "example": "例题卡", "symptom": "症状卡",
            "pitfall": "陷阱卡", "map": "结构卡"}
KIND_LABEL = {"method": "方法论", "example": "例题", "symptom": "症状",
              "pitfall": "陷阱", "map": "章结构"}
BAD_NAME = re.compile(r'[\\/:*?"<>|#^\[\]\n\r\t]')


def safe(name, limit=60):
    name = BAD_NAME.sub("-", str(name or "")).strip().strip(".")
    name = re.sub(r"\s+", " ", name)
    return name[:limit] or "untitled"


def yaml_list(v):
    if not v:
        return "[]"
    return "[" + ", ".join(json.dumps(str(x), ensure_ascii=False) for x in v) + "]"


def q(s):
    return json.dumps(str(s or ""), ensure_ascii=False)


def card_body(c):
    out = []
    for key, label in (("signal", "识别信号"), ("symptom", "识别信号"),
                       ("conditions", "适用条件"), ("failure_boundary", "失效边界"),
                       ("method_chain", "方法链"), ("formula", "关键公式"),
                       ("pitfall", "陷阱"), ("variants", "变式")):
        v = c.get(key)
        if isinstance(v, list) and v:
            out.append(f"## {label}")
            out.extend(f"- {str(x).strip()}" for x in v[:12])
            out.append("")
    raw = str(c.get("raw") or "").strip()
    if raw:
        out.append("## 原文")
        out.append("> " + raw.replace("\n", "\n> ")[:2000])
        out.append("")
    return "\n".join(out)


def card_md(c, node_titles):
    src = c.get("source") if isinstance(c.get("source"), dict) else {}
    head = [
        "---",
        f"id: {c.get('id')}",
        f"kind: {c.get('kind')}",
        f"subject: {c.get('subject')}",
        f"chapter: {q(c.get('chapter'))}",
        f"topic: {q(c.get('topic'))}",
        f"title: {q(c.get('title'))}",
        f"source_file: {q(src.get('file'))}",
        f"source_page: {src.get('page', '')}",
        f"source_page_end: {src.get('page_end', '')}",
        f"anchor_score: {c.get('anchor_score', 0)}",
        f"confidence: {c.get('confidence', '')}",
        f"kk_anchor: {yaml_list(c.get('kk_anchor'))}",
        "tags:",
        "  - 考研数学",
        f"  - {c.get('subject') or ''}",
        f"  - {KIND_LABEL.get(c.get('kind'), c.get('kind'))}",
        "---",
        "",
        f"# {c.get('title')}",
        "",
        f"- **类型**：{KIND_LABEL.get(c.get('kind'), c.get('kind'))}",
        f"- **出处**：{src.get('file', '')} p{src.get('page', '?')}",
    ]
    if node_titles:
        head.append("- **归属骨架**：" + " · ".join(f"[[{safe(t)}]]" for t in node_titles))
    head.append("")
    return "\n".join(head) + "\n" + card_body(c)


def moc_md(chapter, subject, ns, node_cards, card_names):
    by_parent = defaultdict(list)
    for n in sorted(ns, key=lambda x: x["order"]):
        by_parent[n["parent"]].append(n)
    uniq = {cid for n in ns for cid in node_cards.get(n["node_id"], [])}

    lines = ["---", f"chapter: {q(chapter)}", f"subject: {subject}",
             f"nodes: {len(ns)}", f"cards: {len(uniq)}",
             "tags:", "  - 考研数学", "  - 骨架MOC", "---", "",
             f"# {chapter}", "",
             f"> 骨架节点 {len(ns)} 个 · 证据卡 {len(uniq)} 张 · 来源 {len({n['slug'] for n in ns})} 个版本",
             ""]

    for slug in sorted({n["slug"] for n in ns}):
        lines.append(f"### {slug}")
        lines.append("")

        def walk(pid, depth):
            for n in by_parent.get(pid, []):
                if n["slug"] != slug:
                    continue
                cnt = len(node_cards.get(n["node_id"], []))
                tag = f" ({cnt}卡)" if cnt else "  ⚠️ 0卡"
                lines.append(f"{'  ' * depth}- **{n['text']}**{tag}")
                for cid in node_cards.get(n["node_id"], []):
                    nm = card_names.get(cid)
                    if nm:
                        lines.append(f"{'  ' * (depth + 1)}- [[{nm}]]")
                walk(n["node_id"], depth + 1)

        walk(None, 0)
        lines.append("")

    lines.append("## 巡检：0 卡节点（这就是该补的地方）")
    lines.append("")
    empty = [n for n in ns if not node_cards.get(n["node_id"]) and n["column"] != "root"]
    lines.extend(f"- {n['text']}" for n in empty[:100]) if empty else lines.append("- 无")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--chapter", default=None)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if not args.chapter and not args.all:
        ap.error("给 --chapter 试跑，或 --all 全量")

    nodes = [json.loads(l) for l in open(os.path.join(KB, "nodes.jsonl"), encoding="utf-8")]
    cpath = os.path.join(KB, "cards_anchored.jsonl")
    if not os.path.exists(cpath):
        cpath = os.path.join(KB, "cards.jsonl")
    cards = [json.loads(l) for l in open(cpath, encoding="utf-8")]

    node_by_id = {n["node_id"]: n for n in nodes}
    card_by_id = {c["id"]: c for c in cards}
    node_cards = defaultdict(list)
    for c in cards:
        for nid in c.get("kk_anchor") or []:
            if nid in node_by_id:
                node_cards[nid].append(c["id"])

    chapters = defaultdict(list)
    for n in nodes:
        if args.chapter and n["chapter"] != args.chapter:
            continue
        chapters[(n["subject"], n["chapter"])].append(n)

    out = args.out
    os.makedirs(out, exist_ok=True)
    moc_n = card_n = 0

    for (subject, chapter), ns in sorted(chapters.items()):
        chap_dir = os.path.join(out, "01-骨架", safe(chapter))
        os.makedirs(chap_dir, exist_ok=True)

        chap_cards = sorted({cid for n in ns for cid in node_cards.get(n["node_id"], [])})
        card_names = {}
        for cid in chap_cards:
            c = card_by_id.get(cid)
            if c:
                card_names[cid] = f"{safe(cid, 24)}-{safe(c.get('title'), 22)}"

        for cid in chap_cards:
            c = card_by_id.get(cid)
            if not c:
                continue
            d = os.path.join(out, "02-证据卡", KIND_DIR.get(c.get("kind"), "其他卡"))
            os.makedirs(d, exist_ok=True)
            titles = [node_by_id[nid]["text"] for nid in (c.get("kk_anchor") or [])
                      if nid in node_by_id]
            open(os.path.join(d, card_names[cid] + ".md"), "w", encoding="utf-8").write(
                card_md(c, titles))
            card_n += 1

        open(os.path.join(chap_dir, safe(chapter) + ".md"), "w", encoding="utf-8").write(
            moc_md(chapter, subject, ns, node_cards, card_names))
        moc_n += 1

    # vault README：数据来源与重建说明
    open(os.path.join(out, "README.md"), "w", encoding="utf-8").write(
        "# 考研数学笔记库（Obsidian）\n\n"
        "本 vault 由 `D:\\math\\src\\scripts\\export_obsidian.py` 从知识库导出，**不要手改导出结构**；\n"
        "要改内容请改这里的 Markdown，然后用 `obsidian_index.py` 回灌检索索引。\n\n"
        "- `01-骨架/` — 每章一个 MOC，承载 KK 导图节点树，标出 0 卡节点\n"
        "- `02-证据卡/` — 一卡一文件，YAML frontmatter 是结构化字段\n\n"
        "检索：`python src/scripts/query.py --source vault \"查询\" --prompt`\n")

    print(json.dumps({"moc_files": moc_n, "card_files": card_n, "out": out}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
