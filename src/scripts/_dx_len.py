import json,glob,re
BOIL=("扫码了解更多课程","27考研：epsilon","关注公主号","抖音/小红书","By epsilon-delta")
def pages(pat):
    return [json.loads(l) for l in open(glob.glob(pat)[0],encoding="utf-8")]
pats={"GS":r"D:\math\build\pages\(3_1)*.jsonl","XD":r"D:\math\build\pages\(3_2)*.jsonl",
"GL3":r"D:\math\build\pages\(3_3)--大雪深埋概率论电子版*.jsonl","GL4":r"D:\math\build\pages\(3_4)*.jsonl"}
for tag,pat in pats.items():
    ps=pages(pat)
    stems=[];an=[];inline=0;open_end=0;tot=0
    cur=None
    for p in ps:
        for line in p["text"].split("\n"):
            t=line.strip()
            if not t: continue
            if any(b in t for b in BOIL): continue
            if re.fullmatch(r"\d{1,3}",t): continue
            if re.match(r"【例\s*\d+",t):
                cur={"s":[t],"a":[]}; stems.append(cur)
            elif cur is None: continue
            elif "【解析】" in t:
                inline+=1
                a,_,b=t.partition("【解析】")
                if a.strip(): cur["s"].append(a.strip())
                cur["a"].append(b.strip())
            else:
                (cur["a"] if cur["a"] else cur["s"]).append(t)
    sl=[len("".join(c["s"])) for c in stems]
    al=[len("".join(c["a"])) for c in stems if c["a"]]
    sl.sort()
    print("####",tag,"例",len(stems),"stem len p50",sl[len(sl)//2],"p90",sl[int(len(sl)*0.9)],"max",sl[-1])
    if al:
        al.sort(); print("   解析 len p50",al[len(al)//2],"p90",al[int(len(al)*0.9)],"max",al[-1])
    # truncated: stem ends with open token
    tr=[c["s"][-1][-25:] for c in stems if re.search(r"(=|∫|\+|-|/|,|，|\(|（|lim)$", c["s"][-1].strip()[-6:] if c["s"] else "")]
    print("   可能截断的题面结尾样例:",tr[:6],"count",len(tr))
