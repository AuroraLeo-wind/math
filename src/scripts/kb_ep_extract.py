# -*- coding: utf-8 -*-
"""kb_ep_extract.py — epsilon-delta《题型方法梳理班》资料 → 结构化知识卡(EP.jsonl)

输入: D:\\math\\build\\pages\\*.jsonl (每行一页, 含 text / blocks(带 bbox))
输出: D:\\math\\kb\\cards\\EP.jsonl  (严格遵守 docs/02-schema.md)

两种抽取模式:
  manuscript  手稿(讲义页 + 手写板书页混排) —— 高数篇/线代篇
              章标题靠词表命中(板书合集里章标题是单独一行)
  board       纯板书 PPT —— 30+ 个【板书】/【概念重难点】文件
              章由文件名映射, 小节 = "题型一：xxx" / "一、xxx"

分块规则:
  1. 章 = 章标题行;  小节 = "一、xxx" / "2.1 xxx" / "3.5.2 xxx" / "题型N：xxx"
  2. 【例N】 + 印刷解析 + 该例所在页的手写板书 → kind=example (raw 保留完整题面含选项)
  3. 手写板书里的 "总结/口决/口诀/结论/规律" 段 → kind=method | symptom | pitfall (最高价值)
  4. 印刷体 "求法总结/方法总结/框架/三板斧/题型N/注：" 段 → kind=method

手写区识别: 页面最后一个页脚/页码 block 之后的 block 全部判为手写 OCR
           (在 561 页上验证: 页脚之后不存在印刷体正文)。无页脚页用印刷体特征判定。

可重复执行:  python scripts/kb_ep_extract.py
自检:      python scripts/kb_ep_extract.py --verify   (额外做 source.page 回溯校验)
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import Counter, OrderedDict, defaultdict

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES_DIR = os.path.join(ROOT, 'build', 'pages')
OUT_PATH = os.path.join(ROOT, 'kb', 'cards', 'EP.jsonl')

# ---------------------------------------------------------------- 来源
MANUSCRIPTS = [
    {'slug': '板书合集_27考研epsilon-delta题型方法梳理班手稿(高数篇)数学一__eecdc6.jsonl',
     'sid': 'GS', 'subject': '高数', 'default_chapter': '前置知识', 'tag': '手稿·高数篇'},
    {'slug': '板书合集_27考研epsilon-delta题型方法梳理班手稿(线代篇)数学一二三__144e26.jsonl',
     'sid': 'XD', 'subject': '线代', 'default_chapter': '绪论', 'tag': '手稿·线代篇'},
    {'slug': '(3_3)--题型方法梳理班讲义(概率篇)__cc3304.jsonl',
     'sid': 'GL', 'subject': '概率', 'default_chapter': '绪论', 'tag': '讲义·概率篇'},
]

# 补充板书(同一课程体系, 印刷体为主, 题型标题清晰)
BOARDS = [
    ('(4_1)--_板书_函数极限强化课__19943b.jsonl', 'GS', '高数', '函数极限与连续', 'FXLIM'),
    ('(5_1)--_板书_数列极限强化课__8207fd.jsonl', 'GS', '高数', '数列极限', 'SLLIM'),
    ('(6_1)--_板书_一元函数微分学强化课__5582fa.jsonl', 'GS', '高数', '一元函数微分学', 'YYWS'),
    ('(9_1)--_板书_泰勒公式强化专题__afd8d2.jsonl', 'GS', '高数', '一元函数微分学', 'YYWS'),
    ('(9_2)--_板书_凹凸性专题__0d30bd.jsonl', 'GS', '高数', '一元函数微分学', 'YYWS'),
    ('(7_1)--_板书_方程根与函数零点问题__c89b00.jsonl', 'GS', '高数', '一元函数微分学', 'YYWS'),
    ('(8_1)--_板书_中值定理强化板书__f3b172.jsonl', 'GS', '高数', '中值定理', 'ZZDZ'),
    ('(8_3_1)--_板书_例14_柯西中值定理__298474.jsonl', 'GS', '高数', '中值定理', 'ZZDZ'),
    ('(10_1)--_板书_不定积分与定积分__a9919e.jsonl', 'GS', '高数', '一元函数积分学', 'YYJF'),
    ('(11_1)--_板书_积分不等式专题__3fd058.jsonl', 'GS', '高数', '一元函数积分学', 'YYJF'),
    ('(15_1)--_板书_保号性__840fc0.jsonl', 'GS', '高数', '函数极限与连续', 'FXLIM'),
    ('(16_1)--_板书_微积分应用__de34a9.jsonl', 'GS', '高数', '一元函数积分学', 'YYJF'),
    ('(12_1)--_板书_多元函数微分学__360a18.jsonl', 'GS', '高数', '多元函数微分学', 'DYYW'),
    ('(13_1)--_板书_二重积分__1bcf1d.jsonl', 'GS', '高数', '二重积分', 'EZJF'),
    ('(14_1)--_板书_微分方程__e0d5d9.jsonl', 'GS', '高数', '微分方程', 'WFFC'),
    ('(17_1)--_板书_无穷级数__79485e.jsonl', 'GS', '高数', '无穷级数', 'WQJS'),
    ('(18_1)--_板书_曲线曲面积分专题__0243b9.jsonl', 'GS', '高数', '三重积分与曲线曲面积分', 'SZJF'),
    ('(18_2)--_板书_三重积分__8b4c67.jsonl', 'GS', '高数', '三重积分与曲线曲面积分', 'SZJF'),
    ('(18_3)--_板书_微积分应用(仅数一)__247df8.jsonl', 'GS', '高数', '三重积分与曲线曲面积分', 'SZJF'),
    ('(19_1)--_板书_行列式和矩阵__b21aa8.jsonl', 'XD', '线代', '行列式', 'HLS'),
    ('(20_1)--_板书_向量组和方程组__7c4ad3.jsonl', 'XD', '线代', '向量', 'XL'),
    ('(20_2)--_板书_方程组同解和公共解公开课__a1392c.jsonl', 'XD', '线代', '线性方程组', 'XFCS'),
    ('(21_1)--_板书_相似理论__8dd33e.jsonl', 'XD', '线代', '相似理论', 'XSLT'),
    ('(22_1)--_板书_二次型理论__5dd897.jsonl', 'XD', '线代', '二次型', 'ECX'),
    ('(23_1)--_板书_随机事件与概率__c6297d.jsonl', 'GL', '概率', '随机事件与概率', 'SJSJ'),
    ('(24_1)--_板书_一维随机变量(函数)及其分布__b52e71.jsonl', 'GL', '概率', '一维随机变量及其分布', 'YWFB'),
    ('(25_1)--_板书_多维随机变量(函数)及其分布__e22046.jsonl', 'GL', '概率', '多维随机变量及其分布', 'DWFB'),
    ('(26_1)--_板书_随机变量的数字特征__c106fe.jsonl', 'GL', '概率', '随机变量的数字特征', 'SZTZ'),
    ('(27_1)--_板书_大数定律和中心极限定律__3dc455.jsonl', 'GL', '概率', '大数定律和中心极限定理', 'DDSL'),
    ('(27_2)--_板书_统计量及其分布__2c6835.jsonl', 'GL', '概率', '数理统计的基本概念', 'SLTJ'),
    ('(28_1)--_板书_参数估计和假设检验__d01a1a.jsonl', 'GL', '概率', '参数估计与假设检验', 'CSTJ'),
]

# ---------------------------------------------------------------- 章词表
CHAPTERS = {
    '高数': [
        ('前置知识', 'QQZS', ['考研数学必备前置知识', '前置知识']),
        ('函数极限与连续', 'FXLIM', ['函数极限与连续', '函数极限']),
        ('数列极限', 'SLLIM', ['数列极限']),
        ('一元函数微分学', 'YYWS', ['一元函数微分学及其几何应用', '一元函数微分学']),
        ('一元函数积分学', 'YYJF', ['一元函数积分学及其几何应用', '一元函数积分学']),
        ('中值定理', 'ZZDZ', ['中值定理']),
        ('多元函数微分学', 'DYYW', ['多元函数微分学']),
        ('二重积分', 'EZJF', ['二重积分']),
        ('微分方程', 'WFFC', ['微分方程']),
        ('无穷级数', 'WQJS', ['无穷级数']),
        ('三重积分与曲线曲面积分', 'SZJF', ['三重积分与曲线曲面积分', '三重积分']),
    ],
    '线代': [
        ('行列式', 'HLS', ['行列式']),
        ('矩阵', 'JZ', ['矩阵']),
        ('向量', 'XL', ['向量']),
        ('线性方程组', 'XFCS', ['线性方程组']),
        ('相似理论', 'XSLT', ['相似理论']),
        ('二次型', 'ECX', ['二次型']),
    ],
    '概率': [
        ('随机事件与概率', 'SJSJ', ['随机事件与概率']),
        ('一维随机变量及其分布', 'YWFB', ['一维随机变量及其分布']),
        ('多维随机变量及其分布', 'DWFB', ['多维随机变量及其分布']),
        ('随机变量的数字特征', 'SZTZ', ['随机变量的数字特征']),
        ('大数定律和中心极限定理', 'DDSL', ['大数定律和中心极限定理']),
        ('数理统计的基本概念', 'SLTJ', ['数理统计的基本概念']),
        ('参数估计与假设检验', 'CSTJ', ['参数估计与假设检验']),
    ],
}
CH_LOOKUP = {}
for _s, _lst in CHAPTERS.items():
    for _name, _ab, _alias in _lst:
        for _a in _alias:
            CH_LOOKUP[(_s, _a)] = (_name, _ab)

# ---------------------------------------------------------------- 正则
FOOTER_RE = re.compile(
    r'(关注公主号|关注公众号|epsilon-delta\s*数学|扫码了解更多课程|题型方法梳理班》讲义'
    r'|大雪深埋强化课讲义|epsilon\s*-\s*delta\s*大雪深埋|获取更多资料|小红书|抖音|扫码|By epsilon-delta'
    r'|epsilon-delta|公开课)')
PAGENUM_RE = re.compile(r'^[-—–·•]?\s*\d{1,4}\s*[-—–·•]?$')
HEAD1_RE = re.compile(r'^([一二三四五六七八九十]{1,3})\s*、\s*(\S.{0,30})$')
HEAD2_RE = re.compile(r'^(\d{1,2}(?:\.\d{1,2}){1,2})[\s.]+(\S.{0,30})$')
HEAD_TOPIC_RE = re.compile(r'^题型\s*([一二三四五六七八九十\d]{1,3})\s*[:：]\s*(.{1,30})$')
EXAMPLE_RE = re.compile(r'^(?:【\s*例\s*(\d+)\s*】|例\s*(\d+)\s*[:：.、])')
SOLVE_RE = re.compile(r'^(解[:：]|证明[:：]|【解析】|解析[:：]|【分析】|分析[:：]|答[:：]|本题选|故选|法一|法二)')
PRINT_METHOD_RE = re.compile(
    r'^(求法总结|方法总结|思路总结|解题总结|技巧总结|规律总结|框架|三板斧|核心考点|经典例题'
    r'|思路|模板|套路|口诀|口决|方法归纳|小结|注[:：]|Note[:：]|注意[:：]|总结|方法|技巧'
    r'|判别|判定|识别|特征|何时|什么时候|怎么用|怎么判)')
HAND_METHOD_RE = re.compile(
    r'^(总传|总佶|总信|总结|口决|口诀|结论|规律|特征|注意|思路|模板|套路|要点|判定|判别'
    r'|法一|法二|法三|法四|另解|方法|技巧|【总结】|【结论】|【注意】)')
SYMPTOM_RE = re.compile(r'(特征|什么时候|何时|识别|判别|判定|判断.{0,4}(类型|题型)|适用|适合'
                        r'|出现.{0,4}就|看到|类型有)')
PITFALL_RE = re.compile(r'(注意|易错|不能|禁止|小心|陷阱|切记|千万别|避免|失分)')
CJK_RE = re.compile(r'[\u4e00-\u9fff]')
MATH_TOKEN_RE = re.compile(r'(lim|sin|cos|tan|cot|sec|arc|log|ln|exp|max|min|sup|inf|frac|sqrt'
                           r'|dx|dy|dz|dt|rightarrow|left|right|cdot|infty|alpha|beta|theta|xi)')
PRINTED_HINT_RE = re.compile(r'[。，、；：]|【例|\d\.\d')
STRUCT_WORD_RE = re.compile(r'(令|则|故|即|得|先|再|化|取|设|若|因为|所以|转化|构造|代换|换元|求|解|证|用|判)')
RARE_RE = re.compile(r'[｀´ˊˋˇ˘˜˚¼½¾⅓⅔⅛⅜⅝°±×÷≤≥≠∞∅∈∉⊂⊃∪∩∀∃⇒⇔→←↔]')
LATEX_TOKEN_RE = re.compile(r'\b(left|right|frac|begin|end|matrix|cases|overline|cdots|ldots|'
                            r'sim|leq|geq|neq|subset|cup|cap|cdot|alpha|beta|theta|lambda|'
                            r'varphi|sum_|int_|lim_|infty|Rightarrow|rightarrow|bigtriangleup)\b')


# ---------------------------------------------------------------- 文本工具
def clean(s: str) -> str:
    s = s.replace('\xad', '').replace('\u200b', '')
    for a, b in [('\uf00a', "'"), ('\uf00b', "'"), ('\uf0cb', ''), ('\uf0f4', '|'),
                 ('\uf0ee', ''), ('\uf0f6', ''), ('\uf0b1', '\u2211'), ('\uf047', '\u222b'),
                 ('\uf046', '\u222b'), ('\uf0e0', ''), ('\uf0e1', ''), ('\uf0e2', ''),
                 ('\uf028', '('), ('\uf029', ')')]:
        s = s.replace(a, b)
    s = re.sub(r'[ \t\u00a0]+', ' ', s)
    return s.strip()


def cjk_ratio(s: str) -> float:
    ns = re.sub(r'\s', '', s)
    if not ns:
        return 0.0
    return len(CJK_RE.findall(ns)) / len(ns)


def is_readable(s: str) -> bool:
    """手写/OCR 行是否具备可读语义(保守: 宁可丢, 不编造)。"""
    ns = re.sub(r'\s', '', clean(s))
    if len(ns) < 4:
        return False
    if cjk_ratio(ns) < 0.55:
        return False
    if len(CJK_RE.findall(ns)) < 3:
        return False
    if len(re.findall(r'[a-z]{4,}', ns)) >= 2 and not MATH_TOKEN_RE.search(ns):
        return False
    if LATEX_TOKEN_RE.search(ns):
        return False
    if RARE_RE.search(ns) and cjk_ratio(ns) < 0.75:
        return False
    if not STRUCT_WORD_RE.search(ns) and len(ns) < 6:
        return False
    return True


def is_formula(s: str) -> bool:
    t = clean(s)
    if len(t) < 4 or len(t) > 120:
        return False
    if cjk_ratio(t) > 0.45:
        return False
    return bool(re.search(r'[=<>≤≥]', t)) or bool(MATH_TOKEN_RE.search(t))


def dedupe_keep(seq):
    out, seen = [], set()
    for x in seq:
        k = re.sub(r'\s', '', str(x))
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out


def has_balanced(s: str) -> bool:
    return s.count('(') == s.count(')') and s.count('（') == s.count('）')


def short_title(s, limit=48):
    s = re.sub(r'\s+', ' ', s).strip(' :：,，.。;；、')
    return s[:limit]


def head_line(s, limit=30):
    """标题用短句: 取第一个标点前的部分。"""
    s = re.sub(r'\s+', ' ', s).strip(' :：,，.。;；、')
    s = re.split(r'[，,。；;：:？?！!]', s)[0]
    return s[:limit] if s else ''


def tail_clean(t: str) -> str:
    return re.sub(r'^(解[:：]|证明[:：]|【解析】|解析[:：]|【分析】|分析[:：]|答[:：])', '', t).strip()


# ---------------------------------------------------------------- 页面读取
def load_pages(path):
    pages = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line:
                pages.append(json.loads(line))
    return pages


class Line:
    __slots__ = ('text', 'page', 'hand', 'order')

    def __init__(self, text, page, hand, order):
        self.text, self.page, self.hand, self.order = text, page, hand, order

    def __repr__(self):
        return f'<{self.page}{"H" if self.hand else "P"} {self.text[:24]!r}>'


def page_lines(pg):
    """该页行序列: 印刷区在前, 手写区在后(内容流顺序)。"""
    blocks = pg.get('blocks') or []
    texts = [clean(ln) for b in blocks for ln in (b.get('text') or '').split('\n')]
    texts = [t for t in texts if t]
    if not texts:
        return []

    foot_idx = -1
    for i, b in enumerate(blocks):
        t = clean(b.get('text') or '')
        if not t:
            continue
        if FOOTER_RE.search(t) or (PAGENUM_RE.match(t) and len(t) <= 5):
            foot_idx = i

    if foot_idx >= 0:
        hand_from = foot_idx + 1
        all_hand = False
    else:
        printed_hits = sum(1 for t in texts if PRINTED_HINT_RE.search(t))
        all_hand = printed_hits < 2
        hand_from = 0 if all_hand else len(blocks) + 1

    out, order = [], 0
    for i, b in enumerate(blocks):
        for ln in (b.get('text') or '').split('\n'):
            t = clean(ln)
            if not t:
                continue
            if FOOTER_RE.search(t) or (PAGENUM_RE.match(t) and len(t) <= 5):
                continue
            out.append(Line(t, pg['page'], all_hand or (i >= hand_from), order))
            order += 1
    return out


# ---------------------------------------------------------------- 卡片
def tags_of(ctx, lines):
    tags = [ctx['chapter']]
    if ctx.get('tag'):
        tags.append(ctx['tag'])
    tp = ctx.get('topic')
    if tp and tp != ctx['chapter']:
        tags.append('题型·' + short_title(tp, 24))
    joined = ' '.join(lines)
    rules = [('极限', '极限'), ('导数', '导数'), ('积分', '积分'), ('级数', '级数'),
             ('中值', '中值定理'), ('矩阵', '矩阵'), ('秩', '秩'), ('特征值', '特征值'),
             ('二次型', '二次型'), ('概率', '概率'), ('分布', '分布'), ('独立', '独立性'),
             ('等价无穷小', '等价无穷小'), ('泰勒', '泰勒'), ('洛必达', '洛必达'),
             ('单调', '单调性'), ('极值', '极值'), ('不等式', '不等式'), ('行列式', '行列式'),
             ('估值', '估计'), ('切比雪夫', '切比雪夫'), ('期望', '期望'), ('方差', '方差')]
    for kw, tg in rules:
        if kw in joined:
            tags.append(tg)
    return dedupe_keep(tags)[:8]


def build_example(ctx, stem_lines, sol_lines, hand_lines):
    stem = '\n'.join(stem_lines).strip()
    hand_read = [l for l in hand_lines if is_readable(l)]
    sol = [l for l in sol_lines if l.strip()]

    method, symptom, pitfall, formula = [], [], [], []

    for ln in sol:
        t = tail_clean(ln)
        if not t:
            continue
        if is_formula(t):
            formula.append(short_title(t, 100))
            continue
        if SYMPTOM_RE.search(t):
            symptom.append(short_title(t, 90))
        if PITFALL_RE.search(t):
            pitfall.append(short_title(t, 90))
        for part in re.split(r'[;；]', t):
            part = part.strip()
            if frag_ok(part, True):
                method.append(short_title(part, 90))

    for ln in hand_read:
        body = re.sub(r'^(总传|总佶|总信|总结|口决|口诀|结论|规律|特征|注意|思路|方法|技巧)', '', ln).strip(' :：、.')
        if is_formula(ln) and cjk_ratio(ln) < 0.35:
            formula.append(short_title(ln, 100))
        if SYMPTOM_RE.search(ln):
            symptom.append(short_title(ln, 90))
        if PITFALL_RE.search(ln):
            pitfall.append(short_title(ln, 90))
        for part in re.split(r'[;；]', body):
            part = part.strip(' ,，.。')
            if frag_ok(part, False):
                method.append(short_title(part, 90))

    method = dedupe_keep(method)[:8]
    symptom = dedupe_keep(symptom)[:6]
    pitfall = dedupe_keep(pitfall)[:5]
    formula = dedupe_keep(formula)[:6]

    head = head_line(re.sub(r'^【\s*例\s*\d+\s*】\s*', '', stem_lines[0])) if stem_lines else ''
    title = f'{ctx["chapter"]}·{ctx["topic"]} 例{ctx["exno"]}：{head[:40]}'.strip('：')

    parts = ['【题面】\n' + stem[:1100]]
    if sol:
        parts.append('【印刷解析】\n' + '\n'.join(sol)[:400])
    if hand_lines:
        parts.append('【手写板书OCR】\n' + '\n'.join(hand_lines)[:500])
    raw = '\n'.join(parts)[:1600]

    # 置信度: 结构化字段全部来自 raw 原文 → explicit; 没有编造字段时也标 explicit。
    # 题型标签只进 tags(不进 symptom), 避免 index_build 把同章节无解析例题折叠成一张。
    conf = 'explicit'
    return {
        'kind': 'example', 'subject': ctx['subject'], 'chapter': ctx['chapter'],
        'topic': ctx['topic'], 'title': title, 'symptom': symptom,
        'method_chain': method, 'formula': formula, 'pitfall': pitfall, 'variants': [],
        'source': {'file': ctx['file'], 'page': ctx['page'], 'book': 'ep',
                   'locator': f'{ctx["chapter"]}/{ctx["topic"]}/例{ctx["exno"]}'},
        'tags': tags_of(ctx, stem_lines), 'confidence': conf, 'raw': raw,
    }


NUM_ONLY_RE = re.compile(r'^[(（]?[\d一二三四五六七八九十①②③④⑤⑥⑦⑧⑨]{1,3}[)）.、,:：]?$')
GENERIC_MARK_RE = re.compile(r'^(Note[:：]?|注[:：]?|方法|思路|总结|框架|技巧|模板|套路|要点|小结|注意[:：]?)$')
LABEL_ONLY_RE = re.compile(r'(经典例题精讲|核心考点梳理|专题框架|例题精讲|本节思路)')
MATH_TERM_RE = re.compile(
    r'(函数|极限|极值|邻域|导数|微分|单调|积分|连续|可导|等价|泰勒|洛必达|级数|收敛|发散'
    r'|行列式|秩|矩阵|向量|特征值|二次型|方程|概率|期望|方差|分布|独立|事件|样本|估计|检验'
    r'|定理|中值|不等式|对称|换元|代换|构造|判别|收敛|原函数|不定积分|定积分|二重积分|三重积分'
    r'|偏导|全微分|方向导|曲线积分|曲面积分|反常积分|渐进线|渐近线|拐点|凹|凸)')


def frag_ok(frag: str, printed: bool) -> bool:
    """片段是否可进入 method_chain。印刷体宽松, 手写严格(OCR 噪声大)。"""
    f = frag.strip()
    if len(f) < 3:
        return False
    if NUM_ONLY_RE.match(f):
        return False
    if GENERIC_MARK_RE.match(f):
        return False
    if LABEL_ONLY_RE.search(f) and len(f) < 14:
        return False
    n_cjk = len(CJK_RE.findall(f))
    if printed:
        if n_cjk == 0 and not MATH_TERM_RE.search(f) and not re.search(r'[=<>≤≥]', f):
            return False
        return True
    if n_cjk < 3:
        return False
    if not MATH_TERM_RE.search(f):
        if len(f) < 7 or not STRUCT_WORD_RE.search(f):
            return False
    if n_cjk < 4 and not MATH_TERM_RE.search(f):
        return False
    return True


def build_method(kind, ctx, seg_lines, marker, hand, topic_label=None):
    raw_block = '\n'.join(seg_lines)
    readable = [l for l in seg_lines if (is_readable(l) if hand else bool(l.strip()))]

    body, formula, sym, pit = [], [], [], []
    for ln in readable:
        if is_formula(ln) and cjk_ratio(ln) < 0.35:
            formula.append(short_title(ln, 100))
            continue
        if hand:
            t = re.sub(r'^(总传|总佶|总信|总结|口决|口诀|结论|规律|特征|注意|思路|方法|技巧|要点'
                       r'|判定|判别|法一|法二|法三|法四|另解)', '', ln).strip(' :：、.')
        else:
            t = ln.strip()
        if SYMPTOM_RE.search(ln):
            sym.append(short_title(ln, 90))
        if PITFALL_RE.search(ln):
            pit.append(short_title(ln, 90))
        for part in re.split(r'[;；。]', t):
            part = part.strip(' ,，.。')
            if frag_ok(part, not hand):
                body.append(short_title(part, 90))

    body = dedupe_keep(body)[:8]
    formula = dedupe_keep(formula)[:8]
    sym = dedupe_keep(sym)[:6]
    pit = dedupe_keep(pit)[:5]

    head_clean = re.sub(r'^(总传|总佶|总信|总结|口决|口诀|结论|规律|特征|注意|思路|模板|套路'
                        r'|方法|技巧|要点)', '', marker).strip(' :：、.')
    if GENERIC_MARK_RE.match(marker.strip()) and body:
        head_clean = body[0]
    if topic_label:
        label = re.sub(r'^题型\s*[一二三四五六七八九十\d]{1,3}\s*[:：]\s*', '', topic_label)
        title = f'题型·{short_title(label, 30)}：{short_title(head_clean, 30) or short_title(marker, 20)}'
        if not sym:
            sym = [short_title(topic_label, 60)]
    else:
        title = f'{ctx["chapter"]}·{ctx["topic"]}：{short_title(head_clean, 34) or short_title(marker, 24)}'

    symptom, method, pitfall = sym, body, pit
    if kind == 'symptom':
        symptom = sym or body[:6]
        method = [x for x in body if x not in symptom][:8]
    elif kind == 'pitfall':
        symptom, method = sym, body[:8]
        pitfall = pit or body[:3]
    # 纯目录/标题罗列 → 体系图, 不是方法步骤
    if kind == 'method' and not formula and is_heading_list(method):
        kind = 'map'

    # 只要 body/formula 有内容, 就是原文抽出来的 → explicit; 否则只有 marker → inferred
    conf = 'explicit' if (body or formula or (sym and len(sym) > 0)) else 'inferred'
    return {
        'kind': kind, 'subject': ctx['subject'], 'chapter': ctx['chapter'],
        'topic': ctx['topic'], 'title': title, 'symptom': symptom,
        'method_chain': method, 'formula': formula, 'pitfall': pitfall, 'variants': [],
        'source': {'file': ctx['file'], 'page': ctx['page'], 'book': 'ep',
                   'locator': f'{ctx["chapter"]}/{ctx["topic"]}/{short_title(marker, 16)}'},
        'tags': tags_of(ctx, seg_lines), 'confidence': conf, 'raw': raw_block[:900],
    }


# ---------------------------------------------------------------- 抽取引擎
def new_ctx(cfg, fname, chapter, abbr):
    return {'subject': cfg['subject'], 'file': fname, 'chapter': chapter,
            'abbr': abbr, 'topic': chapter, 'page': 0, 'tag': cfg.get('tag', '')}


def set_topic(ctx, text):
    ctx['topic'] = short_title(text, 30) or ctx['chapter']


def collect_example(stream, i, ctx, subj, fname, hand_stop=True):
    """从 stream[i] (例 行) 开始收集题面/解析/手写; 返回 (card, next_i)。"""
    me = EXAMPLE_RE.match(stream[i].text)
    exno = me.group(1) or me.group(2)
    stem, sol, hand = [], [], []
    page_ctx = {'subject': ctx['subject'], 'file': fname, 'chapter': ctx['chapter'],
                'topic': ctx['topic'], 'page': stream[i].page, 'exno': exno,
                'tag': ctx.get('tag', '')}
    j, n = i, len(stream)
    mode, stem_chars, last_page = 'stem', 0, stream[i].page
    while j < n:
        cur = stream[j]
        ct = cur.text
        if j > i:
            if cur.hand:
                if hand_stop and HAND_METHOD_RE.match(ct):
                    break                      # 让主循环把它做成 method 卡
                hand.append(ct)
                last_page = cur.page
                j += 1
                continue
            if cur.page != last_page:
                prev = stem[-1] if stem else ''
                cont_ok = (mode == 'stem' and not re.search(r'[。.；;？?）)]$', prev)
                           and has_balanced(prev))
                if not (cont_ok and not EXAMPLE_RE.match(ct)
                        and not HEAD1_RE.match(ct) and not HEAD2_RE.match(ct)
                        and not HEAD_TOPIC_RE.match(ct)
                        and not CH_LOOKUP.get((subj, ct))
                        and not PRINT_METHOD_RE.match(ct)):
                    break
            if EXAMPLE_RE.match(ct) or CH_LOOKUP.get((subj, ct)):
                break
            if HEAD_TOPIC_RE.match(ct):
                break
            if (HEAD1_RE.match(ct) or HEAD2_RE.match(ct)) and len(ct) <= 40:
                break
            if SOLVE_RE.match(ct) and mode == 'stem':
                mode = 'sol'
                sol.append(ct)
                last_page = cur.page
                j += 1
                continue
            if PRINT_METHOD_RE.match(ct) and mode != 'sol':
                break
        if mode == 'stem':
            stem.append(ct)
            stem_chars += len(ct)
            if stem_chars > 1100:
                mode = 'sol'
        else:
            sol.append(ct)
        last_page = cur.page
        j += 1
    return build_example(page_ctx, stem, sol, hand), j


def collect_hand_method(stream, i, ctx):
    t = stream[i].text
    like = 'symptom' if SYMPTOM_RE.search(t) else ('pitfall' if t.startswith('注意') else 'method')
    seg = [t]
    j, n = i + 1, len(stream)
    while j < n and len(seg) < 14:
        cur = stream[j]
        if cur.page != stream[i].page or not cur.hand:
            break
        if HAND_METHOD_RE.match(cur.text):
            break
        if len(seg) >= 3 and cjk_ratio(cur.text) < 0.3:
            break
        seg.append(cur.text)
        j += 1
    card = build_method(like, {'subject': ctx['subject'], 'file': ctx['file'],
                               'chapter': ctx['chapter'], 'topic': ctx['topic'],
                               'page': stream[i].page, 'tag': ctx.get('tag', '')},
                        seg, t, True)
    return card, j


def collect_print_method(stream, i, ctx):
    t = stream[i].text
    like = 'symptom' if SYMPTOM_RE.search(t) else 'method'
    seg = [t]
    j, n = i + 1, len(stream)
    while j < n and len(seg) < 26:
        cur = stream[j]
        if cur.hand or cur.page != stream[i].page:
            break
        if EXAMPLE_RE.match(cur.text) or CH_LOOKUP.get((ctx['subject'], cur.text)):
            break
        if HEAD_TOPIC_RE.match(cur.text):
            break
        if (HEAD1_RE.match(cur.text) or HEAD2_RE.match(cur.text)) and len(cur.text) <= 40:
            break
        if PRINT_METHOD_RE.match(cur.text) and len(seg) >= 2:
            break
        seg.append(cur.text)
        j += 1
    card = build_method(like, {'subject': ctx['subject'], 'file': ctx['file'],
                               'chapter': ctx['chapter'], 'topic': ctx['topic'],
                               'page': stream[i].page, 'tag': ctx.get('tag', '')},
                        seg, t, False)
    return card, j


def finalize(cards, sid, subject):
    """按页序返回(不编号); 编号统一在 main 里做, 保证跨来源唯一。"""
    out = []
    for _page, _ord, card in sorted(cards, key=lambda x: (x[0], x[1])):
        card['_sid'] = sid
        out.append(card)
    return out


def assign_ids(all_cards):
    """全局编号: EP-<sid>-<章缩写>-<章内序号>。"""
    counters = Counter()
    used = set()
    out = []
    for card in all_cards:
        sid = card.pop('_sid')
        ab = CH_LOOKUP.get((card['subject'], card['chapter']), (card['chapter'], 'GEN'))[1]
        n = counters[(sid, ab)]
        while True:
            n += 1
            cid = f'EP-{sid}-{ab}-{n:03d}'
            if cid not in used:
                break
        counters[(sid, ab)] = n
        used.add(cid)
        out.append(OrderedDict([('id', cid)] + list(card.items())))
    return out


def extract_manuscript(path, cfg):
    pages = load_pages(path)
    fname = pages[0].get('file') or os.path.basename(path)
    subj = cfg['subject']
    stream = []
    for pg in pages:
        stream.extend(page_lines(pg))

    ctx = new_ctx(cfg, fname, cfg['default_chapter'],
                  CH_LOOKUP.get((subj, cfg['default_chapter']), ('', 'GEN'))[1])
    cards, i, n = [], 0, len(stream)
    page_ctx = {}

    def snap(page, force=False):
        if force or page not in page_ctx:
            page_ctx[page] = {'subject': subj, 'file': fname,
                              'chapter': ctx['chapter'], 'topic': ctx['topic']}

    while i < n:
        ln = stream[i]
        t = ln.text
        snap(ln.page)
        key = CH_LOOKUP.get((subj, t)) or CH_LOOKUP.get(
            (subj, re.sub(r'（.*?）|\(.*?\)', '', t).strip()))
        if key:
            ctx['chapter'], ctx['abbr'] = key[0], key[1]
            ctx['topic'] = key[0]
            ctx['page'] = ln.page
            snap(ln.page, True)
            i += 1
            continue
        if (HEAD1_RE.match(t) or HEAD2_RE.match(t) or HEAD_TOPIC_RE.match(t)) and len(t) <= 40:
            set_topic(ctx, t)
            ctx['page'] = ln.page
            snap(ln.page, True)
            i += 1
            continue
        if EXAMPLE_RE.match(t):
            card, i = collect_example(stream, i, ctx, subj, fname)
            cards.append((ln.page, ln.order, card))
            continue
        if ln.hand and HAND_METHOD_RE.match(t):
            card, j = collect_hand_method(stream, i, ctx)
            if card_ok(card):
                cards.append((ln.page, ln.order, card))
            i = j
            continue
        if (not ln.hand) and PRINT_METHOD_RE.match(t) and len(t) <= 40:
            card, j = collect_print_method(stream, i, ctx)
            if card_ok(card):
                cards.append((ln.page, ln.order, card))
            i = j
            continue
        i += 1
    cards.extend(page_theory_cards(stream, page_ctx, cfg.get('tag', '')))
    return finalize(cards, cfg['sid'], subj)


def extract_board(path, cfg, chapter, abbr):
    pages = load_pages(path)
    fname = pages[0].get('file') or os.path.basename(path)
    subj = cfg['subject']
    stream = []
    for pg in pages:
        stream.extend(page_lines(pg))

    ctx = new_ctx(cfg, fname, chapter, abbr)
    cards, i, n = [], 0, len(stream)
    page_ctx = {}

    def snap(page, force=False):
        if force or page not in page_ctx:
            page_ctx[page] = {'subject': subj, 'file': fname,
                              'chapter': chapter, 'topic': ctx['topic']}

    while i < n:
        ln = stream[i]
        t = ln.text
        snap(ln.page)
        mt = HEAD_TOPIC_RE.match(t)
        if mt:
            set_topic(ctx, t)
            ctx['page'] = ln.page
            snap(ln.page, True)
            # 题型标题本身就是方法块起手: 后面到下一个例/题型之前的印刷公式/要点 → method 卡
            seg = [t]
            j = i + 1
            while j < n and len(seg) < 26:
                cur = stream[j]
                if cur.hand or cur.page != ln.page:
                    break
                if EXAMPLE_RE.match(cur.text) or HEAD_TOPIC_RE.match(cur.text):
                    break
                if (HEAD1_RE.match(cur.text) or HEAD2_RE.match(cur.text)) and len(cur.text) <= 40:
                    break
                seg.append(cur.text)
                j += 1
            if len(seg) > 1:
                card = build_method('method',
                                    {'subject': subj, 'file': fname, 'chapter': chapter,
                                     'topic': ctx['topic'], 'page': ln.page, 'tag': cfg.get('tag', '')},
                                    seg, t, False, topic_label=ctx['topic'])
                if card_ok(card):
                    cards.append((ln.page, ln.order, card))
            i = j
            continue
        if (HEAD1_RE.match(t) or HEAD2_RE.match(t)) and len(t) <= 40:
            set_topic(ctx, t)
            ctx['page'] = ln.page
            snap(ln.page, True)
            i += 1
            continue
        if EXAMPLE_RE.match(t):
            card, i = collect_example(stream, i, ctx, subj, fname)
            cards.append((ln.page, ln.order, card))
            continue
        if ln.hand and HAND_METHOD_RE.match(t):
            card, j = collect_hand_method(stream, i, ctx)
            if card_ok(card):
                cards.append((ln.page, ln.order, card))
            i = j
            continue
        if (not ln.hand) and PRINT_METHOD_RE.match(t) and len(t) <= 24:
            card, j = collect_print_method(stream, i, ctx)
            if card_ok(card):
                cards.append((ln.page, ln.order, card))
            i = j
            continue
        i += 1
    cards.extend(page_theory_cards(stream, page_ctx, cfg.get('tag', '')))
    return finalize(cards, cfg['sid'], subj)


# ---------------------------------------------------------------- 去重/统计/自检
ADMIN_RE = re.compile(r'(群聊|打卡|文创|抽奖|回放|课前收集|签名|禁言|踢出群|活动|报名|点赞|关注我)')
PREFACE_RE = re.compile(r'(童哥有话说|各位同学|同学们|我很喜欢|首先我想|这一章我们|鸡汤|加油)')
HEADING_LIKE_RE = re.compile(r'^\s*[（(]?\d*[)）.、]?\s*[\u4e00-\u9fffA-Za-z]{2,14}$')


def is_heading_list(items):
    """body 全是短标题(无句读) → 这是体系目录, 不是方法步骤, 应归 map。"""
    if len(items) < 4:
        return False
    short = [x for x in items if len(x) <= 16 and not re.search(r'(，|。|；|则|得|故|令|可|要|应)', x)]
    return len(short) >= max(4, int(len(items) * 0.75))


def card_ok(card):
    """method/symptom/pitfall 卡的有效性: 必须含数学词、不能是课程管理/广告/前言文字。"""
    if card is None:
        return False
    if card['kind'] in ('method', 'symptom', 'pitfall', 'map'):
        if not (card['method_chain'] or card['formula'] or card['symptom']):
            return False
        txt = card['raw'] + ' '.join(card['method_chain']) + ' '.join(card['formula'])
        if ADMIN_RE.search(card['raw']) or PREFACE_RE.search(card['raw']):
            return False
        if not MATH_TERM_RE.search(txt):
            return False
    return True


def page_theory_cards(stream, page_ctx, tag):
    """补抽: 每页印刷区中"第一个【例N】之前"的理论/方法段落 → method 卡。
    这些页没有 总结/框架 之类显式 marker, 但整段就是方法(如 '4° 对称区间上的定积分…偶倍奇零')。"""
    by_page = OrderedDict()
    for ln in stream:
        by_page.setdefault(ln.page, []).append(ln)

    cards = []
    for page, lns in by_page.items():
        pre = []
        for ln in lns:
            if ln.hand or EXAMPLE_RE.match(ln.text):
                break
            pre.append(ln.text)
        if len(pre) < 3:
            continue
        joined = ' '.join(pre)
        if not re.search(r'(法|思路|条件|性质|公式|判别|技巧|步骤|定理|结论|总结|要点|准则|推广'
                         r'|原则|注意|等价|核心)', joined):
            continue
        if sum(1 for p in pre if len(CJK_RE.findall(p)) >= 4) < 2:
            continue
        c = page_ctx.get(page)
        if not c:
            continue
        card = build_method('method',
                            {'subject': c['subject'], 'file': c['file'], 'chapter': c['chapter'],
                             'topic': c['topic'], 'page': page, 'tag': tag},
                            pre, pre[0], False)
        if card_ok(card):
            card['tags'] = dedupe_keep(card['tags'] + ['整页板书']) [:8]
            cards.append((page, -1, card))
    return cards


def stem_key(card):
    """跨来源去重键: 题面/正文归一化后的前 40 字(去掉例号与空白)。"""
    raw = card['raw']
    if card['kind'] == 'example':
        raw = raw.split('【题面】')[-1].split('【印刷解析】')[0].split('【手写板书OCR】')[0]
    s = re.sub(r'[\s【】]', '', raw)
    s = re.sub(r'^例\d+', '', s)
    return s[:40]


def dedupe_cards(cards):
    """1) 丢 raw 过短的垃圾卡(校验脚本要求 raw>=30)
       2) 跨来源去重: 题面归一化后相同的 example 只留先出现的(手稿/讲义先于补充板书)
       3) 同章正文相同的 method/symptom/pitfall 只留一张(手稿优先)。
    返回 (cards, stats)。"""
    out, seen = [], set()
    stats = Counter()
    for c in cards:
        if len(c.get('raw') or '') < 30:
            stats['drop_short_raw'] += 1
            continue
        body = re.sub(r'[\s【】]', '', c['raw'])
        if c['kind'] == 'example':
            k = ('ex', stem_key(c))
        elif c['kind'] in ('method', 'symptom', 'pitfall'):
            k = ('mt', c['chapter'], body[:60])
        else:
            k = (c['kind'], body[:60])
        if k in seen:
            stats['drop_dup_' + c['kind']] += 1
            continue
        seen.add(k)
        out.append(c)
    return out, stats


def norm_probe(s: str) -> str:
    return re.sub(r'[\s【】]', '', s)


def verify_pages(cards, page_index):
    """回溯校验: 卡片题面片段必须能在 source.page(±1 页)的文本层里找到。"""
    bad = []
    for c in cards:
        fn = c['source']['file']
        pg = c['source']['page']
        pool = ''.join(page_index.get((fn, p), '') for p in (pg - 1, pg, pg + 1))
        if not page_index.get((fn, pg)):
            bad.append((c['id'], f'p{pg} 无文本层'))
            continue
        stem = c['raw'].split('【题面】')[-1].split('【印刷解析】')[0].split('【手写板书OCR】')[0]
        probe = norm_probe(stem)
        if not probe:
            continue
        win = probe[:40]
        ok = any(win[i:i + 16] in pool for i in range(0, max(1, min(len(win), 40) - 16), 4))
        if not ok:
            bad.append((c['id'], f'p{pg} 未命中 "{probe[:20]}"'))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--no-board', action='store_true', help='只用三大主源, 不并入补充板书')
    args = ap.parse_args()

    all_cards = []
    src_stat = []
    for cfg in MANUSCRIPTS:
        path = os.path.join(PAGES_DIR, cfg['slug'])
        if not os.path.exists(path):
            print(f'!! 缺文件 {cfg["slug"]}')
            continue
        cards = extract_manuscript(path, cfg)
        src_stat.append((cfg['slug'], len(cards)))
        print(f'{cfg["sid"]} {cfg["slug"][:46]:<48} → {len(cards):4d} 张')
        all_cards.extend(cards)

    if not args.no_board:
        for slug, sid, subject, chapter, abbr in BOARDS:
            path = os.path.join(PAGES_DIR, slug)
            if not os.path.exists(path):
                print(f'!! 缺板书 {slug}')
                continue
            cfg = {'sid': sid, 'subject': subject, 'tag': '补充板书'}
            cards = extract_board(path, cfg, chapter, abbr)
            src_stat.append((slug, len(cards)))
            print(f'{sid} {slug[:46]:<48} → {len(cards):4d} 张')
            all_cards.extend(cards)

    before = len(all_cards)
    all_cards, dd = dedupe_cards(all_cards)
    all_cards = assign_ids(all_cards)
    print(f'去重: {before} → {len(all_cards)}  ' + ', '.join(f'{k}={v}' for k, v in sorted(dd.items())))
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as fh:
        for c in all_cards:
            fh.write(json.dumps(c, ensure_ascii=False) + '\n')

    print(f'\n写入 {OUT_PATH}  共 {len(all_cards)} 张卡')

    # --- 分布表
    kinds = ['example', 'method', 'symptom', 'pitfall']
    stat = defaultdict(Counter)
    for c in all_cards:
        stat[(c['subject'], c['chapter'])][c['kind']] += 1
    print('\n| 科目 | 章 | 合计 | ' + ' | '.join(kinds) + ' |')
    print('| --- | --- | --- | ' + ' | '.join(['---'] * len(kinds)) + ' |')
    for (subj, ch), cnt in sorted(stat.items(), key=lambda kv: (kv[0][0], -sum(kv[1].values()))):
        print(f'| {subj} | {ch} | {sum(cnt.values())} | ' + ' | '.join(str(cnt[k]) for k in kinds) + ' |')
    tot = Counter(c['kind'] for c in all_cards)
    print('| 全部 | - | %d | ' % len(all_cards) + ' | '.join(str(tot[k]) for k in kinds) + ' |')

    filled = Counter()
    for c in all_cards:
        if c['kind'] in ('method', 'symptom'):
            if c['method_chain']:
                filled['method有链条'] += 1
            if c['symptom']:
                filled['method有特征'] += 1
            if c['formula']:
                filled['method有公式'] += 1
        if c['kind'] == 'example':
            if c['method_chain']:
                filled['example有解析'] += 1
    print('\n填充率: ' + ', '.join(f'{k}={v}' for k, v in sorted(filled.items())))

    # --- 自检
    print('\n===== 自检 A: 随机 5 张卡全文 =====')
    rnd = random.Random(20261101)
    for c in rnd.sample(all_cards, min(5, len(all_cards))):
        print('-' * 72)
        print(json.dumps(c, ensure_ascii=False, indent=1))

    if args.verify:
        print('\n===== 自检 B: source.page 回溯 =====')
        page_index = {}
        for slug in [m['slug'] for m in MANUSCRIPTS] + [b[0] for b in BOARDS]:
            p = os.path.join(PAGES_DIR, slug)
            if not os.path.exists(p):
                continue
            for pg in load_pages(p):
                page_index[(pg.get('file'), pg['page'])] = norm_probe(
                    ''.join(l.text for l in page_lines(pg)))
        bad = verify_pages(all_cards, page_index)
        print(f'校验 {len(all_cards)} 张, 失败 {len(bad)} 张')
        for b in bad[:20]:
            print('  ', b)


if __name__ == '__main__':
    main()
