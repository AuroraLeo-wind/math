# -*- coding: utf-8 -*-
"""_sk_lint.py — Agent Skills 规范体检器(临时调研脚本)

对齐 agentskills.io/specification 的硬约束 + 社区经验阈值,给出可执行的分数与问题清单。

用法:
    python scripts\\_sk_lint.py                     # 体检 ~/.dsh/skills 全部
    python scripts\\_sk_lint.py --root C:\\path\\to\\skills
    python scripts\\_sk_lint.py --skill C:\\Users\\PC\\.dsh\\skills\\kaoyan-math-kk
    python scripts\\_sk_lint.py --json out.json
"""
import argparse
import json
import os
import re
import sys

import yaml

ALLOWED_FIELDS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
MAX_NAME = 64
MAX_DESC = 1024
MAX_COMPAT = 500

# 经验阈值(非硬约束)
WARN_DESC_MIN = 120          # description 太短基本不可判别
WARN_BODY_LINES = 500        # 官方推荐上限
WARN_BODY_TOKENS = 5000      # 官方推荐上限
WARN_BYTES = 20000           # 超过 Claude Code 压缩重挂载截断点(superpowers 实测值)
WARN_REF_LINES = 400         # 单个 references 文件建议上限


def est_tokens(text):
    """粗略 token 估算:CJK 按 1 字≈1 token,其余按 4 字符≈1 token。"""
    cjk = len(re.findall(r"[\u4e00-\u9fff\u3000-\u303f]", text))
    rest = len(text) - cjk
    return int(cjk + rest / 4)


def split_frontmatter(text):
    if not text.startswith("---"):
        return None, None, "SKILL.md 未以 '---' 开头"
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", text, re.S)
    if not m:
        return None, None, "frontmatter 未闭合(缺少第二个 ---)"
    fm_raw, body = m.group(1), m.group(2)
    try:
        fm = yaml.safe_load(fm_raw) or {}
    except Exception as exc:  # noqa: BLE001
        return None, body, "frontmatter YAML 解析失败: %s" % exc
    if not isinstance(fm, dict):
        return None, body, "frontmatter 不是 dict"
    return fm, body, None


def check_skill(skill_dir):
    skill_dir = os.path.abspath(skill_dir)
    name_dir = os.path.basename(skill_dir)
    issues, infos, metrics = [], [], {}

    md_path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(md_path):
        return {"skill": name_dir, "path": skill_dir, "fatal": "缺少 SKILL.md",
                "issues": [], "infos": [], "metrics": {}, "score": 0}

    raw = open(md_path, encoding="utf-8").read()
    fm, body, err = split_frontmatter(raw)
    metrics["skill_md_lines"] = raw.count("\n") + (0 if raw.endswith("\n") else 1)
    metrics["skill_md_bytes"] = len(raw.encode("utf-8"))
    metrics["skill_md_tokens_est"] = est_tokens(raw)
    metrics["body_tokens_est"] = est_tokens(body or "")

    if err:
        issues.append(("E", "frontmatter", err))
        fm = fm or {}
    else:
        extra = set(fm) - ALLOWED_FIELDS
        if extra:
            issues.append(("E", "frontmatter", "出现规范外字段 %s(只允许 %s)"
                           % (sorted(extra), sorted(ALLOWED_FIELDS))))

    name = fm.get("name")
    if not name:
        issues.append(("E", "name", "缺少必填字段 name"))
    else:
        if len(name) > MAX_NAME:
            issues.append(("E", "name", "name 长度 %d > %d" % (len(name), MAX_NAME)))
        if name != name.lower():
            issues.append(("E", "name", "name 必须全小写"))
        if name.startswith("-") or name.endswith("-"):
            issues.append(("E", "name", "name 不能以连字符开头/结尾"))
        if "--" in name:
            issues.append(("E", "name", "name 不能含连续连字符"))
        if not re.fullmatch(r"[a-z0-9\-]+", name):
            issues.append(("E", "name", "name 只允许 a-z0-9 与连字符"))
        if name != name_dir:
            issues.append(("E", "name", "name(%s) 必须与目录名(%s) 一致" % (name, name_dir)))

    desc = fm.get("description")
    if not desc:
        issues.append(("E", "description", "缺少必填字段 description"))
    else:
        desc = str(desc)
        metrics["desc_chars"] = len(desc)
        if len(desc) > MAX_DESC:
            issues.append(("E", "description", "description 长度 %d > %d" % (len(desc), MAX_DESC)))
        if len(desc) < WARN_DESC_MIN:
            issues.append(("W", "description", "description 仅 %d 字符,判别力不足(建议 >=%d)"
                           % (len(desc), WARN_DESC_MIN)))
        if "\n" in desc:
            issues.append(("W", "description", "description 含换行:多数客户端解析 frontmatter 单行,易踩坑"))
        if not re.search(r"(use when|使用时|时使用|触发|when the user|当用户)", desc, re.I):
            issues.append(("W", "description", "缺少触发语(Use when / 当用户…时使用),模型难以判定何时加载"))
        # 触发词覆盖:中英混合关键词数量
        kws = set(re.findall(r"[\u4e00-\u9fff]{2,4}", desc)) | set(
            re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", desc))
        metrics["desc_keywords"] = len(kws)
        if len(kws) < 8:
            issues.append(("W", "description", "关键词仅 %d 个,建议把领域同义词写进 description" % len(kws)))

    compat = fm.get("compatibility")
    if compat is not None and len(str(compat)) > MAX_COMPAT:
        issues.append(("E", "compatibility", "compatibility 长度超 %d" % MAX_COMPAT))

    # ---- 体积预算 ----
    if metrics["skill_md_lines"] > WARN_BODY_LINES:
        issues.append(("W", "size", "SKILL.md %d 行 > %d 行推荐上限,应拆到 references/"
                       % (metrics["skill_md_lines"], WARN_BODY_LINES)))
    if metrics["skill_md_tokens_est"] > WARN_BODY_TOKENS:
        issues.append(("W", "size", "SKILL.md 约 %d tokens > %d 推荐上限"
                       % (metrics["skill_md_tokens_est"], WARN_BODY_TOKENS)))
    if metrics["skill_md_bytes"] >= WARN_BYTES:
        issues.append(("W", "size", "SKILL.md %d bytes >= %d,压缩重挂载会被截断"
                       % (metrics["skill_md_bytes"], WARN_BYTES)))

    # ---- 引用完整性 ----
    body = body or ""
    real_files = []
    for sub in ("references", "assets", "scripts"):
        d = os.path.join(skill_dir, sub)
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if os.path.isfile(os.path.join(d, fn)):
                    real_files.append("%s/%s" % (sub, fn))

    orphan = []
    for rel in real_files:
        base = rel.split("/", 1)[1]
        if rel in body or base in body:
            continue
        orphan.append(rel)

    # 只对"看起来像具体路径"的引用做缺失检查(排除占位符/通配/模板)
    cands = set(re.findall(r"(?:references|assets|scripts)/[^\s`\"'\)\]\|,，。;；]+", body))
    missing = []
    for c in cands:
        if any(ch in c for ch in "*{}<>[]$"):     # 通配或模板
            continue
        if any(c in rel or rel in c for rel in real_files):  # 含空格的中文文件名已被 real_files 覆盖
            continue
        if "." not in os.path.basename(c):        # 无扩展名,大概率是目录引用
            continue
        if not os.path.exists(os.path.join(skill_dir, c.replace("/", os.sep))):
            missing.append(c)

    for m in sorted(missing):
        issues.append(("E", "refs", "SKILL.md 引用了不存在的文件 %s" % m))
    for o in orphan:
        issues.append(("W", "refs", "文件 %s 未被 SKILL.md 提及(模型不会去读它)" % o))
    metrics["refs_referenced"] = len(real_files) - len(orphan)
    metrics["refs_orphan"] = len(orphan)

    for sub in ("references",):
        d = os.path.join(skill_dir, sub)
        if os.path.isdir(d):
            for fn in os.listdir(d):
                p = os.path.join(d, fn)
                if os.path.isfile(p):
                    ln = open(p, encoding="utf-8", errors="ignore").read().count("\n") + 1
                    if ln > WARN_REF_LINES:
                        infos.append(("I", "refs", "%s/%s 有 %d 行,建议再切细" % (sub, fn, ln)))

    # ---- 可移植性 / 易变内容 ----
    abs_hits = sorted(set(re.findall(r"[A-Za-z]:\\\\[^\s`\"'\)]+|[A-Za-z]:\\[^\s`\"'\)]+", body or "")))
    if abs_hits:
        infos.append(("I", "portability", "正文写死绝对路径 %s,建议在 §0 定义 ROOT 变量后统一引用"
                      % abs_hits[:3]))
    if re.search(r"(20\d\d-\d\d-\d\d|\bv?\d+\.\d+\.\d+\b)", body or ""):
        infos.append(("I", "volatile", "正文出现日期/版本号,易变内容建议移到 metadata 或 references"))

    # ---- 评分 ----
    score = 100
    for lvl, _, _ in issues:
        score -= 12 if lvl == "E" else 5
    for _ in infos:
        score -= 1
    score = max(0, score)

    return {"skill": name_dir, "path": skill_dir, "fatal": None,
            "issues": issues, "infos": infos, "metrics": metrics, "score": score}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(os.path.expanduser("~"), ".dsh", "skills"))
    ap.add_argument("--skill", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    targets = [args.skill] if args.skill else [
        os.path.join(args.root, d) for d in sorted(os.listdir(args.root))
        if os.path.isdir(os.path.join(args.root, d))
    ]

    results = [check_skill(t) for t in targets]
    for r in results:
        print("=" * 78)
        print("%-32s score=%3d" % (r["skill"], r["score"]))
        if r["fatal"]:
            print("  FATAL:", r["fatal"])
            continue
        m = r["metrics"]
        print("  lines=%d bytes=%d tokens~%d desc=%s"
              % (m["skill_md_lines"], m["skill_md_bytes"], m["skill_md_tokens_est"],
                 m.get("desc_chars", "-")))
        for lvl, cat, msg in r["issues"]:
            print("  [%s] %-12s %s" % (lvl, cat, msg))
        for lvl, cat, msg in r["infos"]:
            print("  [%s] %-12s %s" % (lvl, cat, msg))
        if not r["issues"] and not r["infos"]:
            print("  OK 无问题")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("\nJSON ->", args.json)

    bad = [r for r in results if r.get("fatal") or any(i[0] == "E" for i in r["issues"])]
    print("\n合计 %d 个 skill,硬错误 %d 个" % (len(results), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
