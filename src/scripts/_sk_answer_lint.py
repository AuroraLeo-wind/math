# -*- coding: utf-8 -*-
"""_sk_answer_lint.py — skill 输出结构合规率检查(临时调研脚本)

把「skill 写得好不好」拆成两个可测的数字:
  1) 触发准确率        -> scripts\\_sk_trigger_eval.py
  2) 输出结构合规率    -> 本脚本

本脚本按 kaoyan-math-kk 的四要素契约(SKILL.md §2/§6)检查一份回答:
    ① 特征识别 ② 方法定位 ③ 逻辑链条 ④ 结构化复盘 ⑤ 自检    + 出处硬要求 + LaTeX

用法:
    python scripts\\_sk_answer_lint.py --selftest              # 用内置正/反样例自检
    python scripts\\_sk_answer_lint.py build\\ask.md            # 检查单份回答
    python scripts\\_sk_answer_lint.py --dir build\\answers      # 批量,输出合规率
"""
import argparse
import glob
import io
import json
import os
import re
import sys

# ------------------------------------------------------------------ 契约
SECTIONS = [
    ("①", "特征识别", r"(①|特征识别)"),
    ("②", "方法定位", r"(②|方法定位)"),
    ("③", "逻辑链条", r"(③|逻辑链条)"),
    ("④", "结构化复盘", r"(④|结构化复盘)"),
    ("⑤", "自检", r"(⑤|自检|收尾三问)"),
]
CARD_ID = re.compile(r"\[((?:KK|EP|DX|ZY)-[A-Z0-9\-]+)\]")
SRC_PAGE = re.compile(r"p\.?\s*\d+|p\d+|第\s*\d+\s*页")
LATEX = re.compile(r"\$[^$\n]{2,}\$|\\\[.{2,}\\\]|\\\(.{2,}\\\)", re.S)
EMPTY_TALK = re.compile(r"(希望对你有帮助|本题考察了.{0,6}能力|综上所述,我们可以看出)")


def load_ids(kb_path):
    ids = set()
    if not os.path.isfile(kb_path):
        return ids
    with io.open(kb_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line)["id"])
            except Exception:  # noqa: BLE001
                continue
    return ids


def check(text, known_ids):
    res = []

    def add(name, passed, detail=""):
        res.append({"check": name, "passed": bool(passed), "detail": detail})

    # 1) 五段齐全 + 顺序
    hits, positions = [], []
    for mark, label, pat in SECTIONS:
        m = re.search(pat, text)
        hits.append((label, bool(m)))
        positions.append(m.start() if m else -1)
    missing = [lb for lb, ok in hits if not ok]
    add("五段结构齐全", not missing, "缺 " + ",".join(missing) if missing else "①~⑤ 全在")

    found = [p for p in positions if p >= 0]
    add("五段顺序正确", found == sorted(found), "出现位置 %s" % positions)

    # 2) 引用硬要求
    cited = CARD_ID.findall(text)
    add("至少 1 个卡片引用", bool(cited), "引用 %d 处" % len(cited))
    bad = [c for c in cited if known_ids and c not in known_ids]
    add("引用 id 都真实存在", not bad, ("编造 id: " + ",".join(sorted(set(bad))[:5])) if bad else "全部命中 kb")

    # 3) 未命中时必须声明
    disclaim = re.search(r"笔记库未命中|笔记里没有直接对应", text)
    if cited:
        add("未命中声明(有引用时不要求)", True, "有引用,跳过")
    else:
        add("未命中声明(无引用时必须写)", bool(disclaim), "缺 `> 笔记库未命中…` 一行")

    # 4) 出处格式:引用旁边要有页码/文件名
    if cited and not SRC_PAGE.search(text):
        add("引用附页码/文件名", False, "未找到 p页码 形式")
    else:
        add("引用附页码/文件名", True, "ok" if cited else "无引用,跳过")

    # 5) LaTeX
    has_tex = bool(LATEX.search(text))
    add("含 LaTeX 公式", has_tex, "ok" if has_tex else "未找到 $...$")

    # 6) 空话
    m = EMPTY_TALK.search(text)
    add("无套话", not m, ("出现: " + m.group(1)) if m else "ok")

    # 7) 编号步骤(逻辑链条必须逐条)
    steps = len(re.findall(r"^\s*(?:\d+[\.\)、]|[（(]\d+[）)])", text, re.M))
    add("逻辑链条有编号步骤(>=3)", steps >= 3, "编号步骤 %d 个" % steps)

    passed = sum(1 for r in res if r["passed"])
    return res, passed, len(res)


SAMPLE_GOOD = """① 特征识别
- 分子分母同为加减结构 → [KK-GS-0001] kk函数极限.pdf p3
② 方法定位
主选:泰勒展开定阶 [KK-GS-0001]
③ 逻辑链条
1. 先判断是否相消
2. 相消则展开到第一个非零项 $\\sin x = x - x^3/6 + o(x^3)$
3. 用展开阶定阶
④ 结构化复盘
题型归属:极限定阶;陷阱:等价无穷小丢阶
⑤ 自检
1. 边界条件用到了吗 2. 能验证吗 3. 有更短路径吗
"""

SAMPLE_BAD = """这道题考察了极限计算能力。
首先用等价无穷小替换,sin x ~ x,所以原式等于 1。
相关笔记见 references/xxx.md,希望对你有帮助。
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", default=None)
    ap.add_argument("--dir", default=None)
    ap.add_argument("--kb", default=os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "kb", "cards.jsonl"))
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    known = load_ids(args.kb)
    print("kb 载入卡片 id: %d" % len(known))

    targets = []
    if args.selftest:
        targets = [("<内置-合规样例>", SAMPLE_GOOD), ("<内置-反面样例>", SAMPLE_BAD)]
    elif args.dir:
        for p in sorted(glob.glob(os.path.join(args.dir, "*.md"))):
            targets.append((p, io.open(p, encoding="utf-8").read()))
    elif args.file:
        targets.append((args.file, io.open(args.file, encoding="utf-8").read()))
    else:
        print("给 --selftest / 文件 / --dir")
        return 2

    total_p = total_n = 0
    for name, text in targets:
        res, passed, n = check(text, known)
        total_p += passed
        total_n += n
        print("\n=== %s  合规 %d/%d = %.0f%% ===" % (name, passed, n, 100.0 * passed / n))
        for r in res:
            print("  [%s] %-28s %s" % ("PASS" if r["passed"] else "FAIL", r["check"], r["detail"]))

    print("\n总体结构合规率: %d/%d = %.1f%%" % (total_p, total_n, 100.0 * total_p / total_n))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
