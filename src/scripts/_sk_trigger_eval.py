# -*- coding: utf-8 -*-
"""_sk_trigger_eval.py — skill 触发判别力评测(临时调研脚本)

思路:模型选 skill 时唯一可见的是 <available_skills> 里的 name + description。
所以「description 能不能把用户原话拉到自己头上」可以先用纯文本相似度做代测:
把全部已装 skill 的 name+description 建 BM25 索引,对每条用户问句算排序,
正确 skill 是否排第一 —— 这就是触发准确率的上界估计(不需要调模型,零成本可回归)。

用法:
    python scripts\\_sk_trigger_eval.py                       # 默认 ~/.dsh/skills
    python scripts\\_sk_trigger_eval.py --root C:\\path\\skills
    python scripts\\_sk_trigger_eval.py --verbose
    python scripts\\_sk_trigger_eval.py --json build\\_sk_trigger.json
"""
import argparse
import io
import json
import math
import os
import re
import sys

import yaml

# ---------------------------------------------------------------- 数据集
# expect = 正确的 skill 名;expect = None 表示「哪个都不该触发」(近义负样本)
QUERIES = [
    # ---- 应为 kaoyan-math-kk 触发(正样本,10 条:措辞/显式度/长度各异)----
    ("这题极限怎么想,分子分母都趋近于零", "kaoyan-math-kk"),
    ("帮我看看这道二重积分的思路,区域是圆环", "kaoyan-math-kk"),
    ("中值定理这题为什么构造不出辅助函数", "kaoyan-math-kk"),
    ("特征值和二次型这块的题型方法帮我理一下", "kaoyan-math-kk"),
    ("我这步错在哪:洛必达之后忘了验证条件", "kaoyan-math-kk"),
    ("随机变量的分布函数求期望方差,给个标准解法", "kaoyan-math-kk"),
    ("和笔记对照一下,我记的这套方法对不对", "kaoyan-math-kk"),
    ("概率论参数估计和假设检验考什么", "kaoyan-math-kk"),
    ("行列式化简到上三角有没有套路", "kaoyan-math-kk"),
    ("无穷级数判敛这题卡住了", "kaoyan-math-kk"),

    # ---- 近义负样本:同样是"数学/解题/文档",但该走别的路或不用 skill ----
    ("帮我把这个 PDF 里的公式截图导出来", None),
    ("用 Python 写个脚本解线性方程组", None),
    ("帮我生成一份数学建模竞赛的论文框架", None),
    ("帮我给这个项目写单元测试,用红绿重构", "tdd"),
    ("这个函数偶发报错,帮我诊断一下", "diagnose"),
    ("把这份需求拆成可领取的 issue", "to-issues"),
    ("先拷问我这个方案的设计", "grill-me"),
    ("扫描这个仓库生成架构导读", "repo-wiki"),
    ("帮我把对话整理成 PRD", "to-prd"),
    ("给这个 issue 分拣一下优先级", "triage"),

    # ---- 完全无关:验证不会乱触发 ----
    ("今天北京天气怎么样", None),
    ("帮我订一张明天去上海的高铁票", None),
    ("把这段英文翻译成中文", None),
    ("推荐几本好看的小说", None),
    ("帮我看看这张图片里有什么", None),
    ("numpy 的 einsum 怎么用", None),
]

STOP = set("的 了 是 在 我 你 他 这 那 个 和 与 或 就 都 也 很 要 会 能 把 被 让 给 对 a an the of to and or for in on with is are".split())


def tokens(text):
    text = text.lower()
    latin = re.findall(r"[a-z0-9][a-z0-9\-_.+]*", text)
    cjk_runs = re.findall(r"[\u4e00-\u9fff]+", text)
    grams = []
    for run in cjk_runs:
        if len(run) == 1:
            grams.append(run)
        for i in range(len(run) - 1):
            grams.append(run[i:i + 2])
    return [t for t in latin + grams if t not in STOP and len(t) > 1 or (len(t) == 1 and re.match(r"[a-z0-9]", t))]


def load_skills(root):
    out = []
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d)
        md = os.path.join(p, "SKILL.md")
        if not (os.path.isdir(p) and os.path.isfile(md)):
            continue
        raw = open(md, encoding="utf-8").read()
        m = re.match(r"^---\r?\n(.*?)\r?\n---", raw, re.S)
        fm = {}
        if m:
            try:
                fm = yaml.safe_load(m.group(1)) or {}
            except Exception:  # noqa: BLE001
                fm = {}
        out.append({
            "name": fm.get("name", d),
            "dir": d,
            "description": str(fm.get("description", "")),
        })
    return out


class BM25:
    def __init__(self, docs, k1=1.2, b=0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.tf = [{} for _ in docs]
        df = {}
        for i, d in enumerate(docs):
            for t in d:
                self.tf[i][t] = self.tf[i].get(t, 0) + 1
            for t in set(d):
                df[t] = df.get(t, 0) + 1
        self.N = len(docs)
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}
        self.avg = (sum(sum(x.values()) for x in self.tf) / self.N) if self.N else 0

    def score(self, i, q):
        s, dl = 0.0, sum(self.tf[i].values())
        for t in q:
            if t not in self.tf[i]:
                continue
            f = self.tf[i][t]
            s += self.idf.get(t, 0) * (f * (self.k1 + 1)) / (
                f + self.k1 * (1 - self.b + self.b * dl / (self.avg or 1)))
        return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(os.path.expanduser("~"), ".dsh", "skills"))
    ap.add_argument("--set", default=None, help="评测集 jsonl,每行 {q, expect, tags}")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    global QUERIES
    if args.set:
        QUERIES = []
        for line in io.open(args.set, encoding="utf-8-sig"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            QUERIES.append((r["q"], r.get("expect")))
        print("评测集 %s: %d 条" % (args.set, len(QUERIES)))

    skills = load_skills(args.root)
    if not skills:
        print("没找到 skill:", args.root)
        return 2

    docs = [tokens(s["name"] + " " + s["description"]) for s in skills]
    bm = BM25(docs)

    pos = neg = 0
    pos_top1 = neg_clean = neg_clean_floor = 0
    mrr = 0.0
    rows, fails, missing_kw = [], [], {}
    FLOOR = 2.5   # top1 分数低于此值,视为"没有真正命中",模型不会触发

    names = [s["name"] for s in skills]
    TARGET = "kaoyan-math-kk"

    for q, expect in QUERIES:
        qs = tokens(q)
        ranked = sorted(range(len(skills)), key=lambda i: -bm.score(i, qs))
        top = skills[ranked[0]]["name"]
        scores = [bm.score(i, qs) for i in ranked]
        margin = (scores[0] - scores[1]) if len(scores) > 1 else scores[0]
        target_score = bm.score(names.index(TARGET), qs) if TARGET in names else None
        top1_meaningful = scores[0] >= FLOOR

        if expect:
            pos += 1
            if expect not in names:
                fails.append((q, expect, "SKILL-MISSING", top, margin))
            else:
                rank = ranked.index(names.index(expect)) + 1
                mrr += 1.0 / rank
                if rank == 1:
                    pos_top1 += 1
                else:
                    fails.append((q, expect, "rank=%d" % rank, top, margin))
                    if expect == TARGET:
                        dt = set(docs[names.index(TARGET)])
                        missing_kw[q] = sorted(set(qs) - dt)
        else:
            neg += 1
            if top != TARGET:
                neg_clean += 1
            if top != TARGET or not top1_meaningful:
                neg_clean_floor += 1
            else:
                fails.append((q, "None", "-", top, margin))

        rows.append({"query": q, "expect": expect, "top1": top,
                     "top1_score": round(scores[0], 2),
                     "target_score": None if target_score is None else round(target_score, 2),
                     "margin": round(margin, 2)})

        if args.verbose:
            ok = (expect == top) if expect else (top != TARGET)
            print("[%s] %-44s top1=%-24s s=%.2f margin=%.2f"
                  % ("OK  " if ok else "MISS", q[:42], top, scores[0], margin))

    n = len(QUERIES)
    print("\n== 触发判别力(纯 description 相似度代测,零模型调用)==")
    print("skill 总数                  : %d" % len(skills))
    print("正样本 top1 命中             : %d/%d = %.1f%%" % (pos_top1, pos, 100.0 * pos_top1 / pos))
    print("正样本 MRR                  : %.3f" % (mrr / pos))
    print("负样本 严格未误触(排第一)     : %d/%d = %.1f%%"
          % (neg_clean, neg, 100.0 * neg_clean / neg))
    print("负样本 阈值化未误触(score<%.1f) : %d/%d = %.1f%%"
          % (FLOOR, neg_clean_floor, neg, 100.0 * neg_clean_floor / neg))
    print("平均 top1-top2 分差(margin) : %.2f  (越小越容易被别家抢走)"
          % (sum(r["margin"] for r in rows) / n))

    if missing_kw:
        print("\n目标 skill 未命中的问句里,description 缺哪些词(二字片段,可直接抄进 description):")
        for q, kws in missing_kw.items():
            kws = sorted(set(kws), key=lambda t: (-len(t), t))[:10]
            print("  %s\n    缺: %s" % (q, " ".join(kws)))

    if fails:
        print("\n未过用例:")
        for q, expect, rank, top, margin in fails:
            print("  Q: %s\n     期望=%-24s 实得top1=%-24s %s margin=%.2f"
                  % (q, expect, top, rank, margin))

    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"skills": [s["name"] for s in skills], "rows": rows,
                       "pos_top1": pos_top1, "pos": pos, "neg_clean": neg_clean,
                       "neg": neg, "mrr": mrr / pos,
                       "avg_margin": sum(r["margin"] for r in rows) / n},
                      f, ensure_ascii=False, indent=2)
        print("\nJSON ->", args.json)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
