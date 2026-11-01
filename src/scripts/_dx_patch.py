import io
p = r"D:\math\scripts\kb_dx_extract.py"
src = io.open(p, encoding="utf-8").read()
start = src.index("# ---------------------------------------------------------------- method / pitfall ")
end = src.index("def dedup(cards")
new = '''# ---------------------------------------------------------------- method / pitfall 卡
CN_NUM = "一二三四五六七八九十"
SUBHEAD_CN = re.compile(rf"^[（(]([{CN_NUM}]{{1,2}})[)）]\\s*(\\S.*)$")
SUBHEAD_NUM = re.compile(r"^[（(](\\d{1,2})[)）]\\s*(\\S.*)$")
SUBHEAD_DOT = re.compile(r"^(\\d{1,2})\\s*[.、]\\s*(\\S.*)$")
MATH_SYMBOLS = "=∼~⟺⇒≥≤"
NOTE_KEYS = ("NOTE", "注", "小结", "总结")
# 易错/反例/边界提示 —— 这类段落单独立 pitfall 卡
PITFALL_MARK = ("注意", "易错", "陷阱", "混淆", "不一定", "得不到", "不能", "不可",
                "切记", "不要", "错在", "区别")
CONT_HEAD = ("=", "＝", "+", "−", "-", ",", "，", ")", "）", "≥", "≤")


def cjk_count(s: str) -> int:
    return len(re.findall(r"[\\u4e00-\\u9fff]", s))


def merge_fragments(lines: list[str]) -> list[str]:
    """OCR 把公式拆成一堆 1~3 字碎片(如 "∞" "n=0" "i=1"),先并回上一行。"""
    out: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if out and (len(s) <= 3 or re.fullmatch(r"[=+\\-−×*/(),，。；:：·|]+", s)):
            out[-1] = out[-1] + " " + s
        else:
            out.append(s)
    return out


def as_subhead(s: str) -> str | None:
    """(一)xxx / (1) xxx / 1. xxx 这类小节标题;含数学符号或太长的不算。"""
    if len(s) > 24 or any(ch in s for ch in MATH_SYMBOLS):
        return None
    if s.endswith(("，", ",", "；", ";", "。", "：")):
        return None
    m = SUBHEAD_CN.match(s)
    if m and len(m.group(2)) <= 16:
        return m.group(2).strip()
    m = SUBHEAD_NUM.match(s)
    if m and len(m.group(2)) <= 14:
        return m.group(2).strip()
    m = SUBHEAD_DOT.match(s)
    if m and len(m.group(2)) <= 14 and cjk_count(m.group(2)) >= 2:
        return m.group(2).strip()
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
    parent: str | None = None
    for ln in merged:
        s = ln.strip()
        if not s:
            continue
        sub = as_subhead(s)
        if sub:
            parent = sub
            cur = {"label": sub, "raw_label": s, "parent": None, "level": "sub", "lines": []}
            segs.append(cur)
            continue
        lab = as_label(s)
        if lab:
            level = "note" if (lab.upper().startswith("NOTE") or lab in ("注", "小结", "总结")) else "label"
            cur = {"label": lab, "raw_label": s, "parent": parent, "level": level, "lines": []}
            segs.append(cur)
            continue
        if cur is None:
            cur = {"label": None, "raw_label": "", "parent": None, "level": "topic", "lines": []}
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
        t = re.sub(r"\\s+", "", s)
        t = re.sub(r"^[（(]?\\d{1,2}[)）.、]", "", t).strip("，,。；;、")
        if len(t) < 8 or cjk_count(t) < 2:
            continue
        cand.append(clip40(t))
    key = [c for c in cand if any(k in c for k in
                                  ("若", "则", "⟺", "用", "先", "再", "取", "判", "求", "当",
                                   "即", "得", "⇒", "设", "注意", "当且仅当"))]
    steps: list[str] = []
    for s in (key or cand):
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
        t = re.sub(r"\\s+", " ", s).strip()
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
        t = re.sub(r"\\s+", "", s)
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
    prose = [s for s in lines if cjk_count(s) >= 6]
    if prose:
        return clip_title(prose[0])
    semi = [s for s in lines if cjk_count(s) >= 2]
    if semi:
        return clip_title(semi[0])
    if lines:
        return clip_title(lines[0])
    return ""


def make_method_card(seg: dict, pre: dict, subject: str,
                     title_used: Counter, suffix_seq: Counter) -> tuple[dict | None, str]:
    """一个铺垫小节 -> 一张 method/pitfall 卡。返回 (card, 丢弃原因)。"""
    topic = pre.get("topic_label") or pre.get("chapter") or "未分类"
    chapter = pre.get("chapter") or topic
    lines = [x for x in seg["lines"] if x.strip()]
    body = "".join(lines)
    if len(body) < 25 or cjk_count(body) + body.count("=") < 4:
        return None, "太短/纯过渡"

    level = seg["level"]
    label = seg["label"]
    parent = seg["parent"]

    kind = classify_segment(lines, level, label)
    gist = pick_gist(lines, label)

    parts = [topic]
    if parent and parent != topic:
        parts.append(parent)
    if label and level in ("sub", "label", "note"):
        parts.append(label if level != "note" else f"{label}")
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
    if parent and parent != topic:
        symptom.append(f"小节：{parent}")
    if label and level != "sub":
        symptom.append(f"标签：{label}")
    if "⟺" in body:
        symptom.append("判别条件型：逐条核对充要条件")

    raw_lines = ([seg["raw_label"]] if seg["raw_label"] else []) + lines
    raw = "【题型铺垫】\\n" + "\\n".join(raw_lines)
    truncated = False
    if len(raw) > MAX_RAW:
        raw = raw[:MAX_RAW].rstrip() + "\\n…（原文后段省略）"
        truncated = True

    inferred = ["title", "symptom"]
    if chain:
        inferred.append("method_chain")

    card = {
        "id": "",
        "kind": kind,
        "subject": subject,
        "chapter": chapter,
        "topic": parent or label or topic,
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
            "locator": f"{chapter}/题型铺垫/{label or parent or topic}",
        },
        "tags": [x for x in dict.fromkeys([chapter, topic, parent, label]) if x],
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


'''
io.open(p, "w", encoding="utf-8").write(src[:start] + new + src[end:])
print("patched")
