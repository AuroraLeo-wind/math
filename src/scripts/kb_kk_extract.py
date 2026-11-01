# -*- coding: utf-8 -*-
"""L1a -> L2: 把 KK 大纲 Markdown 转成知识卡(kind=map / kind=symptom / kind=method)。

产出 D:\\math\\kb\\cards\\KK.jsonl

设计取舍
--------
KK 导图是一张巨型脑图,PDF 文本层的 x0 只能近似表达"深浅",不能可靠还原父子关系。
所以这里**不伪造层级路径**,而是按 KK 自己的四段式板块切卡:
  - 每本书 1 张 `map` 卡:整页节点全文 + 四板块索引(回答"这一章的方法体系是什么")
  - 每个板块 1 张卡:`知识点结构化` -> kind=symptom(这章会出现哪些概念/特征)
                        `解题思路结构化` -> kind=method(方法链条,有序)
                        `题型结构化` -> kind=symptom(题型识别)
                        `通俗理解` -> kind=method
  检索命中具体词(如"脱帽法""万能K值法")时,返回的是它所在的板块卡,raw 里完整保留原始节点文本。
"""
import glob
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTLINE = os.path.join(BASE, "build", "kk_outline")
CARDS_DIR = os.path.join(BASE, "kb", "cards")

SUBJ_RULES = [
    (("行列式", "矩阵", "向量组", "方程组", "相似", "二次型", "特征值", "线性代数", "空间解析几何"), "线代"),
    (("概率", "随机", "大数", "统计量", "参数估计", "数字特征", "中心极限"), "概率"),
]

SECTION_KIND = {
    "知识点结构化": ("symptom", "知识点体系"),
    "通俗理解": ("method", "通俗理解"),
    "解题思路结构化": ("method", "解题思路链条"),
    "题型结构化": ("symptom", "题型识别"),
    "冷门知识点": ("pitfall", "冷门/易漏知识点"),
}

SLUG_CODE = {}


def subject_of(title):
    for kws, s in SUBJ_RULES:
        if any(k in title for k in kws):
            return s
    return "高数"


def parse_outline(md):
    """返回 (title, [(section, [lines])...])"""
    title = ""
    sections = []
    cur = None
    for line in md.splitlines():
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            cur = line[3:].strip()
            sections.append((cur, []))
            continue
        s = line.strip()
        if not s:
            continue
        if cur is None:
            sections.append(("_root", []))
            cur = "_root"
        sections[-1][1].append(s)
    return title, sections


def items_of(lines):
    out = []
    for ln in lines:
        m = re.match(r"^[-\s]*-\s*(.+)$", ln) or re.match(r"^-\s*(.+)$", ln)
        if m:
            out.append(m.group(1).strip())
        else:
            s = re.sub(r"^[-\s]+", "", ln).strip()
            if s:
                out.append(s)
    # 去重保序
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def clean_chapter(t):
    t = re.sub(r"^\(\d+\.\d+(?:\.\d+)?\)--|^\d+\.\d+--", "", t)
    t = re.sub(r"【[^】]*】", "", t)
    t = re.sub(r"^\(\d+\.\d+版\)", "", t)
    t = re.sub(r"\(自测版本?\)|（自测版本?）", "", t)
    return t.strip() or "未分类"


def main():
    os.makedirs(CARDS_DIR, exist_ok=True)
    idx_path = os.path.join(OUTLINE, "_index.json")
    index = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else []
    cards = []
    cnt = {"高数": 0, "线代": 0, "概率": 0}
    for rec in index:
        slug = rec["slug"]
        md_path = os.path.join(BASE, rec["outline_md"])
        if not os.path.exists(md_path):
            continue
        md = open(md_path, encoding="utf-8").read()
        title, sections = parse_outline(md)
        if not title:
            title = rec.get("title") or slug
        title = clean_chapter(title)
        subject = subject_of(title)
        s_code = {"高数": "GS", "线代": "XD", "概率": "GL"}[subject]
        all_text = []
        for sec, lines in sections:
            items = items_of(lines)
            if not items:
                continue
            all_text.append((sec, items))
            kind, label = SECTION_KIND.get(sec, ("method", sec))
            seq = len(cards) + 1
            card = {
                "id": f"KK-{s_code}-{seq:04d}",
                "kind": kind,
                "subject": subject,
                "chapter": title,
                "topic": sec if sec != "_root" else "总览",
                "title": f"{title}｜{sec if sec!='_root' else '总览'}({label})",
                "symptom": [] if kind != "symptom" else items[:12],
                "method_chain": items[:8] if kind == "method" else [],
                "formula": [],
                "pitfall": items[:6] if kind == "pitfall" else [],
                "variants": [],
                "source": {
                    "file": rec["file"], "page": 0, "book": "kk",
                    "locator": f"{title}/{sec}",
                },
                "tags": [title, sec, label],
                "confidence": "explicit",
                "raw": " / ".join(items),
            }
            cards.append(card)
        # 全书总览卡
        if all_text:
            summary = "\n".join(f"- {sec}: {'、'.join(items)}" for sec, items in all_text)
            cards.append({
                "id": f"KK-{s_code}-M{len(cards)+1:04d}",
                "kind": "map",
                "subject": subject,
                "chapter": title,
                "topic": "方法体系全图",
                "title": f"{title}｜方法体系全图(知识点/题型/解题思路三段式)",
                "symptom": [i for sec, items in all_text if "题型" in sec for i in items],
                "method_chain": [i for sec, items in all_text if "解题思路" in sec for i in items],
                "formula": [],
                "pitfall": [],
                "variants": [],
                "source": {"file": rec["file"], "page": 0, "book": "kk", "locator": title},
                "tags": [title, "体系图", "思维导图"],
                "confidence": "explicit",
                "raw": summary,
            })
    out = os.path.join(CARDS_DIR, "KK.jsonl")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        for c in cards:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    from collections import Counter
    print("cards:", len(cards))
    print("by kind:", dict(Counter(c["kind"] for c in cards)))
    print("by subject:", dict(Counter(c["subject"] for c in cards)))
    print("->", out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
