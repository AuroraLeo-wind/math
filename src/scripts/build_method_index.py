# -*- coding: utf-8 -*-
"""从知识库导出「方法名 | 识别信号 | 适用条件 | 失效边界 | 卡 id | 口语说法」反向索引。

产物:C:\\Users\\PC\\.dsh\\skills\\kaoyan-math-kk\\references\\10-method-index.md
用途:① skill description 的触发词来源 ② 检索换词兜底 ③ 触发评测集的正样本来源

用法: python scripts/build_method_index.py
"""
import json
import os
import re
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS = os.path.join(BASE, "kb", "cards.jsonl")
OUT = os.path.join(os.path.expanduser("~"), ".dsh", "skills", "kaoyan-math-kk", "references", "10-method-index.md")

# 口语说法:方法名关键词 -> 学生会怎么说
COLLOQUIAL = {
    "洛必达": "上下都趋近于0/无穷,能不能直接求导",
    "泰勒": "展开到几阶、添项减项",
    "等价无穷小": "能不能直接替换、相消了怎么办",
    "夹逼": "两端夹住、放缩",
    "罗尔": "端点相等、造一个函数",
    "拉格朗日": "f(b)-f(a)、连接两点",
    "柯西": "两个函数之比",
    "辅助函数": "这个函数怎么想出来的",
    "换元": "看着不像标准形式",
    "分部": "乘积形式积不出来",
    "对称": "区间对称、奇偶",
    "瑕点": "积分发散了、判敛",
    "幂级数": "求和函数、收敛半径",
    "正定": "顺序主子式、化标准形",
    "秩": "几个自由变量",
    "相似": "能不能对角化",
    "特征值": "求 λ、重根怎么办",
    "全概率": "分情况、完备事件组",
    "贝叶斯": "已知结果反推原因",
    "极大似然": "构造似然函数求导",
    "无偏": "估计量好不好",
    "置信区间": "区间估计",
    "假设检验": "拒绝域、原假设",
    "单调有界": "递推数列、证明收敛",
    "零点": "方程有几个根",
}


def readable(s, minlen=3, maxlen=30):
    """只保留"人话":中文字符占比够高、长度合理、不含公式符号"""
    s = (s or "").strip()
    if not (minlen <= len(s) <= maxlen):
        return False
    if re.search(r"[=∼≈≤≥→∫∑√±×·λμσθαβξ∞\[\]{}|\\^_]", s):
        return False
    cjk = len(re.findall(r"[\u4e00-\u9fff]", s))
    return cjk >= max(2, len(s) * 0.5)


def pick_name(c):
    """方法名候选:topic > title 后半 > method_chain[0]"""
    cands = []
    topic = re.sub(r"^题型[一二三四五六七八九十\d]*[:：]\s*", "", c["topic"]).strip()
    if topic:
        cands.append(topic)
    if "：" in c["title"]:
        cands.append(c["title"].split("：")[-1].strip())
    if "｜" in c["title"]:
        cands.append(c["title"].split("｜")[-1].strip())
    if c["method_chain"]:
        cands.append(re.sub(r"^[①②③④⑤⑥⑦⑧\d]+[\.\)、]\s*", "", c["method_chain"][0]).strip())
    cands.append(c["chapter"])
    for x in cands:
        x = x.strip(" ·｜-—")
        if readable(x):
            return x[:30]
    return ""


def pick_col(name):
    for k, v in COLLOQUIAL.items():
        if k in name:
            return v
    return ""


def main():
    cards = [json.loads(l) for l in open(CARDS, encoding="utf-8") if l.strip()]
    methods = [c for c in cards if c["kind"] == "method"]
    # 方法名 = method_chain 第一步 或 title 末尾片段
    rows = []
    for c in methods:
        name = pick_name(c)
        if not name:
            continue  # 名字读不出来的卡不进索引,避免污染触发词
        symptom = next((s for s in c["symptom"] if readable(s, 3, 40)), "")
        if not symptom:
            symptom = c["topic"][:30] if readable(c["topic"], 3, 40) else ""
        cond = next((s for s in c["method_chain"][1:] if readable(s, 3, 40)), "")
        edge = next((s for s in c["pitfall"] if readable(s, 3, 40)), "")
        rows.append({
            "name": name, "symptom": symptom, "cond": cond, "edge": edge,
            "id": c["id"], "col": pick_col(name + " " + c["title"]),
            "subj": c["subject"], "chapter": c["chapter"],
        })

    # 同名方法合并,保留第一条 id,记录出现次数
    merged = {}
    for r in rows:
        k = re.sub(r"[^\u4e00-\u9fffA-Za-z]", "", r["name"])[:12]
        if not k:
            continue
        if k in merged:
            merged[k]["n"] += 1
            if not merged[k]["cond"] and r["cond"]:
                merged[k]["cond"] = r["cond"]
            if not merged[k]["edge"] and r["edge"]:
                merged[k]["edge"] = r["edge"]
            if not merged[k]["col"] and r["col"]:
                merged[k]["col"] = r["col"]
        else:
            r["n"] = 1
            merged[k] = r

    items = sorted(merged.values(), key=lambda x: (x["subj"], -x["n"], x["name"]))
    lines = [
        "# 方法反向索引(方法名 → 症状 → 卡 id)",
        "",
        "> 由 `python scripts/build_method_index.py` 从 `kb/cards.jsonl` 自动导出,勿手改。",
        "> 三个用途:① `SKILL.md` 的 `description` 从这里挑触发词 ② 检索不灵时按方法名反查症状词 ③ 触发评测集的正样本来源。",
        f"> 生成时间基线:方法卡 {len(methods)} 张 → 合并同名后 {len(items)} 条。",
        "",
        "| 方法名 | 识别信号(症状) | 下一步 | 失效边界 | 卡 id | 学生怎么说 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in items:
        def esc(s):
            return (s or "").replace("|", "/").replace("\n", " ").strip()
        lines.append(
            f"| {esc(r['name'])} | {esc(r['symptom'])} | {esc(r['cond'])} | {esc(r['edge']) or '—'} "
            f"| `{r['id']}` | {esc(r['col']) or '—'} |"
        )
    lines += ["", "## 按科目分组的高频方法词(供 description 挑词)", ""]
    for subj in ("高数", "线代", "概率"):
        names = [r["name"] for r in items if r["subj"] == subj][:18]
        lines.append(f"- **{subj}**:{'、'.join(names)}")
    lines += ["", "## 说明", "",
              "- 这是**索引**,不是教程:命中后仍要用 `query.py --id <卡id>` 看原文与出处。",
              "- `失效边界` 为 `—` 的条目,表示笔记原文没写边界,回答时要显式说明这一点,不要自己编。",
              ""]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print(f"方法卡 {len(methods)} 张 → 合并 {len(items)} 条 → {OUT}")
    print("科目分布:", dict(Counter(r["subj"] for r in items)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
