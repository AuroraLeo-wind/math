# -*- coding: utf-8 -*-
"""P2: 把证据卡挂载到 KK 骨架节点上（生成 kk_anchor）。

设计
----
- 骨架节点（kb/nodes.jsonl）是组织轴，证据卡是内容。
- 一张卡可以挂多个节点，但必须有 ≥1 个；低置信挂载进人工抽查队列。
- 匹配在**同章范围内**先缩小，再做词项重叠打分，避免跨章误挂。

输出
----
kb/cards_anchored.jsonl     带 kk_anchor / anchor_score 的卡片
build/anchor_review.tsv     低置信挂载，待人工抽查

用法
----
  python src/scripts/anchor_cards.py            # 全量
  python src/scripts/anchor_cards.py --min 0.2  # 调低阈值(挂得更多)
"""
import argparse
import json
import math
import os
import re
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB = os.path.join(BASE, "kb")
BUILD = os.path.join(BASE, "build")

SUBJ2CODE = {"高数": "GS", "线代": "LD", "概率": "GL", "高等数学": "GS",
             "线性代数": "LD", "概率论": "GL"}
PUNCT = re.compile(r"[\s\u3000·,，。、；;：:!！?？(){}\[\]【】<>《》\"'`~@#$%^&*+=|\\/—\-_…]+")

_jieba = None


def tokenize(text):
    global _jieba
    if _jieba is None:
        import jieba
        jieba.setLogLevel(20)
        _jieba = jieba
        for w in ["洛必达", "泰勒展开", "等价无穷小", "夹逼", "中值定理", "拉格朗日",
                  "罗尔", "柯西", "变限积分", "二重积分", "曲线积分", "曲面积分",
                  "特征值", "特征向量", "二次型", "正定", "相似对角化", "行列式",
                  "随机变量", "分布函数", "数学期望", "极大似然", "无偏估计",
                  "置信区间", "假设检验", "幂级数", "傅里叶", "微分方程"]:
            _jieba.add_word(w)
    text = PUNCT.sub(" ", str(text))
    toks = [t for t in _jieba.lcut_for_search(text) if len(t) > 1 or t.isdigit()]
    return toks


def norm_key(s):
    return re.sub(r"[\s\u3000（）()【】\[\]、，。．\.]", "", str(s or ""))


def card_text(c):
    parts = [c.get("title"), c.get("topic"), c.get("chapter")]
    for f in ("symptom", "tags", "formula"):
        v = c.get(f)
        if isinstance(v, (list, tuple)):
            parts.extend(str(x) for x in v)
    return " ".join(p for p in parts if p)


def node_text(n):
    return " ".join(n.get("path") or [n.get("text", "")])


def score(q, d, min_inter=2):
    """归一化词项重叠：交集 / sqrt(|q|*|d|)，抗长文档偏置。"""
    if not q or not d:
        return 0.0
    inter = len(set(q) & set(d))
    if inter < min_inter:               # 单个词重合不足以证明是同一个知识点(严格档)
        return 0.0
    return inter / math.sqrt(len(set(q)) * len(set(d)))


def score_pair(qt, qp, nt, npth):
    """节点名命中权重高于路径命中：卡的主题应当落在节点本身，而不是祖先章节上。"""
    s_text = score(qt, nt) or score(qt, nt, min_inter=1)
    s_path = score(qt + qp, npth) or score(qt + qp, npth, min_inter=1)
    return max(s_text * 2.0, s_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=float, default=0.15, help="低于此分进人工抽查队列")
    ap.add_argument("--top", type=int, default=3)
    args = ap.parse_args()

    nodes = [json.loads(l) for l in open(os.path.join(KB, "nodes.jsonl"), encoding="utf-8")]
    cards = [json.loads(l) for l in open(os.path.join(KB, "cards.jsonl"), encoding="utf-8")]

    # 索引：章节 -> 节点；章节 -> 已分词节点
    # 挂载池排除书名根与一级栏节点：它们是组织轴，不是内容落点
    by_chapter = defaultdict(list)
    for n in nodes:
        if n["column"] == "root" or n["depth"] <= 1:
            continue
        by_chapter[norm_key(n["chapter"])].append(n)
    toks_cache = {}
    for n in nodes:
        toks_cache[n["node_id"]] = (tokenize(n.get("text", "")),
                                    tokenize(node_text(n)))

    def pick_pool(card):
        """章名双向包含匹配（「函数极限与连续」↔「函数极限」），并限定同科目。"""
        cchap = norm_key(card.get("chapter"))
        code = SUBJ2CODE.get(str(card.get("subject") or ""))
        pool = []
        for k, ns in by_chapter.items():
            if not k or not cchap:
                continue
            if k == cchap or k in cchap or cchap in k:
                pool.extend(n for n in ns if not code or n["subject"] == code)
        return pool

    low, anchored, stats = [], [], defaultdict(int)
    for c in cards:
        pool = pick_pool(c)
        if len(pool) < 5:                  # 章名彻底对不上，才退回同科目全库
            code = SUBJ2CODE.get(str(c.get("subject") or ""))
            pool = [n for n in nodes
                    if n["column"] != "root" and n["depth"] >= 2
                    and (not code or n["subject"] == code)]
            stats["fallback_global"] += 1
        ct = tokenize(card_text(c))
        qt, qp = ct, tokenize(str(c.get("chapter") or ""))
        scored = sorted(((score_pair(qt, qp, *toks_cache[n["node_id"]]), n) for n in pool),
                        key=lambda x: -x[0])[: args.top]
        best = scored[0] if scored else (0.0, None)
        anchors = [n["node_id"] for s, n in scored if s > 0]
        c2 = dict(c)
        c2["kk_anchor"] = anchors
        c2["anchor_score"] = round(best[0], 3)
        anchored.append(c2)
        stats["anchored" if anchors else "unanchored"] += 1
        if not anchors or best[0] < args.min:
            low.append((c.get("id"), c.get("kind"), c.get("chapter"),
                        (best[1]["path"] if best[1] else []), round(best[0], 3),
                        str(c.get("title"))[:60]))

    with open(os.path.join(KB, "cards_anchored.jsonl"), "w", encoding="utf-8") as f:
        for c in anchored:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    os.makedirs(BUILD, exist_ok=True)
    with open(os.path.join(BUILD, "anchor_review.tsv"), "w", encoding="utf-8") as f:
        f.write("card_id\tkind\tchapter\tbest_node_path\tscore\ttitle\n")
        for row in low:
            f.write("\t".join(str(x) for x in row) + "\n")

    total = len(cards)
    ok = stats["anchored"]
    print(json.dumps({
        "cards": total,
        "anchored": ok,
        "unanchored": stats["unanchored"],
        "coverage": round(ok / max(total, 1), 3),
        "low_confidence": len(low),
        "chapter_miss_fallback": stats["fallback_global"],
    }, ensure_ascii=False))
    print(f"-> kb/cards_anchored.jsonl, build/anchor_review.tsv")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()

