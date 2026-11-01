# -*- coding: utf-8 -*-
"""DX 源抽取:27 大雪深埋做题本(高数 / 线代 / 概率) -> 结构化知识卡。

输入(已抽好的页级 JSONL,不重新解析 PDF):
    build/pages/(3.1)--27大雪深埋做题本（高等数学）__*.jsonl     159 页
    build/pages/(3.2)--27大雪深埋做题本（线代）__*.jsonl          56 页
    build/pages/(3.3)--大雪深埋概率论电子版（含解析）__*.jsonl     53 页
    build/pages/(3.4)--27大雪深埋概率论做题本__*.jsonl            43 页

输出:
    kb/cards/DX.jsonl   一行一张卡,遵守 docs/02-schema.md

切分规则
--------
1. 以 ``【例N】`` 为切点;题面 + 后续 ``【解析】`` 同属一张 ``kind=example`` 卡。
2. 页眉页脚按几何位置过滤(``y1<=40`` 页眉条、``y0>=789`` 页脚条),再叠加
   文案过滤(扫码 / 公众号 / 抖音 / By epsilon-delta / 27考研讲义条)。
3. 跨页题:整册按页序拼成一条连续行流,``【例N】`` 之前的内容天然归属该题,
   所以"题面在上页 / 解析在下页"自动拼起来;另外对 OCR 版式造成的
   "公式碎片排到题号前面"(如 ``【例18】… xn=`` 而积分式留在上一题尾部)
   做一次回补(``repair_truncated_stems``)。
4. 去重:同一题在多份文件重复时(概率 3.3 与 3.4 完全同题),比较归一化题面
   前缀,保留 ``raw`` 更长的一份。

用法::

    $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
    python scripts\\kb_dx_extract.py                 # 抽取 + 落盘 + 统计 + 抽样自检
    python scripts\\kb_dx_extract.py --no-write      # 只看统计,不写文件
    python scripts\\kb_dx_extract.py --sample 8      # 抽样自检张数
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import re
import sys
from collections import Counter, OrderedDict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES_DIR = os.path.join(BASE, "build", "pages")
OUT_PATH = os.path.join(BASE, "kb", "cards", "DX.jsonl")

# 页边距阈值(单位 pt,页面高 841.9)。实测:内容块 y1 最大 781.7,y0 最小 45。
MARGIN_TOP = 40.0
MARGIN_BOT = 789.0

# ---------------------------------------------------------------- 输入清单
SOURCES = [
    {
        "key": "3.1",
        "pattern": "(3_1)*.jsonl",
        "subject": "高数",
        "scode": "GS",
        "has_analysis": False,
    },
    {
        "key": "3.2",
        "pattern": "(3_2)*.jsonl",
        "subject": "线代",
        "scode": "XD",
        "has_analysis": False,
    },
    {
        "key": "3.3",
        "pattern": "(3_3)--大雪深埋概率论电子版*.jsonl",
        "subject": "概率",
        "scode": "GL",
        "has_analysis": True,
    },
    {
        "key": "3.4",
        "pattern": "(3_4)*.jsonl",
        "subject": "概率",
        "scode": "GL",
        "has_analysis": False,
    },
]

# 页眉页脚文案特征(命中即视为版式噪声)
BOILER_KEYS = (
    "扫码了解更多课程",
    "27考研：epsilon",
    "27考研:epsilon",
    "关注公主号",
    "抖音/小红书",
    "By epsilon-delta",
    "大雪深埋强化课讲义",
)

EXAMPLE_RE = re.compile(r"【例\s*(\d{1,3})\s*】")
TOPIC_RE = re.compile(r"^题型\s*[一二三四五六七八九十0-9]+\s*[：:]")
PURE_NUM_RE = re.compile(r"^\d{1,3}$")
CJK_ONLY_RE = re.compile(r"^[\u4e00-\u9fff（）()、·]+$")
PAREN_NUM_RE = re.compile(r"^[（(][一二三四五六七八九十0-9]+[)）]")

# 题面"续行"特征:说明题面被页边界或版式截断
OPEN_TAIL_RE = re.compile(r"(=|＝|\+|-|−|×|\*|/|,|，|、|∫|∑|lim|max|min|\(|（)\s*$")
MATH_SYM = set("=+−-×*/∫∑∞≤≥√()（）｜|")

TERM_PUNCT = "。．.；;？?）)"


# ---------------------------------------------------------------- 版面工具
def is_boiler(line: str) -> bool:
    return any(k in line for k in BOILER_KEYS)


def page_layout(page: dict):
    """切出页眉/页脚块,返回 (页眉行集合, 页脚行集合, 印刷页码)。"""
    hdr_lines, ftr_lines = set(), set()
    pageno = None
    for b in page.get("blocks", []):
        t = (b.get("text") or "").strip()
        if not t:
            continue
        if b.get("y1", 1e9) <= MARGIN_TOP:                      # 页眉条
            for ln in t.split("\n"):
                if ln.strip():
                    hdr_lines.add(ln.strip())
        elif b.get("y0", -1e9) >= MARGIN_BOT:                   # 页脚条
            for ln in t.split("\n"):
                ln = ln.strip()
                if not ln:
                    continue
                if PURE_NUM_RE.match(ln):
                    pageno = ln
                else:
                    ftr_lines.add(ln)
    return hdr_lines, ftr_lines, pageno


def header_chapter(page: dict) -> str | None:
    """页眉条里的章名(GS/XD 恒有,GL 隔页出现)。"""
    for b in page.get("blocks", []):
        t = (b.get("text") or "").strip()
        if not t or b.get("y1", 1e9) > MARGIN_TOP:
            continue
        for ln in t.split("\n"):
            ln = ln.strip()
            if ln and not is_boiler(ln) and len(ln) <= 24:
                return ln
    return None


def title_block(page: dict) -> str | None:
    """章首页的大标题块(y0≈67,纯中文短串)。"""
    for b in page.get("blocks", []):
        t = (b.get("text") or "").strip().replace("\n", "")
        y0 = b.get("y0", -1)
        if 55.0 <= y0 <= 95.0 and 2 <= len(t) <= 20 and CJK_ONLY_RE.match(t):
            if PAREN_NUM_RE.match(t) or is_boiler(t) or t.startswith("【"):
                continue
            return t
    return None


def clean_lines(page: dict, title: str | None) -> list[str]:
    """按行清洗一页正文:去掉页眉页脚、页码、章名大标题。"""
    hdr_lines, ftr_lines, pageno = page_layout(page)
    title_dropped = False
    out: list[str] = []
    for raw in (page.get("text") or "").split("\n"):
        ln = raw.strip()
        if not ln:
            continue
        if is_boiler(ln):
            continue
        if ln in hdr_lines or ln in ftr_lines:
            continue
        if title and not title_dropped and ln == title and not out:
            title_dropped = True
            continue
        out.append(ln)
    # 印刷页码:只掐掉出现在页首/页尾的那一个
    if pageno:
        if out and out[-1] == pageno:
            out.pop()
        elif out and out[0] == pageno:
            out.pop(0)
    return out


# ---------------------------------------------------------------- 章节识别
def is_subsequence(short: str, long: str) -> bool:
    it = iter(long)
    return all(ch in it for ch in short)


def related_chapter(a: str, b: str) -> bool:
    """章名变体判定:页眉简称 vs 章首全称(一元微分学 / 一元函数微分学)。

    用"短串是否为长串子序列"+长度比,挡掉正文里的短中文块(如"因此")。
    """
    if not a or not b:
        return False
    if a == b:
        return True
    s, l = (a, b) if len(a) <= len(b) else (b, a)
    if len(s) / len(l) < 0.5:
        return False
    return is_subsequence(s, l)


def build_chapter_index(pages: list[dict]):
    """返回 (每页章名 dict, 页眉名->正式章名 映射, 章名出现顺序)。"""
    headers = [header_chapter(p) for p in pages]
    header_names = {h for h in headers if h}

    # 只有"与某个页眉章名同源"的标题块才认作章名,挡掉正文里的短中文块(如"因此")
    hdr2title: dict[str, str] = {}
    for p, h in zip(pages, headers):
        t = title_block(p)
        if h and t and related_chapter(h, t):
            if len(t) > len(hdr2title.get(h, "")):
                hdr2title[h] = t

    chapter_by_page: dict[int, str] = {}
    running = None
    for p, h in zip(pages, headers):
        t = title_block(p)
        if h:
            running = hdr2title.get(h, h)
        elif t and any(related_chapter(t, hn) for hn in header_names):
            running = t
        chapter_by_page[p["page"]] = running
    # 章名顺序(按首次出现)
    order: list[str] = []
    for p in pages:
        ch = chapter_by_page[p["page"]]
        if ch and ch not in order:
            order.append(ch)
    return chapter_by_page, hdr2title, order


# ---------------------------------------------------------------- 抽卡
def new_card(no: int, chapter: str, page: int, fname: str, topic_label: str | None):
    return {
        "no": no,
        "chapter": chapter,
        "page": page,
        "page_end": page,
        "file": fname,
        "topic_label": topic_label,
        "stem": [],
        "analysis": [],
    }


def add_line(card: dict, line: str, mode: str, page: int):
    card["page_end"] = max(card["page_end"], page)
    if mode == "analysis":
        card["analysis"].append(line)
    else:
        card["stem"].append(line)


def is_topic_heading(line: str) -> bool:
    return bool(TOPIC_RE.match(line)) and len(line) <= 40


def collect_cards(pages: list[dict], chapter_by_page: dict[int, str],
                  known_chapters: set[str]) -> tuple[list[dict], dict, list[dict]]:
    cards: list[dict] = []
    preambles: list[dict] = []
    cur: dict | None = None
    cur_pre: dict | None = None
    mode = "stem"
    cur_topic: str | None = None
    stat = {"题号总数": 0, "非例块丢弃": 0, "题型标题": 0}

    def flush_pre():
        nonlocal cur_pre
        if cur_pre and cur_pre["lines"]:
            preambles.append(cur_pre)
        cur_pre = None

    for p in pages:
        ch = chapter_by_page.get(p["page"])
        fname = p.get("file", "")
        title = title_block(p)
        lines = clean_lines(p, title)
        for ln in lines:
            # 章节切换 -> 结束当前卡(卡不跨章)
            if cur is not None and ch and cur["chapter"] and ch != cur["chapter"]:
                cards.append(cur)
                cur = None
                mode = "stem"
                cur_topic = None
                flush_pre()
            if is_topic_heading(ln):
                if cur is not None:
                    cards.append(cur)
                    cur = None
                flush_pre()
                cur_topic = TOPIC_RE.sub("", ln).strip().rstrip("：: ")
                mode = "stem"
                stat["题型标题"] += 1
                continue
            m = EXAMPLE_RE.match(ln)
            if m:
                if cur is not None:
                    cards.append(cur)
                flush_pre()                     # 题目开始,铺垫段结束
                stat["题号总数"] += 1
                cur = new_card(int(m.group(1)), ch or "", p["page"], fname, cur_topic)
                cur["stem"].append(ln)
                mode = "stem"
                continue
            if cur is None:
                # 章首或"题型N："下的公式/定义/结论 —— 收进铺垫段,后面抽 method/pitfall 卡
                if ln and not is_boiler(ln):
                    stat["非例块丢弃"] += 1
                    if cur_pre is None:
                        cur_pre = {
                            "chapter": ch or "",
                            "topic_label": cur_topic,
                            "page": p["page"],
                            "page_end": p["page"],
                            "file": fname,
                            "lines": [],
                        }
                    cur_pre["lines"].append(ln)
                    cur_pre["page_end"] = max(cur_pre["page_end"], p["page"])
                continue
            if "【解析】" in ln:
                head, _, tail = ln.partition("【解析】")
                if head.strip():
                    cur["stem"].append(head.strip())
                mode = "analysis"
                cur["page_end"] = max(cur["page_end"], p["page"])
                if tail.strip():
                    cur["analysis"].append(tail.strip())
                continue
            add_line(cur, ln, mode, p["page"])
    if cur is not None:
        cards.append(cur)
    flush_pre()
    return cards, stat, preambles


def repair_truncated_stems(cards: list[dict]) -> list[tuple]:
    """OCR 版式修复:题号块的公式碎片被排到上一题尾部时,把碎片搬回来。

    只在"当前题面明显没写完"时触发(以 ``=`` ``∫`` ``(`` 等开符号结尾),
    从上一题同章的尾部自后向前搬 1~3 行"数学碎片行";搬动的都是纯公式/数字行,
    不会把上一题的正文段落带走。
    """
    repairs = []
    for i, card in enumerate(cards):
        if i == 0 or not card["stem"]:
            continue
        stem_txt = "".join(card["stem"]).strip()
        if not stem_txt or not OPEN_TAIL_RE.search(stem_txt):
            continue
        prev = cards[i - 1]
        if prev["chapter"] != card["chapter"] or not prev["stem"]:
            continue
        moved: list[str] = []
        budget = 0
        for ln in reversed(prev["stem"]):
            s = ln.strip()
            if not s or len(s) > 60 or budget + len(s) > 130:
                break
            if is_boiler(s) or s.startswith("【"):
                break
            if re.match(r"^[（(]?[ABCD][).、）]", s):        # 选项行不动
                break
            if re.match(r"^[（(]\d+[)）]", s):               # (1)(2) 小问不动
                break
            has_math = any(c in MATH_SYM for c in s) or PURE_NUM_RE.match(s) is not None
            if not has_math or s.endswith(TERM_PUNCT) and not any(
                    c in s for c in "=+−-×/∫∑") and len(s) > 20:
                break
            moved.append(prev["stem"].pop())
            budget += len(s)
            if len(moved) >= 3:
                break
        if not moved:
            continue
        moved.reverse()
        head = card["stem"][0]
        rest = card["stem"][1:]
        card["stem"] = [head] + moved + rest
        repairs.append((prev["no"], card["no"], card["chapter"], " ".join(moved)[:50]))
    return repairs


# ---------------------------------------------------------------- 字段提炼
KEYWORD_TABLE = {
    # 高数
    "函数极限": ["等价无穷小", "无穷小量", "无穷大量", "间断点", "未定式", "洛必达", "泰勒展开", "连续", "极限存在", "定阶", "脱帽"],
    "数列极限": ["单调有界", "夹逼", "递推", "子列", "数列收敛", "极限存在", "单调增加", "压缩映射"],
    "一元函数微分学": ["导数定义", "可导", "高阶导数", "拐点", "曲率", "渐近线", "参数方程", "左右导数", "连续但不可导"],
    "一元微分学": ["导数定义", "可导", "高阶导数", "拐点", "曲率", "渐近线", "参数方程", "左右导数"],
    "方程根与零点问题": ["零点定理", "实根", "根的个数", "单调性", "介值"],
    "中值定理": ["罗尔定理", "拉格朗日中值定理", "柯西中值定理", "构造辅助函数", "双中值", "存在ξ", "介值"],
    "泰勒公式": ["泰勒展开", "拉格朗日余项", "皮亚诺余项", "麦克劳林", "展开阶"],
    "凹凸性": ["凹凸性", "拐点", "单调", "凸函数", "琴生"],
    "不定积分与定积分": ["变限积分", "换元", "分部积分", "反常积分", "定积分计算", "原函数", "积分上限"],
    "积分不等式": ["积分不等式", "放缩", "柯西不等式", "单调函数", "积分中值"],
    "多元微分学": ["偏导数", "全微分", "隐函数", "条件极值", "方向导数", "梯度", "拉格朗日乘数"],
    "二重积分": ["二重积分", "交换积分次序", "极坐标", "对称性", "积分区域"],
    "微分方程": ["微分方程", "通解", "特解", "一阶线性", "齐次", "特征方程", "可降阶"],
    "保号性": ["保号性", "极限保号", "局部保号", "单调递减"],
    "微积分应用": ["旋转体", "弧长", "曲率", "做功", "侧压力", "引力", "形心", "几何应用"],
    "无穷级数": ["收敛半径", "幂级数", "敛散性", "绝对收敛", "条件收敛", "交错级数", "和函数", "傅里叶"],
    "三重积分": ["三重积分", "柱坐标", "球坐标", "投影"],
    "曲线曲面积分": ["格林公式", "高斯公式", "斯托克斯公式", "曲线积分", "曲面积分", "路径无关", "通量"],
    # 线代
    "行列式和矩阵": ["行列式", "伴随矩阵", "矩阵的秩", "初等变换", "逆矩阵", "分块矩阵", "正交矩阵"],
    "向量组与方程组": ["线性相关", "线性无关", "基础解系", "通解", "极大无关组", "秩", "同解", "公共解", "等价"],
    "相似理论": ["特征值", "特征向量", "相似对角化", "可对角化", "相似", "秩为1"],
    "二次型理论": ["二次型", "正定", "合同", "惯性指数", "标准形", "规范形", "正交变换"],
    # 概率
    "随机事件与概率": ["全概率公式", "贝叶斯公式", "条件概率", "独立性", "古典概型", "几何概型", "事件的运算", "对立事件"],
    "一维随机变量（函数）及其分布": ["分布函数", "概率密度", "离散型", "连续型", "随机变量函数", "正态分布", "均匀分布", "指数分布"],
    "多维随机变量（函数）及其分布": ["边缘分布", "条件分布", "联合分布", "独立性", "二维随机变量", "卷积"],
    "随机变量的数字特征": ["数学期望", "方差", "协方差", "相关系数", "矩", "不相关"],
    "大数定律和中心极限定理": ["大数定律", "中心极限定理", "切比雪夫", "辛钦", "依概率收敛"],
    "统计量及其分布": ["统计量", "样本均值", "样本方差", "卡方分布", "t分布", "F分布", "抽样分布"],
    "参数估计和假设检验": ["矩估计", "极大似然估计", "无偏性", "有效性", "一致性", "置信区间", "假设检验", "拒绝域", "两类错误"],
}

GENERIC_KEYWORDS = ["极限", "导数", "积分", "级数", "矩阵", "向量", "特征值", "分布", "概率", "期望", "方差", "估计", "检验"]

# 关键词表没命中时的结构兜底(只看题面写法,不做知识推断)
STRUCT_TOPIC = [
    # \uf046 是 OCR 出来的积分号私用区字形
    (r"dx\s*dy|dxdy|d\s*σ|dσ|∫|\uf046|d\s*x", "积分计算"),
    (r"lim", "求极限"),
    (r"(证明|求证)", "证明推理"),
    (r"(收敛|发散|敛散)", "敛散性判定"),
    (r"(分布函数|概率密度)", "分布与密度"),
]

ASK_RULES = [
    (r"下列.{0,12}(正确|错误|不成立|成立|为假命题|真命题)", "判断命题/选项真伪"),
    (r"(证明|求证|试证)", "证明/求证"),
    (r"(求|计算).{0,6}(极限|lim)", "求极限"),
    (r"(敛散性|收敛|发散)", "判断敛散性"),
    (r"(求|计算)", "求值/求表达式"),
    (r"计算", "计算"),
    (r"(判断|讨论)", "讨论/判断"),
]

STRUCT_RULES = [
    (r"①[\s\S]{0,400}④", "题面用①②③④列多条命题，需逐条判定"),
    (r"[（(]\s*[)）]", "设问留空的选择/填空位，先定结论再验算"),
    (r"x\s*n?\s*\+?\s*1\s*=|x_?\{?n\+1", "由递推关系定义数列，需先证收敛再求极限"),
    (r"[（(]\s*1\s*[)）][\s\S]{0,200}[（(]\s*2\s*[)）]", "多小问递进，后问依赖前问结论"),
    (r"(仅数一|仅数二|仅数一数二)", "标注了适用卷种（数一/数二），可跳过不考项"),
]

PARAM_RE = re.compile(r"(为任意常数|待定|讨论\s*[a-zA-Zλμθ]|参数\s*[a-zA-Zλμθ]|\bλ\b|\bθ\b)")
# 选项标记:(A) / A. / A、——字母后必须紧跟括号或点号,否则 "A 为3阶矩阵" 会误判
OPTION_RE = re.compile(r"[（(]([ABCD])[)）]|(?:^|\s)([ABCD])[.．、]")


def is_choice_question(stem: str) -> bool:
    """至少出现 A/B/C/D 里 3 个选项标记,才算选择题。"""
    labels = {m.group(1) or m.group(2) for m in OPTION_RE.finditer(stem)}
    return len(labels & set("ABCD")) >= 3

STEP_CUES = ("由", "设", "则", "得", "故", "所以", "由于", "利用", "代入", "令", "取",
             "即", "从而", "于是", "整理", "求解", "验证", "因为", "将", "考虑",
             "记", "依据", "首先", "其次", "最后", "再", "若", "当")
STEP_START = ("由", "设", "则", "故", "所以", "由于", "利用", "代入", "令", "取", "即",
              "从而", "于是", "整理", "验证", "因为", "将", "考虑", "记", "当", "若",
              "又", "而", "且", "并", "首先", "其次", "最后", "再", "对", "用", "把")
STEP_END_BAD = ("故", "则", "得", "可知", "即", "所以", "由于", "因为", "且", "并",
                "从而", "于是", "有", "为", "是", "则可得")
PITFALL_CUES = ("注意", "易错", "陷阱", "特别地", "这里", "不能", "不可", "切记")
ANSWER_RE = re.compile(r"故\s*选\s*[（(]?\s*([A-D])\s*[)）]?|故选择\s*[（(]?\s*([A-D])\s*[)）]?"
                       r"|所以\s*选\s*[（(]?\s*([A-D])\s*[)）]?|应选\s*[（(]?\s*([A-D])\s*[)）]?")


def norm_text(s: str) -> str:
    return re.sub(r"\s+", "", s)


def detect_ask(stem: str) -> str:
    for pat, label in ASK_RULES:
        if re.search(pat, stem):
            return label
    return "综合求解"


def build_symptom(stem: str, ask: str) -> list[str]:
    out = [f"设问类型：{ask}"]
    for pat, label in STRUCT_RULES:
        if re.search(pat, stem):
            out.append(label)
    if is_choice_question(stem):
        out.append("四选一选择题，选项为结论/命题形式")
    if PARAM_RE.search(stem):
        out.append("含待定参数，结论需按参数范围分段讨论")
    if re.search(r"(设|已知)[\s\S]{0,40}(满足|且)[\s\S]{0,40}(可导|连续)", stem):
        out.append("给定可导/连续的邻域条件，多为定义或中值定理场景")
    # 去重保序
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq[:6]


def pick_topic(stem: str, chapter: str, topic_label: str | None) -> tuple[str, list[str]]:
    """题型标题优先(概率册的“题型N：…”),否则用章内关键词表。"""
    hits: list[str] = []
    table = KEYWORD_TABLE.get(chapter, [])
    for kw in table:
        if kw in stem:
            hits.append(kw)
    if topic_label:
        topic = topic_label
    elif hits:
        topic = hits[0]
    else:
        struct = [lab for pat, lab in STRUCT_TOPIC if re.search(pat, stem)]
        generic = [kw for kw in GENERIC_KEYWORDS if kw in stem]
        topic = struct[0] if struct else (generic[0] if generic else (chapter or "未分类"))
    return topic, hits[:3]


def split_sentences(lines: list[str], max_len: int = 110) -> list[str]:
    """把逐行 OCR 文本先拼回段落,按句末标点切句,超长句再按逗号二次切。

    OCR 常在句子中间硬折行(如 "…故" / "D(X)=100…"),不先拼接会把一句话
    断成两个碎片;而公式多的解析往往整段只有一个句号,不分段又会切出一大坨。
    """
    body = "".join(x.strip() for x in lines)
    out: list[str] = []
    for part in re.split(r"[。；;！？]", body):
        part = part.strip(" ，,、")
        if not part:
            continue
        if len(part) <= max_len:
            out.append(part)
            continue
        buf = ""
        for piece in re.split(r"[，,]", part):
            piece = piece.strip()
            if not piece:
                continue
            if buf and len(buf) + len(piece) > 80:
                out.append(buf)
                buf = piece
            else:
                buf = f"{buf}，{piece}" if buf else piece
        if buf:
            out.append(buf)
    return out


def clip_step(t: str, limit: int = 110) -> str:
    """长句按逗号断,别把结论截成半句。"""
    if len(t) <= limit:
        return t
    cut = t[:limit]
    idx = max(cut.rfind("，"), cut.rfind(","), cut.rfind("；"))
    return (cut[:idx] if idx >= 50 else cut) + "…"


def extract_answer(analysis: list[str]) -> str:
    for s in split_sentences(analysis):
        m = ANSWER_RE.search(s)
        if m:
            letter = next(g for g in m.groups() if g)
            return letter
    return ""


def build_method_chain(analysis: list[str]) -> list[str]:
    """从解析里按"步骤线索句"提炼链条;读不出来就返回 []。"""
    if not analysis:
        return []
    steps: list[str] = []
    for s in split_sentences(analysis):
        t = s.strip(" ，,、")
        t = re.sub(r"^[（(]?\d{1,2}[)）.、]\s*", "", t)      # 去掉小问编号
        t = norm_text(t)
        if len(t) < 12 or len(t) > 160:
            continue
        if re.fullmatch(r"[A-D][)）.、]?", t):
            continue
        if t.endswith(STEP_END_BAD):
            continue
        if sum(1 for ch in t if "\u4e00" <= ch <= "\u9fff") < 2:
            continue                                          # 纯公式不算"步骤"
        started = t.startswith(STEP_START)
        cued = any(c in t for c in ("故", "所以", "即", "则", "得", "由", "从而", "于是", "因此"))
        if not (started or cued):
            continue
        t = clip_step(t)
        if t in steps:
            continue
        steps.append(t)
        if len(steps) >= 8:
            break
    letter = extract_answer(analysis)
    if letter and len(steps) < 8:
        already = any(("故选" in s) or ("故选择" in s) or ("应选" in s) or ("所以选" in s)
                      for s in steps)
        if not already:
            steps.append(f"结论：选（{letter}）")
    return steps[:8]


def build_formulas(analysis: list[str], stem: list[str], limit: int = 3) -> list[str]:
    out: list[str] = []
    for ln in list(analysis) + list(stem):
        s = ln.strip()
        s = re.sub(r"^[，,、。；]+", "", s)
        if not (14 <= len(s) <= 80) or "=" not in s:
            continue
        if any(k in s for k in ("故选", "选项", "注意", "故选择", "综上")):
            continue
        if s[-1] in "=（(=+-*/，," or s[0] in "）)=+-*/，,":
            continue
        tail = s.rsplit("=", 1)[-1].strip()
        if len(tail) < 2:
            continue
        cjk = sum(1 for c in s if "\u4e00" <= c <= "\u9fff")
        if cjk and cjk / len(s) > 0.45:
            continue
        out.append(re.sub(r"\s+", " ", s))
        if len(out) >= limit:
            break
    return out


def build_pitfalls(analysis: list[str], limit: int = 2) -> list[str]:
    out: list[str] = []
    for s in split_sentences(analysis):
        if not any(c in s for c in PITFALL_CUES):
            continue
        s2 = re.sub(r"\s+", "", s)
        if len(s2) < 8:
            continue
        out.append(s2[:100])
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- 组卡
MAX_RAW = 1600


def make_card(cur: dict, scode: str, subject: str) -> tuple[dict, bool]:
    stem_lines = [ln for ln in cur["stem"] if ln.strip()]
    ana_lines = [ln for ln in cur["analysis"] if ln.strip()]
    stem_txt = "\n".join(stem_lines).strip()
    ana_txt = "\n".join(ana_lines).strip()

    raw = "【题面】\n" + stem_txt
    if ana_txt:
        raw += "\n【解析】\n" + ana_txt
    truncated = False
    if len(raw) > MAX_RAW and len(stem_txt) < MAX_RAW - 60:
        raw = raw[:MAX_RAW].rstrip() + "\n…（原文后段省略）"
        truncated = True

    ask = detect_ask(stem_txt)
    symptom = build_symptom(stem_txt, ask)
    method = build_method_chain(ana_lines)
    topic, kw_hits = pick_topic(stem_txt, cur["chapter"], cur["topic_label"])
    chapter = cur["chapter"] or (cur["topic_label"] or "未分类")

    title = f"{chapter}·例{cur['no']}：{topic}｜{ask}"
    tags = [chapter]
    if cur["topic_label"]:
        tags.append(cur["topic_label"])
    tags += [k for k in kw_hits if k not in tags]
    if "选择题" in " ".join(symptom):
        tags.append("选择题")
    if ask == "证明/求证":
        tags.append("证明题")

    # 字段来源:题面/解析是原文照录 -> explicit;由规则归纳出的结构化字段单独标注
    inferred_fields: list[str] = []
    if symptom:
        inferred_fields.append("symptom")
    if not cur["topic_label"]:
        inferred_fields.append("topic")
    if method and not ana_lines:
        inferred_fields.append("method_chain")

    card = {
        "id": "",                       # 去重后统一编号
        "kind": "example",
        "subject": subject,
        "chapter": chapter,
        "topic": topic,
        "title": title,
        "symptom": symptom,
        "method_chain": method,
        "formula": build_formulas(ana_lines, stem_lines),
        "pitfall": build_pitfalls(ana_lines),
        "variants": [],
        "source": {
            "file": cur["file"],
            "page": cur["page"],
            "page_end": cur["page_end"],
            "book": "dx",
            "locator": f"{chapter}/例{cur['no']}",
        },
        "tags": tags,
        # 题面 + 解析均为原文 OCR 照录,故整卡 explicit;归纳字段见 inferred_fields
        "confidence": "explicit",
        "inferred_fields": inferred_fields,
        "raw": raw,
    }
    return card, truncated


# ---------------------------------------------------------------- method / pitfall 卡
CN_NUM = "一二三四五六七八九十"
SUBHEAD_CN = re.compile(rf"^[（(]([{CN_NUM}]{{1,2}})[)）]\s*(\S.*)$")
SUBHEAD_NUM = re.compile(r"^[（(](\d{1,2})[)）]\s*(\S.*)$")
SUBHEAD_DOT = re.compile(r"^(\d{1,2})\s*[.、]\s*(\S.*)$")
MATH_SYMBOLS = "=∼~⟺⇒≥≤"
NOTE_KEYS = ("NOTE", "注", "小结", "总结")
# 易错/反例/边界提示 —— 这类段落单独立 pitfall 卡
PITFALL_MARK = ("注意", "易错", "陷阱", "混淆", "不一定", "得不到", "不能", "不可",
                "切记", "不要", "错在", "区别")
CONT_HEAD = ("=", "＝", "+", "−", "-", ",", "，", ")", "）", "≥", "≤")


def cjk_count(s: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", s))


def merge_fragments(lines: list[str]) -> list[str]:
    """OCR 把公式拆成一堆 1~3 字碎片(如 "∞" "n=0" "i=1"),先并回上一行。

    但上一行是小标签("Note："/"定义：")时不并,否则标签会被吃掉、段落切不开。
    """
    out: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        prev_is_label = bool(out) and out[-1].endswith(("：", ":"))
        if out and not prev_is_label and (
                len(s) <= 3 or re.fullmatch(r"[=+\-−×*/(),，。；:：·|]+", s)):
            out[-1] = out[-1] + " " + s
        else:
            out.append(s)
    return out


def as_subhead(s: str) -> tuple[str, str] | None:
    """返回 (级别, 名称)。part=(一)这类部分,item=(1)/1. 这类细条目。

    含数学符号或太长的不算标题。
    """
    if len(s) > 24 or any(ch in s for ch in MATH_SYMBOLS):
        return None
    if s.endswith(("，", ",", "；", ";", "。", "：")):
        return None
    m = SUBHEAD_CN.match(s)
    if m and len(m.group(2)) <= 16:
        return ("part", m.group(2).strip())
    m = SUBHEAD_NUM.match(s)
    if m and len(m.group(2)) <= 14:
        return ("item", m.group(2).strip())
    m = SUBHEAD_DOT.match(s)
    if m and len(m.group(2)) <= 14 and cjk_count(m.group(2)) >= 2:
        return ("item", m.group(2).strip())
    return None


def as_label(s: str) -> str | None:
    """"Note:"、"定义："、"独立性的重要结论：" 这类小标签。"""
    if len(s) > 18 or not s.endswith(("：", ":")):
        return None
    core = s.rstrip("：:").strip()
    if any(ch in core for ch in MATH_SYMBOLS):
        return None
    if core.upper().startswith("NOTE") or core in ("注", "小结", "总结"):
        return core
    if 2 <= cjk_count(core) <= 12 and len(core) <= 16:
        return core
    return None


def split_segments(merged: list[str]) -> list[dict]:
    """把一个铺垫段按 小节标题 / colon 标签 切成若干内容段,并记住父小节。"""
    segs: list[dict] = []
    cur: dict | None = None
    parent: str | None = None      # (一) 级
    item: str | None = None        # (1) / 1. 级
    for ln in merged:
        s = ln.strip()
        if not s:
            continue
        head = as_subhead(s)
        if head:
            level, name = head
            if level == "part":
                parent, item = name, None
                cur = {"label": name, "raw_label": s, "parent": None, "part": name,
                       "level": "part", "lines": []}
            else:
                item = name
                cur = {"label": name, "raw_label": s, "parent": item, "part": parent,
                       "level": "item", "lines": []}
            segs.append(cur)
            continue
        lab = as_label(s)
        if lab:
            level = "note" if (lab.upper().startswith("NOTE") or lab in ("注", "小结", "总结")) else "label"
            cur = {"label": lab, "raw_label": s, "parent": item or parent,
                   "part": parent, "level": level, "lines": []}
            segs.append(cur)
            continue
        if cur is None:
            cur = {"label": None, "raw_label": "", "parent": item or parent,
                   "part": parent, "level": "topic", "lines": []}
            segs.append(cur)
        cur["lines"].append(s)
    return segs


def merge_continuations(lines: list[str]) -> list[str]:
    """公式续行(以 = , ) 开头)并回上一行,避免一条公式被切成 8 步。"""
    out: list[str] = []
    for s in lines:
        t = s.strip()
        if not t:
            continue
        if out and (t[0] in CONT_HEAD or re.match(r"^[=+−]", t)):
            out[-1] = out[-1] + " " + t
        else:
            out.append(t)
    return out


def clip40(t: str) -> str:
    """每步 ≤ 40 字;要截就截在逗号处,不留半句。"""
    if len(t) <= 40:
        return t
    cut = t[:40]
    idx = max(cut.rfind("，"), cut.rfind(","), cut.rfind("；"), cut.rfind("、"))
    return (cut[:idx] if idx >= 16 else cut) + "…"


def segment_chain(lines: list[str]) -> list[str]:
    """公式为主的段落不给链(公式已经进 formula 字段),只从读得懂的句子提步骤。"""
    merged = merge_continuations(lines)
    cand: list[str] = []
    for s in merged:
        t = re.sub(r"\s+", "", s)
        t = re.sub(r"^[（(]?\d{1,2}[)）.、]", "", t).strip("，,。；;、")
        if len(t) < 6 or cjk_count(t) < 2:
            continue
        cand.append(clip40(t))
    key = [c for c in cand if any(k in c for k in
                                  ("若", "则", "⟺", "用", "先", "再", "取", "判", "求", "当",
                                   "即", "得", "⇒", "设", "注意", "当且仅当"))]
    # 段落不长时按原文顺序全给(顺序本身就是步骤);太长才优先挑线索句
    ordered = cand if len(cand) <= 8 else (key or cand)
    steps: list[str] = []
    for s in ordered:
        if s not in steps:
            steps.append(s)
        if len(steps) >= 8:
            break
    return steps


def classify_segment(lines: list[str], level: str, label: str | None) -> str:
    text = "".join(lines)
    lab = (label or "").upper()
    if level == "note" or lab.startswith("NOTE"):
        return "pitfall" if any(m in text for m in PITFALL_MARK) else "method"
    if any(m in text for m in ("易错", "陷阱", "切记", "容易混淆")) and len(text) < 200:
        return "pitfall"
    return "method"


def segment_formulas(lines: list[str], limit: int = 5) -> list[str]:
    out: list[str] = []
    for s in merge_continuations(lines):
        t = re.sub(r"\s+", " ", s).strip()
        if not (8 <= len(t) <= 90):
            continue
        if not (("=" in t) or ("⟺" in t) or ("∼" in t) or ("~" in t)):
            continue
        if t in out:
            continue
        out.append(t)
        if len(out) >= limit:
            break
    return out


def segment_pitfalls(lines: list[str], limit: int = 3) -> list[str]:
    out: list[str] = []
    for s in merge_continuations(lines):
        if not any(m in s for m in PITFALL_MARK):
            continue
        t = re.sub(r"\s+", "", s)
        if len(t) < 10:
            continue
        out.append(t[:110])
        if len(out) >= limit:
            break
    return out


def clip_title(s: str, limit: int = 44) -> str:
    s = s.strip().rstrip("：:")
    if len(s) <= limit:
        return s.rstrip("，,、")
    cut = s[:limit]
    idx = max(cut.rfind("，"), cut.rfind(","), cut.rfind("；"), cut.rfind("、"))
    return (cut[:idx] if idx >= 14 else cut).rstrip("，,、") + "…"


def pick_gist(lines: list[str], label: str | None) -> str:
    """标题里的一句话:优先读得懂的中文句子,其次公式行。"""
    def strip_num(s: str) -> str:
        s = re.sub(r"^[（(]?\d{1,2}[)）.、]\s*", "", s.strip())
        return s

    prose = [strip_num(s) for s in lines if cjk_count(s) >= 6]
    if prose:
        return clip_title(prose[0])
    semi = [strip_num(s) for s in lines if cjk_count(s) >= 2]
    if semi:
        return clip_title(semi[0])
    if lines:
        return clip_title(strip_num(lines[0]))
    return ""


def make_method_card(seg: dict, pre: dict, subject: str,
                     title_used: Counter, suffix_seq: Counter) -> tuple[dict | None, str]:
    """一个铺垫小节 -> 一张 method/pitfall 卡。返回 (card, 丢弃原因)。"""
    topic = pre.get("topic_label") or pre.get("chapter") or "未分类"
    chapter = pre.get("chapter") or topic
    lines = [x for x in seg["lines"] if x.strip()]
    body = "".join(lines)
    # 只有标题没有内容(纯过渡)才丢;公式型小节(0-1分布/指数分布这类)要留下
    has_math = ("=" in body) or ("∼" in body) or ("~" in body) or ("⟺" in body)
    if len(body) < 20 or (cjk_count(body) < 2 and not has_math):
        return None, "太短/纯过渡"

    level = seg["level"]
    label = seg["label"]
    part = seg.get("part")
    item = seg.get("parent") if level in ("label", "note", "topic") else None

    kind = classify_segment(lines, level, label)
    gist = pick_gist(lines, label)

    parts = [topic]
    part_redundant = False
    if part:
        pt = re.sub(r"[的与和及]", "", part)
        tp = re.sub(r"[的与和及]", "", topic)
        part_redundant = pt in tp or tp in pt
    if part and part != topic and level != "part" and not part_redundant:
        parts.append(part)
    if item and item not in parts and item != part:
        parts.append(item)
    if label and label not in parts:
        parts.append(label)
    head = "·".join(dict.fromkeys(parts))
    while len(head) > 34 and len(parts) > 2:      # 标题别太长:先丢父级,再丢标签
        parts.pop(1)
        head = "·".join(dict.fromkeys(parts))
    title = f"{head}｜{gist}" if gist else head
    if title_used[title]:
        suffix_seq[head] += 1
        title = f"{title}（{suffix_seq[head]}）"
    title_used[title] += 1

    chain = segment_chain(lines) if kind == "method" else []
    formula = segment_formulas(lines)
    pitfall = segment_pitfalls(lines)

    symptom = [f"题型：{topic}"]
    if part and part != topic:
        symptom.append(f"部分：{part}")
    if item and item != part:
        symptom.append(f"小节：{item}")
    if label and label not in (part, item):
        symptom.append(f"标签：{label}")
    if "⟺" in body:
        symptom.append("判别条件型：逐条核对充要条件")

    raw_lines = ([seg["raw_label"]] if seg["raw_label"] else []) + lines
    raw = "【题型铺垫】\n" + "\n".join(raw_lines)
    truncated = False
    if len(raw) > MAX_RAW:
        raw = raw[:MAX_RAW].rstrip() + "\n…（原文后段省略）"
        truncated = True

    inferred = ["title", "symptom"]
    if chain:
        inferred.append("method_chain")

    card = {
        "kind": kind,
        "subject": subject,
        "chapter": chapter,
        "topic": item or label or part or topic,
        "title": title,
        "symptom": symptom,
        "method_chain": chain,
        "formula": formula,
        "pitfall": pitfall,
        "variants": [],
        "source": {
            "file": pre.get("file", ""),
            "page": pre.get("page"),
            "page_end": pre.get("page_end"),
            "book": "dx",
            "locator": f"{chapter}/题型铺垫/{item or label or part or topic}",
        },
        "tags": [x for x in dict.fromkeys([chapter, topic, part, item, label]) if x],
        "confidence": "explicit",
        "inferred_fields": inferred,
        "raw": raw,
    }
    return card, ("truncated" if truncated else "")


def build_method_cards(preambles: list[dict], subject: str) -> tuple[list[dict], dict]:
    cards: list[dict] = []
    stat = {"铺垫段": len(preambles), "method": 0, "pitfall": 0, "丢弃": 0, "截断": 0}
    title_used: Counter = Counter()
    suffix_seq: Counter = Counter()
    for pre in preambles:
        merged = merge_fragments(pre["lines"])
        for seg in split_segments(merged):
            card, why = make_method_card(seg, pre, subject, title_used, suffix_seq)
            if card is None:
                stat["丢弃"] += 1
                continue
            if why == "truncated":
                stat["截断"] += 1
            stat[card["kind"]] += 1
            cards.append(card)
    return cards, stat


def dedup(cards: list[dict]) -> tuple[list[dict], list[dict]]:
    groups: "OrderedDict[str, list[int]]" = OrderedDict()
    for idx, c in enumerate(cards):
        if c["kind"] == "example":
            stem = c["raw"].split("【解析】")[0]
            stem = norm_text(stem.replace("【题面】", ""))
            stem = EXAMPLE_RE.sub("", stem)
            key = "ex|" + stem[:100]
        else:
            key = c["kind"] + "|" + norm_text(c["raw"])[:120]
        groups.setdefault(key, []).append(idx)

    keep: list[dict] = []
    dropped: list[dict] = []
    for key, idxs in groups.items():
        if len(idxs) == 1:
            keep.append(cards[idxs[0]])
            continue
        idxs_sorted = sorted(idxs, key=lambda i: (-len(cards[i]["raw"]), i))
        keep.append(cards[idxs_sorted[0]])
        for i in idxs_sorted[1:]:
            dropped.append(cards[i])
    keep.sort(key=lambda c: (c["source"]["file"], c["source"]["page"]))
    return keep, dropped


def assign_ids(cards: list[dict], subject_order: dict[str, list[str]]) -> None:
    """example -> DX-<科>-C<章码>-<序号>;method/pitfall/symptom -> DX-<科>-M<章码>-<序号>。"""
    chap_seq: Counter = Counter()
    chap_idx: dict[tuple, int] = {}
    for c in cards:
        subj = c["subject"]
        order = subject_order.get(subj, [])
        ch = c["chapter"]
        if (subj, ch) not in chap_idx:
            chap_idx[(subj, ch)] = (order.index(ch) + 1) if ch in order else len(order) + 1
        ci = chap_idx[(subj, ch)]
        pre = "C" if c["kind"] == "example" else "M"
        chap_seq[(subj, ch, pre)] += 1
        c["id"] = f"DX-{c['scode']}-{pre}{ci:02d}-{chap_seq[(subj, ch, pre)]:03d}"


# ---------------------------------------------------------------- 主流程
def load_pages(pattern: str) -> list[dict]:
    files = glob.glob(os.path.join(PAGES_DIR, pattern))
    if not files:
        raise SystemExit(f"找不到页文件:{pattern}")
    path = sorted(files)[0]
    pages = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    pages.sort(key=lambda p: p["page"])
    return pages


def stitch_audit(all_page_lines: dict[int, list[str]], page_order: list[int]):
    """跨页拼接审计:上一页末行停在开符号(=、∫、lim…)上,下一页却直接开新题
    => 题面尾巴疑似丢在页边界。"""
    fails = []
    for a, b in zip(page_order, page_order[1:]):
        la, lb = all_page_lines.get(a) or [], all_page_lines.get(b) or []
        if not la or not lb:
            continue
        tail = la[-1].strip()
        head = lb[0].strip()
        if not OPEN_TAIL_RE.search(tail):
            continue
        if EXAMPLE_RE.match(head) or head.startswith("【解析】") or is_topic_heading(head):
            fails.append((a, b, tail[-30:], head[:30]))
    return fails


def analyze_source(src: dict) -> dict:
    pages = load_pages(src["pattern"])
    chapter_by_page, hdr2title, order = build_chapter_index(pages)
    known = set(hdr2title.keys()) | set(hdr2title.values())

    card_dicts, stat, preambles = collect_cards(pages, chapter_by_page, known)
    repairs = repair_truncated_stems(card_dicts)

    cards = []
    truncated = 0
    for cur in card_dicts:
        card, tr = make_card(cur, src["scode"], src["subject"])
        card["scode"] = src["scode"]
        truncated += int(tr)
        cards.append(card)

    mcards, mstat = build_method_cards(preambles, src["subject"])
    for c in mcards:
        c["scode"] = src["scode"]

    # 跨页审计用的行流(含页眉页脚已剔除)
    page_lines = {}
    for p in pages:
        page_lines[p["page"]] = clean_lines(p, title_block(p))
    order_pages = [p["page"] for p in pages if page_lines[p["page"]]]
    fails = stitch_audit(page_lines, order_pages)

    return {
        "src": src,
        "file": pages[0].get("file", ""),
        "pages": len(pages),
        "empty_pages": sum(1 for p in pages if not (p.get("text") or "").strip()),
        "cards": cards,
        "method_cards": mcards,
        "mstat": mstat,
        "chapters": order,
        "chapter_by_page": chapter_by_page,
        "page_norm": {p["page"]: norm_text(p.get("text") or "") for p in pages},
        "stat": stat,
        "repairs": repairs,
        "truncated_raw": truncated,
        "stitch_fails": fails,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="DX(27大雪深埋做题本)知识卡抽取")
    ap.add_argument("--no-write", action="store_true", help="只统计,不写 DX.jsonl")
    ap.add_argument("--sample", type=int, default=5, help="抽样自检张数")
    ap.add_argument("--full", action="store_true", help="抽样卡片打印 raw 全文")
    ap.add_argument("--seed", type=int, default=27)
    args = ap.parse_args()

    results = [analyze_source(src) for src in SOURCES]

    all_cards: list[dict] = []
    for r in results:
        all_cards.extend(r["cards"])
        all_cards.extend(r["method_cards"])

    kept, dropped = dedup(all_cards)

    subject_order: dict[str, list[str]] = {}
    for src in SOURCES:
        r = next(x for x in results if x["src"]["key"] == src["key"])
        subject_order.setdefault(src["subject"], [])
        for ch in r["chapters"]:
            if ch not in subject_order[src["subject"]]:
                subject_order[src["subject"]].append(ch)

    assign_ids(kept, subject_order)
    for c in kept:
        c.pop("scode", None)

    # ---------------- 统计表
    def stem_of(c: dict) -> str:
        return c["raw"].split("【解析】")[0].replace("【题面】", "").strip()

    def ex_of(cards):
        return [c for c in cards if c["kind"] == "example"]

    print("=" * 78)
    print("DX 抽取统计(27 大雪深埋做题本)")
    print("=" * 78)
    print(f"{'科目':<6}{'文件':<30}{'例题':>4}{'方法卡':>5}{'平均题面':>8}{'链非空':>6}{'跨页':>4}")
    print("-" * 78)
    total = 0
    for src in SOURCES:
        r = next(x for x in results if x["src"]["key"] == src["key"])
        sub = [c for c in kept if c["source"]["file"] == r["file"]]
        ex = ex_of(sub)
        mm = [c for c in sub if c["kind"] != "example"]
        n = len(ex)
        total += len(sub)
        avg = sum(len(stem_of(c)) for c in ex) / n if n else 0
        chain = sum(1 for c in ex if c["method_chain"])
        span = sum(1 for c in ex if c["source"]["page_end"] > c["source"]["page"])
        tag = "3.3/3.4 概率合并" if src["subject"] == "概率" else ""
        print(f"{src['subject']:<6}{src['key'] + ' ' + tag:<30}{n:>4}{len(mm):>5}"
              f"{avg:>8.0f}{chain:>6}{span:>4}")
    print("-" * 78)
    kinds = Counter(c["kind"] for c in kept)
    print(f"入库卡片合计 {total}({dict(kinds)});原始切分 {len(all_cards)};去重丢弃 {len(dropped)}")
    print()

    # method/pitfall 卡的来源
    print("题型铺垫 -> 方法卡")
    for r in results:
        m = r["mstat"]
        if not m["铺垫段"]:
            continue
        print(f"  {r['src']['key']}: 铺垫段 {m['铺垫段']} 个 -> method {m['method']} 张"
              f" / pitfall {m['pitfall']} 张 / 丢弃 {m['丢弃']} 段(纯过渡或只有标题)")
    print()

    # 分科汇总
    print("分科明细(例题)")
    print(f"{'科目':<6}{'例题':>5}{'方法卡':>6}{'平均题面长度':>12}{'链非空':>7}{'链非空率':>9}{'跨页卡':>7}")
    print("-" * 64)
    for subj in ("高数", "线代", "概率"):
        sub = [c for c in kept if c["subject"] == subj]
        ex = ex_of(sub)
        n = len(ex)
        avg = sum(len(stem_of(c)) for c in ex) / n if n else 0
        chain = sum(1 for c in ex if c["method_chain"])
        span = sum(1 for c in ex if c["source"]["page_end"] > c["source"]["page"])
        rate = f"{chain / n * 100:.1f}%" if n else "-"
        print(f"{subj:<6}{n:>5}{len(sub) - n:>6}{avg:>12.0f}{chain:>7}{rate:>9}{span:>7}")
    print()

    # 章节分布
    print("章节分布")
    for subj in ("高数", "线代", "概率"):
        cnt = Counter(c["chapter"] for c in kept if c["subject"] == subj)
        for ch, k in cnt.items():
            print(f"  {subj} · {ch:<22} {k:>4}")
    print()

    # 题号连续性(章内 例号 应为 1..N)——缺号说明源页可能漏抽
    print("题号连续性检查(章内例号应为 1..N 连续)")
    miss_total = dup_total = 0
    for subj in ("高数", "线代", "概率"):
        for ch in subject_order.get(subj, []):
            nums = []
            for c in kept:
                if c["subject"] != subj or c["chapter"] != ch:
                    continue
                m = re.search(r"例(\d+)$", c["source"]["locator"])
                if m:
                    nums.append(int(m.group(1)))
            if not nums:
                continue
            nums_sorted = sorted(nums)
            expect = list(range(1, max(nums) + 1))
            missing = sorted(set(expect) - set(nums))
            dup = sorted({n for n in nums if nums.count(n) > 1})
            miss_total += len(missing)
            dup_total += len(dup)
            if missing or dup:
                print(f"  {subj}·{ch}: 有 {len(nums)} 例, 缺号 {missing[:10]}"
                      f"{' 重复号 ' + str(dup[:6]) if dup else ''}")
    if not miss_total and not dup_total:
        print("  全部章节题号连续,无缺号/重号")
    else:
        print(f"  合计:缺号 {miss_total} 个,重号 {dup_total} 个")
    print()

    # 跨页拼接 / 修复
    st_total = sum(sum(1 for c in r["cards"] if c["source"]["page_end"] > c["source"]["page"])
                   for r in results)
    fail_total = sum(len(r["stitch_fails"]) for r in results)
    rep_total = sum(len(r["repairs"]) for r in results)
    print("跨页拼接")
    print(f"  成功(卡片内容确实跨页拼起来了): {st_total} 张")
    print(f"  失败(页边界处上一页停在 =、∫、lim 等开符号,下一页却直接开新题): {fail_total} 处")
    print(f"  公式碎片回补(题号块公式被排到上一题尾部,已搬回): {rep_total} 处")
    print("  逐文件:")
    for r in results:
        k = r["src"]["key"]
        span = sum(1 for c in r["cards"] if c["source"]["page_end"] > c["source"]["page"])
        print(f"    {k}: 跨页卡 {span:>3} 张 / 丢尾 {len(r['stitch_fails']):>2} 处"
              f" / 回补 {len(r['repairs']):>2} 处 / 非例块丢弃 {r['stat']['非例块丢弃']:>3}")
    for r in results:
        for f in r["stitch_fails"][:3]:
            print(f"    [丢尾?] {r['src']['key']} p{f[0]}->p{f[1]} 尾:{f[2]!r} 下页:{f[3]!r}")
    for r in results:
        for rep in r["repairs"][:3]:
            print(f"    [回补] {r['src']['key']} 例{rep[0]} -> 例{rep[1]}({rep[2]}): {rep[3]}")
    print()

    residual = [c for c in kept if OPEN_TAIL_RE.search(stem_of(c))]
    trunc_total = sum(r["truncated_raw"] for r in results)

    # 页码回验:题面开头 20 字必须能在 source.page..page_end 的原文里找到
    page_norm = {r["file"]: r["page_norm"] for r in results}
    ok_pg = bad_pg = 0
    bad_samples = []
    for c in kept:
        f = c["source"]["file"]
        pages_norm = page_norm.get(f, {})
        stem_norm = norm_text(stem_of(c).replace("【题型铺垫】", ""))
        stem_norm = EXAMPLE_RE.sub("", stem_norm)
        probe = stem_norm[:20]
        if not probe:
            continue
        joined = "".join(pages_norm.get(pg, "") for pg in
                         range(c["source"]["page"], c["source"]["page_end"] + 1))
        if probe and probe in joined:
            ok_pg += 1
        else:
            bad_pg += 1
            if len(bad_samples) < 5:
                bad_samples.append((c["id"], c["source"]["page"], probe))
    tot_pg = ok_pg + bad_pg
    print(f"页码回验(题面开头 20 字能在 source.page 起的原文里找到): "
          f"{ok_pg}/{tot_pg} = {ok_pg / max(1, tot_pg):.1%}")
    for x in bad_samples:
        print(f"  [对不上] {x[0]} p{x[1]} probe={x[2]!r}")
    print()
    print(f"题面尾部未收尾(以 =、∫、lim、逗号结尾,疑似 OCR 截断): {len(residual)} 张")
    for c in residual[:5]:
        print(f"  {c['id']} p{c['source']['page']}: …{stem_of(c)[-40:]!r}")
    print(f"raw 超长截断: {trunc_total} 张(上限 {MAX_RAW} 字符,题面永不截断)")
    conf = Counter(c["confidence"] for c in kept)
    inf_ratio = conf.get("inferred", 0) / max(1, len(kept))
    print(f"confidence 分布: {dict(conf)}(inferred 占比 {inf_ratio:.1%})")
    inf_fields = Counter()
    for c in kept:
        for f in c.get("inferred_fields", []):
            inf_fields[f] += 1
    print(f"inferred_fields 分布: {dict(inf_fields)}")
    print(f"kind 分布: {dict(Counter(c['kind'] for c in kept))}")
    steps = [len(c["method_chain"]) for c in kept if c["method_chain"]]
    if steps:
        print(f"method_chain 步数: 非空 {len(steps)} 张,平均 {sum(steps)/len(steps):.1f} 步,"
              f"最多 {max(steps)} 步/最少 {min(steps)} 步")
    print()

    # ---------------- 抽样自检
    random.seed(args.seed)
    sample = random.sample(kept, min(args.sample, len(kept)))
    print("=" * 78)
    print(f"抽样自检({len(sample)} 张,seed={args.seed})")
    print("=" * 78)
    for c in sample:
        src = c["source"]
        stem = stem_of(c)
        has_opt = bool(OPTION_RE.search(stem))
        print(f"[{c['id']}] {c['title']}")
        print(f"  file={os.path.basename(src['file'])} p{src['page']}"
              f"→p{src['page_end']} | {src['locator']}")
        print(f"  题面 {len(stem)} 字 / 含选项 {has_opt} / 链 {len(c['method_chain'])} 步"
              f" / conf={c['confidence']} / inferred_fields={c.get('inferred_fields')}")
        if args.full:
            print("  raw 全文:")
            for ln in c["raw"].split("\n"):
                print("    | " + ln)
        else:
            print(f"  raw: {c['raw'][:180].replace(chr(10), ' ⏎ ')}")
            print(f"  tail: …{c['raw'][-90:].replace(chr(10), ' ⏎ ')}")
        print()

    if args.no_write:
        print("--no-write:未落盘")
        return

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as fh:
        for c in kept:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"-> {OUT_PATH}  ({len(kept)} 张卡)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
