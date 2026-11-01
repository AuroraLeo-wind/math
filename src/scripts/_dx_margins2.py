import json,glob,re,collections
pats={"GS":r"D:\math\build\pages\(3_1)*.jsonl","XD":r"D:\math\build\pages\(3_2)*.jsonl",
"GL3":r"D:\math\build\pages\(3_3)--大雪深埋概率论电子版*.jsonl","GL4":r"D:\math\build\pages\(3_4)*.jsonl"}
for tag,pat in pats.items():
    pages=[json.loads(l) for l in open(glob.glob(pat)[0],encoding="utf-8")]
    h=pages[0]["h"]; w=pages[0]["w"]
    ys1=[]; low=[]
    maxy1_top=0
    for p in pages:
        for b in p["blocks"]:
            t=b["text"].strip()
            if b["y0"]>=790:
                low.append((round(b["y0"]),round(b["x0"]),t[:50]))
            else:
                ys1.append(b["y1"])
    ys1.sort()
    print("####",tag,"content y1 max:",round(ys1[-1],1),"p99:",round(ys1[int(len(ys1)*0.99)],1),"n<790:",len(low))
    bad=[x for x in low if not re.fullmatch(r"\d{1,3}",x[2]) and "扫码" not in x[2] and "epsilon-delta 数学" not in x[2] and "抖音" not in x[2] and "大雪深埋强化课讲义" not in x[2]]
    print("  非页脚样式的低区块:",bad[:10], "count",len(bad))
    # header x positions
    hdr=[(round(b["y0"]),round(b["x0"]),round(b["x1"]),b["text"].replace("\n","/")[:40]) for p in pages for b in p["blocks"] if b["y1"]<=40]
    print("  头部块样例:",collections.Counter([x[3][:30] for x in hdr]).most_common(4))
    print("  头部y范围:", min(x[0] for x in hdr) if hdr else None, max(x[0] for x in hdr) if hdr else None)
