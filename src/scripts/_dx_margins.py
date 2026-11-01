import json,glob,collections,re
pats={"GS":r"D:\math\build\pages\(3_1)*.jsonl","XD":r"D:\math\build\pages\(3_2)*.jsonl",
"GL3":r"D:\math\build\pages\(3_3)--大雪深埋概率论电子版*.jsonl","GL4":r"D:\math\build\pages\(3_4)*.jsonl"}
for tag,pat in pats.items():
    pages=[json.loads(l) for l in open(glob.glob(pat)[0],encoding="utf-8")]
    h=pages[0]["h"]; w=pages[0]["w"]
    top=collections.Counter(); bot=collections.Counter()
    for p in pages:
        for b in p["blocks"]:
            t=re.sub(r"\s+"," ",b["text"]).strip()
            if b["y1"]<=0.075*h: top[(round(b["y0"]),round(b["y1"]),t[:60])]+=1
            if b["y0"]>=0.925*h: bot[(round(b["y0"]),round(b["y1"]),t[:60])]+=1
    print("####",tag,"h",h)
    print(" TOP:", [(k,v) for k,v in top.most_common(12)])
    print(" BOT:", [(k,v) for k,v in bot.most_common(12)])
    print()
