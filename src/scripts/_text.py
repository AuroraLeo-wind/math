# -*- coding: utf-8 -*-
"""共用分词与打分工具。数学符号、LaTeX 片段做整体保留，避免 BM25 把公式切碎。"""
import re

PUNCT = re.compile(r"[\s\u3000·,，。、；;：:!！?？(){}\[\]【】<>《》\"'`~@#$%^&*+=|\\/—\-_…]+")
# 整体保留的数学片段（不被 jieba 切开）
MATH_TOKENS = ["洛必达", "泰勒展开", "等价无穷小", "等价无穷大", "夹逼", "中值定理",
               "拉格朗日", "罗尔", "柯西", "积分中值定理", "变限积分", "二重积分",
               "三重积分", "曲线积分", "曲面积分", "特征值", "特征向量", "二次型",
               "正定", "相似对角化", "行列式", "随机变量", "分布函数", "数学期望",
               "极大似然", "无偏估计", "置信区间", "假设检验", "幂级数", "微分方程",
               "反常积分", "定积分", "不定积分", "偏导数", "全微分", "方向导数",
               "梯度", "散度", "旋度", "格林公式", "高斯公式", "斯托克斯"]

_jieba = None


def _load():
    global _jieba
    if _jieba is None:
        import jieba
        jieba.setLogLevel(20)
        for w in MATH_TOKENS:
            jieba.add_word(w)
        _jieba = jieba
    return _jieba


def tokenize(text):
    j = _load()
    text = PUNCT.sub(" ", str(text or ""))
    out = []
    for t in j.lcut_for_search(text):
        t = t.strip()
        if not t:
            continue
        if t.isdigit():                 # 章节编号「1.6」这类纯数字只会稀释相似度
            if len(t) >= 2:
                out.append(t)
            continue
        if len(t) > 1 or t.isalpha():
            out.append(t.lower())
    return out


def norm_key(s):
    return re.sub(r"[\s\u3000（）()【】\[\]、，。．\.]", "", str(s or ""))
