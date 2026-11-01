import json, re, sys, os
sys.stdout.reconfigure(encoding="utf-8")
man = {x["file"]: x["slug"] for x in json.load(open("build/manifest.json", encoding="utf-8"))}
slug = man["(3.3)--大雪深埋概率论电子版（含解析）.pdf"]
def norm(s):
    s=(s or "").replace("\u200b","")
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]","",s)
needle = norm("常常把没有充分理由不能轻易否定的假设取为原假设")
with open(f"build/pages/{slug}.jsonl", encoding="utf-8") as fh:
    for i, line in enumerate(fh):
        t = json.loads(line)["text"]
        if needle[:12] in norm(t):
            print(f"命中页: p{i}")
for i in range(45, 52):
    with open(f"build/pages/{slug}.jsonl", encoding="utf-8") as fh:
        for j, line in enumerate(fh):
            if j == i:
                t = norm(json.loads(line)["text"])
                print(f"p{i}: len={len(t)}  head={t[:60]}")
