# -*- coding: utf-8 -*-
"""L0 抽取:遍历 PDF -> build/pages/<slug>.jsonl(每页一条:文本 + 带坐标文本块 + 图像数)

用法:
    python scripts/extract_pdf.py                # 增量:跳过已存在的 slug
    python scripts/extract_pdf.py --force        # 全量重抽
    python scripts/extract_pdf.py --filter kk    # 只抽文件名含 kk 的
"""
import os
import re
import json
import sys
import hashlib
import argparse

import pymupdf

ROOT = r"D:\Download\math"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "pages")


def slugify(name: str) -> str:
    base = os.path.splitext(name)[0]
    base = base.replace("（", "(").replace("）", ")").replace("《", "").replace("》", "")
    base = re.sub(r"[^\w\u4e00-\u9fff()\-]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    h = hashlib.md5(name.encode("utf-8")).hexdigest()[:6]
    return f"{base[:60]}__{h}"


def iter_pdfs():
    for dp, _, fn in os.walk(ROOT):
        for f in sorted(fn):
            if f.lower().endswith(".pdf"):
                yield os.path.join(dp, f)


def blocks_of(page):
    out = []
    for b in page.get_text("blocks"):
        # b = (x0, y0, x1, y1, text, block_no, block_type)
        txt = b[4].replace("\r", "")
        txt = re.sub(r"[ \t]+\n", "\n", txt)
        txt = re.sub(r"\n{2,}", "\n", txt).strip()
        if not txt:
            continue
        out.append({
            "x0": round(float(b[0]), 1), "y0": round(float(b[1]), 1),
            "x1": round(float(b[2]), 1), "y1": round(float(b[3]), 1),
            "text": txt, "type": int(b[6]),
        })
    return out


def extract(path, force=False, only=None):
    name = os.path.basename(path)
    if only and only.lower() not in name.lower():
        return None
    slug = slugify(name)
    dst = os.path.join(OUT_DIR, slug + ".jsonl")
    if os.path.exists(dst) and not force:
        return {"slug": slug, "skipped": True}
    doc = pymupdf.open(path)
    n = len(doc)
    chars = 0
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        for i in range(n):
            page = doc[i]
            text = page.get_text("text")
            chars += len(text.strip())
            rec = {
                "file": name,
                "page": i,
                "w": round(page.rect.width, 1),
                "h": round(page.rect.height, 1),
                "text": text,
                "blocks": blocks_of(page),
                "images": len(page.get_images(full=True)),
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    doc.close()
    return {
        "slug": slug, "file": name, "pages": n,
        "chars_per_page": round(chars / max(1, n), 1),
        "size_mb": round(os.path.getsize(path) / 1048576, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--filter", default=None)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    report = []
    for p in iter_pdfs():
        try:
            r = extract(p, force=args.force, only=args.filter)
            if r is None:
                continue
            report.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"file": os.path.basename(p), "error": str(e)[:200]}, ensure_ascii=False), flush=True)
    manifest = os.path.join(os.path.dirname(OUT_DIR), "manifest.json")
    old = {}
    if os.path.exists(manifest):
        old = {m["slug"]: m for m in json.load(open(manifest, encoding="utf-8")) if "slug" in m}
    for r in report:
        if "slug" in r and not r.get("skipped"):
            old[r["slug"]] = r
    json.dump(sorted(old.values(), key=lambda x: x.get("file", "")),
              open(manifest, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nDONE  extracted={sum(1 for r in report if not r.get('skipped'))} "
          f"skipped={sum(1 for r in report if r.get('skipped'))} -> {OUT_DIR}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
