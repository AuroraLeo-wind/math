import json,glob,re
pats={"GS":r"D:\math\build\pages\(3_1)*.jsonl","XD":r"D:\math\build\pages\(3_2)*.jsonl",
"GL3":r"D:\math\build\pages\(3_3)--大雪深埋概率论电子版*.jsonl","GL4":r"D:\math\build\pages\(3_4)*.jsonl"}
BOIL=["扫码了解更多课程","27考研：epsilon","关注公主号","抖音/小红书","By epsilon-delta"]
for tag,pat in pats.items():
    pages=[json.loads(l) for l in open(glob.glob(pat)[0],encoding="utf-8")]
    h=pages[0]["h"]
    seq=[]; midblock=[]; chapters=[]
    cur=None
    for p in pages:
        for b in p["blocks"]:
            t=b["text"].strip()
            if any(x in t for x in BOIL): continue
            if b["y0"]>=790 or b["y1"]<=40: continue
            if 60<b["y0"]<75 and len(t)<=12 and not t.startswith("【"): cur=t
            ms=list(re.finditer(r"【例\s*(\d+)\s*】",t))
            if ms:
                if ms[0].start()!=0: midblock.append((p["page"],t[:80]))
                for m in ms: seq.append((cur,int(m.group(1)),p["page"]))
    nums={}
    for ch,n,pg in seq: nums.setdefault(ch,[]).append(n)
    print("####",tag)
    for ch,v in nums.items():
        gaps=[]
        for a,b2 in zip(v,v[1:]):
            if b2!=a+1: gaps.append((a,b2))
        print("  ",ch,"count",len(v),"first/last",v[0],v[-1],"gaps",gaps[:12])
    print("  mid-block 例 markers:",midblock[:5], len(midblock))
